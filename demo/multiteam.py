"""Publish shared AML assets and verify three independently billed team workspaces."""

import argparse
import base64
import json
import logging
import shlex
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import StringIO

import requests
from azure.ai.ml import Input, MLClient, Output, command, load_job
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import (
    AmlCompute,
    IdentityConfiguration,
    NetworkSettings,
    PipelineJob,
)
from azure.identity import AzureCliCredential

from demo.workspace import ROOT, grant_role

LOGGER = logging.getLogger(__name__)
REPORT = ROOT / "local" / "multiteam.json"
VERSION = "1"
COMPONENT_VERSION = "3"
BLOB_CONTRIBUTOR = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
READER = "acdd72a7-3385-48ef-bd42-f606fba81ae7"


def team_configs(subscription: str) -> list[dict[str, str]]:
    return [
        {
            "subscription_id": subscription,
            "resource_group": f"rg-kt-mlops-team-{number}",
            "workspace_name": f"mlw-ktmlops-secure-{number}",
            "compute_subnet": (
                f"/subscriptions/{subscription}/resourceGroups/rg-kt-mlops-team-{number}"
                f"/providers/Microsoft.Network/virtualNetworks/vnet-ktmlops{number}/subnets/compute"
            ),
        }
        for number in range(1, 4)
    ]


def record(**updates) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    report.update(updates, updated_utc=datetime.now(UTC).isoformat())
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")


def workspace_client(config: dict[str, str]) -> MLClient:
    return MLClient(
        AzureCliCredential(process_timeout=600),
        config["subscription_id"],
        config["resource_group"],
        config["workspace_name"],
    )


def authorized_request(method: str, url: str, *, audience: str, **kwargs) -> requests.Response:
    token = AzureCliCredential(process_timeout=600).get_token(audience).token
    for attempt in range(5):
        response = requests.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}", "x-ms-version": "2023-11-03"},
            timeout=120,
            **kwargs,
        )
        if response.status_code != 429 or attempt == 4:
            break
        delay = int(
            response.headers.get(
                "Retry-After",
                response.headers.get("x-ms-ratelimit-microsoft.consumption-retry-after", "60"),
            )
        )
        LOGGER.warning("HTTP 429 from %s; retrying in %s seconds.", url.split("?")[0], delay)
        time.sleep(delay)
    response.raise_for_status()
    return response


def publish(subscription: str, registry_name: str) -> None:
    credential = AzureCliCredential(process_timeout=600)
    source = MLClient(credential, subscription, "rg-kt-mlops", "mlw-ktmlops-secure")
    registry = MLClient(credential, registry_name=registry_name)
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    reference = f"azureml://registries/{registry_name}"
    if report.get("model") == f"{reference}/models/telco-shared/versions/{VERSION}":
        model = registry.models.get("telco-shared", VERSION)
    else:
        model = source.models.share(
            "telco-churn-classifier",
            "1",
            share_with_name="telco-shared",
            share_with_version=VERSION,
            registry_name=registry_name,
        )
    record(registry=registry_name, model=model.id)
    if report.get("environment") == f"{reference}/environments/kt-shared-cpu/versions/{VERSION}":
        environment = registry.environments.get("kt-shared-cpu", VERSION)
    else:
        environment = source.environments.share(
            "kt-sklearn-mlflow",
            "2",
            share_with_name="kt-shared-cpu",
            share_with_version=VERSION,
            registry_name=registry_name,
        )
    record(environment=environment.id)
    probe_source = (ROOT / "demo" / "registry_probe" / "probe.py").read_text(encoding="utf-8")
    # AML normalizes command whitespace, including whitespace inside quoted source.
    encoded_probe = base64.b64encode(probe_source.encode("utf-8")).decode("ascii")
    component = command(
        name="verify_shared_model",
        version=COMPONENT_VERSION,
        display_name="Shared model consumption and team data isolation",
        description="Loads the real shared model; own Blob succeeds and peer Blob is forbidden.",
        environment=environment.id,
        inputs={
            "model": Input(type=AssetTypes.MLFLOW_MODEL),
            "team": Input(type="string"),
            "own_blob": Input(type="string"),
            "peer_blob": Input(type="string"),
        },
        outputs={"report": Output(type=AssetTypes.URI_FOLDER)},
        command="python -c "
        + shlex.quote(f"exec(__import__('base64').b64decode({encoded_probe!r}))")
        + " --model ${{inputs.model}} --team ${{inputs.team}} "
        "--own-blob ${{inputs.own_blob}} --peer-blob ${{inputs.peer_blob}} "
        "--report ${{outputs.report}}",
    )
    registered = registry.components.create_or_update(component.component)
    record(
        registry=registry_name, model=model.id, environment=environment.id, component=registered.id
    )
    LOGGER.info("Published model, environment and component to %s.", registry_name)


def prepare_team(config: dict[str, str], registry_id: str) -> dict[str, str]:
    ml = workspace_client(config)
    workspace = ml.workspaces.get(ml.workspace_name)
    if workspace.managed_network.isolation_mode.lower() != "disabled":
        raise RuntimeError("Deploy the team-owned VNet foundation before creating private compute.")
    team_scope = f"/subscriptions/{ml.subscription_id}/resourceGroups/{ml.resource_group_name}"
    grant_role(team_scope, workspace.identity.principal_id, READER, ml.subscription_id)
    grant_role(registry_id, workspace.identity.principal_id, READER, ml.subscription_id)
    team = f"team-{ml.workspace_name.rsplit('-', 1)[-1]}"
    compute = ml.compute.begin_create_or_update(
        AmlCompute(
            name="cpu-secure",
            size="Standard_DS3_v2",
            min_instances=0,
            max_instances=1,
            idle_time_before_scale_down=120,
            ssh_public_access_enabled=False,
            enable_node_public_ip=False,
            network_settings=NetworkSettings(subnet=config["compute_subnet"]),
            identity=IdentityConfiguration(type="SystemAssigned"),
            tags={"team": team, "costCenter": f"kt-mlops-{team}"},
        )
    ).result()
    grant_role(
        workspace.storage_account,
        compute.identity.principal_id,
        BLOB_CONTRIBUTOR,
        ml.subscription_id,
    )
    grant_role(registry_id, compute.identity.principal_id, READER, ml.subscription_id)
    account = workspace.storage_account.rsplit("/", 1)[-1]
    container = f"https://{account}.blob.core.windows.net/team-probe"
    token = AzureCliCredential(process_timeout=600).get_token("https://storage.azure.com/.default")
    response = requests.put(
        f"{container}?restype=container",
        headers={"Authorization": f"Bearer {token.token}", "x-ms-version": "2023-11-03"},
        data=b"",
        timeout=60,
    )
    if response.status_code == 409 and response.headers.get("x-ms-error-code") == (
        "ContainerAlreadyExists"
    ):
        authorized_request(
            "HEAD",
            container + "?restype=container",
            audience="https://storage.azure.com/.default",
        )
    else:
        response.raise_for_status()
    blob = f"{container}/marker.txt"
    response = requests.put(
        blob,
        headers={
            "Authorization": f"Bearer {token.token}",
            "x-ms-version": "2023-11-03",
            "x-ms-blob-type": "BlockBlob",
        },
        data=team.encode(),
        timeout=60,
    )
    response.raise_for_status()
    return {**config, "storage": workspace.storage_account, "blob": blob, "team": team}


def prepare(subscription: str, registry_name: str) -> None:
    registry_id = (
        f"/subscriptions/{subscription}/resourceGroups/rg-kt-mlops/providers/"
        f"Microsoft.MachineLearningServices/registries/{registry_name}"
    )
    registry = authorized_request(
        "GET",
        f"https://management.azure.com{registry_id}?api-version=2025-06-01",
        audience="https://management.azure.com/.default",
    ).json()
    registry_storage = registry["properties"]["regionDetails"][0]["storageAccountDetails"][0][
        "systemCreatedStorageAccount"
    ]["armResourceId"]["resourceId"]
    record(
        registry_storage=registry_storage,
        registry_managed_group=registry["properties"]["managedResourceGroup"]["resourceId"].rsplit(
            "/", 1
        )[-1],
    )
    with ThreadPoolExecutor(max_workers=3) as pool:
        teams = list(
            pool.map(
                lambda config: prepare_team(config, registry_id),
                team_configs(subscription),
            )
        )
    record(teams=teams)


def consumer_job(
    registry: str, version: str, team: str, own_blob: str, peer_blob: str
) -> PipelineJob:
    reference = f"azureml://registries/{registry}"
    return load_job(
        source=StringIO(
            json.dumps(
                {
                    "type": "pipeline",
                    "display_name": f"{team}-shared-registry-consumer",
                    "tags": {"team": team, "costCenter": f"kt-mlops-{team}"},
                    "settings": {"force_rerun": True},
                    "outputs": {"report": {"type": "uri_folder"}},
                    "jobs": {
                        "consume": {
                            "type": "command",
                            "component": (
                                f"{reference}/components/verify_shared_model/versions/{COMPONENT_VERSION}"
                            ),
                            "compute": "cpu-secure",
                            "identity": {"type": "managed"},
                            "outputs": {"report": "${{parent.outputs.report}}"},
                            "inputs": {
                                "model": {
                                    "type": "mlflow_model",
                                    "path": f"{reference}/models/telco-shared/versions/{version}",
                                    "mode": "download",
                                },
                                "team": team,
                                "own_blob": own_blob,
                                "peer_blob": peer_blob,
                            },
                        }
                    },
                }
            )
        )
    )


def collect_consumer_report(ml: MLClient, job_name: str, team: str) -> dict[str, object]:
    children = list(ml.jobs.list(parent_job_name=job_name))
    if len(children) != 1 or children[0].status != "Completed":
        raise RuntimeError(f"{ml.workspace_name}/{job_name}: expected one completed consumer.")
    destination = ROOT / "local" / ml.workspace_name / job_name
    # Pipeline named-output URIs can be absent; child stdout is a persisted run artifact.
    ml.jobs.download(children[0].name, download_path=str(destination), all=True)
    log = destination / "artifacts" / "user_logs" / "std_log.txt"
    proof = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    expected = {
        "team": team,
        "own_blob_status": 200,
        "peer_blob_status": 403,
        "peer_error": "AuthorizationPermissionMismatch",
        "identity": "compute-managed-identity",
    }
    if not isinstance(proof, dict) or any(
        proof.get(key) != value for key, value in expected.items()
    ):
        raise AssertionError(f"Unexpected consumer verification: {proof}")
    predictions = proof.get("predictions")
    if not isinstance(predictions, list) or len(predictions) != 3 or not set(predictions) <= {0, 1}:
        raise AssertionError(f"Unexpected consumer verification predictions: {predictions}")
    (destination / "verification.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return proof


def consume(subscription: str, registry_name: str) -> None:
    teams = json.loads(REPORT.read_text(encoding="utf-8"))["teams"]
    submitted = []
    for index, team in enumerate(teams):
        ml = workspace_client(team_configs(subscription)[index])
        job = ml.jobs.create_or_update(
            consumer_job(
                registry_name, VERSION, team["team"], team["blob"], teams[(index + 1) % 3]["blob"]
            ),
            experiment_name="kt-shared-registry",
        )
        submitted.append({"workspace": ml.workspace_name, "job": job.name})
        record(consumer_jobs=submitted)
    for config, team, item in zip(team_configs(subscription), teams, submitted, strict=True):
        ml = workspace_client(config)
        ml.jobs.stream(item["job"])
        completed = ml.jobs.get(item["job"])
        item["status"] = completed.status
        record(consumer_jobs=submitted)
        if completed.status != "Completed":
            raise RuntimeError(f"{ml.workspace_name}/{completed.name}: {completed.status}")
        item["verification"] = collect_consumer_report(ml, item["job"], team["team"])
        record(consumer_jobs=submitted)


def cost_rows(payload: dict) -> list[dict]:
    properties = payload["properties"]
    columns = [column["name"] for column in properties["columns"]]
    rows = properties["rows"]
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("Cost result columns and row lengths differ.")
    return [dict(zip(columns, row, strict=True)) for row in rows]


def costs(subscription: str) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    groups = ["rg-kt-mlops"] + [item["resource_group"] for item in team_configs(subscription)]
    if report.get("registry_managed_group"):
        groups.append(report["registry_managed_group"])
    url = (
        f"https://management.azure.com/subscriptions/{subscription}/providers/"
        "Microsoft.CostManagement/query?api-version=2025-03-01"
    )
    query = {
        "type": "ActualCost",
        "timeframe": "MonthToDate",
        "dataset": {
            "granularity": "None",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ResourceGroupName"}],
            "filter": {
                "dimensions": {
                    "name": "ResourceGroupName",
                    "operator": "In",
                    "values": groups,
                }
            },
        },
    }
    rows = []
    while url:
        payload = authorized_request(
            "POST", url, audience="https://management.azure.com/.default", json=query
        ).json()
        rows.extend(cost_rows(payload))
        url = payload["properties"].get("nextLink")
    record(actual_cost=rows, cost_next_link=None)
    print(json.dumps(rows, indent=2))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["publish", "prepare", "consume", "costs"])
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--registry", default="mlr-ktmlops-shared")
    return parser


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    args = create_parser().parse_args()
    if args.action == "costs":
        costs(args.subscription)
    else:
        {"publish": publish, "prepare": prepare, "consume": consume}[args.action](
            args.subscription, args.registry
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
