"""Register a pinned HF snapshot and serve it on an authenticated CPU online endpoint."""

import json
import logging
import os
import time
from datetime import UTC, datetime

import requests
from azure.ai.ml import MLClient
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import (
    CodeConfiguration,
    Environment,
    ManagedOnlineDeployment,
    ManagedOnlineEndpoint,
    Model,
    OnlineRequestSettings,
    ProbeSettings,
)
from azure.identity import AzureCliCredential
from huggingface_hub import snapshot_download

from demo.pipeline import BASE_IMAGE
from demo.workspace import ENDPOINT, ROOT, grant_role, read_state, save_state

LOGGER = logging.getLogger(__name__)
HF_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
HF_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def deploy(ml: MLClient) -> None:
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    folder = ROOT / "local" / "hf-model"
    snapshot_download(
        HF_MODEL,
        revision=HF_REVISION,
        local_dir=folder,
        allow_patterns=[
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "README.md",
            "LICENSE*",
        ],
    )
    model = ml.models.create_or_update(
        Model(
            name="hf-minilm-ticket-router",
            version="1",
            path=str(folder),
            type=AssetTypes.CUSTOM_MODEL,
            description="22.7M English embedding model; Apache-2.0; CPU; not a generative LLM.",
            tags={"huggingface_model": HF_MODEL, "revision": HF_REVISION, "license": "Apache-2.0"},
        )
    )
    env = ml.environments.create_or_update(
        Environment(
            name="kt-hf-cpu",
            version="1",
            image=BASE_IMAGE,
            conda_file=str(ROOT / "environments" / "serving.yml"),
            description="Offline CPU inference; pinned torch CPU and transformers; no remote code.",
        )
    )
    endpoint = ml.online_endpoints.begin_create_or_update(
        ManagedOnlineEndpoint(
            name=ENDPOINT,
            description="Synthetic English telco routing, HF MiniLM CPU. Entra authentication.",
            auth_mode="aad_token",
            public_network_access="enabled",
            tags={"purpose": "training-demo", "data": "synthetic"},
        )
    ).result()
    workspace = ml.workspaces.get(ml.workspace_name)
    for scope, role in [
        (workspace.storage_account, "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"),
        (workspace.container_registry, "7f951dda-4ed3-4680-a7ca-43fe172d538d"),
    ]:
        grant_role(scope, endpoint.identity.principal_id, role, ml.subscription_id)
    save_state(
        endpoint_name=endpoint.name, scoring_uri=endpoint.scoring_uri, hf_revision=HF_REVISION
    )
    deployment = ManagedOnlineDeployment(
        name="blue",
        endpoint_name=ENDPOINT,
        model=model.id,
        environment=env.id,
        code_configuration=CodeConfiguration(
            code=str(ROOT / "demo" / "serving"), scoring_script="score.py"
        ),
        instance_type="Standard_DS2_v2",
        instance_count=1,
        app_insights_enabled=True,
        environment_variables={
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        },
        request_settings=OnlineRequestSettings(
            request_timeout_ms=30000, max_concurrent_requests_per_instance=1
        ),
        liveness_probe=ProbeSettings(initial_delay=60, period=10, failure_threshold=30),
        readiness_probe=ProbeSettings(initial_delay=60, period=10, failure_threshold=30),
    )
    ml.online_deployments.begin_create_or_update(deployment).result()
    endpoint.traffic = {"blue": 100}
    ml.online_endpoints.begin_create_or_update(endpoint).result()
    save_state(endpoint_deployment="blue")


def verify(ml: MLClient) -> dict:
    state = read_state()
    for job in state.get("pipeline_jobs", []):
        status = ml.jobs.get(job["name"]).status
        if status != "Completed":
            raise AssertionError(f"Pipeline {job['name']}: {status}")
    data = {
        name: [item.version for item in ml.data.list(name=name)]
        for name in ["telco-churn", "telco-churn-table"]
    }
    if any(not {"1", "2"} <= set(versions) for versions in data.values()):
        raise AssertionError(f"Missing versioned data assets: {data}")
    models = [model.version for model in ml.models.list(name="telco-churn-classifier")]
    if not {"1", "2"} <= set(models):
        raise AssertionError(f"Missing MLflow model versions: {models}")
    endpoint = ml.online_endpoints.get(ENDPOINT)
    deployment = ml.online_deployments.get("blue", ENDPOINT)
    if endpoint.provisioning_state != "Succeeded" or deployment.provisioning_state != "Succeeded":
        raise AssertionError("Endpoint and deployment must both be Succeeded.")
    if endpoint.auth_mode != "aad_token" or endpoint.traffic != {"blue": 100}:
        raise AssertionError("Endpoint must have Entra authentication and 100% blue traffic.")
    payload = json.loads((ROOT / "samples" / "tickets.json").read_text(encoding="utf-8"))
    token = AzureCliCredential(process_timeout=120).get_token("https://ml.azure.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}
    latencies = []
    for _ in range(3):
        started = time.perf_counter()
        response = requests.post(endpoint.scoring_uri, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        latencies.append(round(time.perf_counter() - started, 3))
    result = response.json()
    if isinstance(result, str):
        result = json.loads(result)
    actual = [item["intent"] for item in result["predictions"]]
    if actual != ["billing", "network", "cancellation"] or result["embedding_dimension"] != 384:
        raise AssertionError(f"Unexpected endpoint output: {result}")
    anonymous = requests.post(endpoint.scoring_uri, json=payload, timeout=30)
    if anonymous.status_code not in (401, 403):
        raise AssertionError(f"Anonymous request unexpectedly returned {anonymous.status_code}.")
    invalid = requests.post(endpoint.scoring_uri, headers=headers, json={"texts": []}, timeout=30)
    if invalid.status_code < 400 or invalid.status_code >= 500:
        raise AssertionError(f"Invalid input must yield 4xx, not {invalid.status_code}.")
    report = {
        "verified_utc": datetime.now(UTC).isoformat(),
        "data_versions": data,
        "churn_model_versions": models,
        "pipeline_jobs": state.get("pipeline_jobs", []),
        "endpoint": ENDPOINT,
        "endpoint_state": endpoint.provisioning_state,
        "deployment_state": deployment.provisioning_state,
        "authentication": endpoint.auth_mode,
        "traffic": endpoint.traffic,
        "inference": result,
        "request_seconds": latencies,
        "anonymous_status": anonymous.status_code,
        "invalid_input_status": invalid.status_code,
        "external_run_id": state.get("external_run_id"),
    }
    path = ROOT / "local" / "verification.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Live verification passed. Evidence: %s", path)
    return report
