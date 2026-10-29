"""Publish the existing training sample into each team's Studio notebook share."""

import argparse
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from azure.core.exceptions import ResourceExistsError
from azure.identity import AzureCliCredential
from azure.storage.fileshare import ShareServiceClient

from demo.multiteam import authorized_request, team_configs, workspace_client
from demo.workspace import ROOT

LOGGER = logging.getLogger(__name__)
FOLDER = "Users/kt-demo/kt-mlops-training"


def sample_files(config: dict[str, str]) -> dict[str, bytes]:
    files = {
        "01_submit_training.ipynb": (ROOT / "notebooks" / "01_submit_training.ipynb").read_bytes(),
        "config.json": json.dumps(config, indent=2).encode("utf-8"),
    }
    for name in ("__init__.py", "data.py", "training.py"):
        files[f"src/demo/{name}"] = (ROOT / "demo" / name).read_bytes()
    return files


def publish_team(config: dict[str, str]) -> dict:
    ml = workspace_client(config)
    team = ml.workspace_name.rsplit("-", 1)[-1]
    identity_id = (
        f"/subscriptions/{config['subscription_id']}/resourceGroups/{config['resource_group']}"
        f"/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-kt-notebook-{team}"
    )
    identity = authorized_request(
        "GET",
        f"https://management.azure.com{identity_id}?api-version=2023-01-31",
        audience="https://management.azure.com/.default",
    ).json()
    sample_config = {
        key: config[key] for key in ("subscription_id", "resource_group", "workspace_name")
    }
    sample_config["notebook_identity_client_id"] = identity["properties"]["clientId"]
    datastore = ml.datastores.get("workspaceworkingdirectory")
    files = sample_files(sample_config)
    with ShareServiceClient(
        f"https://{datastore.account_name}.file.core.windows.net",
        credential=AzureCliCredential(process_timeout=600),
        token_intent="backup",
    ) as service:
        share = service.get_share_client(datastore.file_share_name)
        for directory in ("Users", "Users/kt-demo", FOLDER, f"{FOLDER}/src", f"{FOLDER}/src/demo"):
            try:
                share.get_directory_client(directory).create_directory()
            except ResourceExistsError:
                LOGGER.info("Using existing sample directory: %s", directory)
        verified = {}
        for name, content in files.items():
            target = share.get_file_client(f"{FOLDER}/{name}")
            target.upload_file(content)
            downloaded = target.download_file().readall()
            if downloaded != content:
                raise RuntimeError(
                    f"Notebook share verification failed: {ml.workspace_name}/{name}"
                )
            verified[name] = hashlib.sha256(downloaded).hexdigest()
    proof = {
        "workspace": ml.workspace_name,
        "compute_instance": f"ci-kt-team{team}",
        "folder": FOLDER,
        "share": datastore.file_share_name,
        "files_sha256": verified,
        "verified_utc": datetime.now(UTC).isoformat(),
    }
    evidence = ROOT / "local" / ml.workspace_name / "notebook-files.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    LOGGER.info("Published and read back %s files in %s.", len(files), ml.workspace_name)
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(publish_team, team_configs(args.subscription)))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
