"""Workspace connection, scoped identity permissions and persisted demo state."""

import json
import logging
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import requests
from azure.ai.ml import MLClient
from azure.ai.ml.entities import AmlCompute, IdentityConfiguration
from azure.identity import AzureCliCredential

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "local" / "state.json"
COMPUTE = "cpu-demo"
ENDPOINT = "kt-hf-cpu"


def client(config_path: Path) -> MLClient:
    return MLClient.from_config(
        credential=AzureCliCredential(process_timeout=120), path=str(config_path)
    )


def read_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(**updates) -> dict:
    state = read_state()
    state.update(updates)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def grant_role(scope: str, principal_id: str, role_id: str, subscription_id: str) -> None:
    assignment = uuid5(NAMESPACE_URL, f"{scope}:{principal_id}:{role_id}")
    token = (
        AzureCliCredential(process_timeout=120)
        .get_token("https://management.azure.com/.default")
        .token
    )
    response = requests.put(
        f"https://management.azure.com{scope}/providers/Microsoft.Authorization/"
        f"roleAssignments/{assignment}?api-version=2022-04-01",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "properties": {
                "principalId": principal_id,
                "principalType": "ServicePrincipal",
                "roleDefinitionId": f"/subscriptions/{subscription_id}/providers/"
                f"Microsoft.Authorization/roleDefinitions/{role_id}",
            }
        },
        timeout=60,
    )
    response.raise_for_status()
    LOGGER.info("Assigned scoped role %s to principal %s.", role_id, principal_id)


def create_compute(ml: MLClient) -> None:
    compute = ml.compute.begin_create_or_update(
        AmlCompute(
            name=COMPUTE,
            size="Standard_DS3_v2",
            min_instances=0,
            max_instances=2,
            idle_time_before_scale_down=120,
            ssh_public_access_enabled=False,
            identity=IdentityConfiguration(type="SystemAssigned"),
            description="CPU-only training; automatically scales to zero after two idle minutes.",
        )
    ).result()
    workspace = ml.workspaces.get(ml.workspace_name)
    grant_role(
        workspace.storage_account,
        compute.identity.principal_id,
        "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
        ml.subscription_id,
    )
    save_state(compute=compute.name)
