"""Registry consumers must use the same immutable assets and isolated team scopes."""

import importlib
import json
import re
import shlex
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def module():
    return importlib.import_module("demo.multiteam")


def test_three_team_scopes_are_distinct():
    teams = module().team_configs("subscription")
    assert [item["workspace_name"] for item in teams] == [
        f"mlw-ktmlops-secure-{number}" for number in range(1, 4)
    ]
    assert len({item["resource_group"] for item in teams}) == 3
    assert all(item["subscription_id"] == "subscription" for item in teams)


def test_team_foundation_receives_disabled_managed_network_mode():
    template = (Path(__file__).parents[1] / "infra" / "teams.bicep").read_text(encoding="utf-8")
    group, foundation = template.split("module foundations ", 1)
    assert "managedNetworkMode: 'Disabled'" in foundation
    assert "managedNetworkMode: 'Disabled'" not in group


def test_private_compute_network_includes_workspace_private_endpoint():
    template = (Path(__file__).parents[1] / "infra" / "team-network.bicep").read_text(
        encoding="utf-8"
    )
    assert "groupId: 'amlworkspace'" in template
    assert "resourceId: workspaceId" in template
    assert "'privatelink.api.azureml.ms'" in template
    assert "'privatelink.notebooks.azure.net'" in template


def test_peer_blob_rbac_probe_can_resolve_public_names_without_private_records():
    template = (Path(__file__).parents[1] / "infra" / "team-network.bicep").read_text(
        encoding="utf-8"
    )
    assert (
        "resolutionPolicy: name == 'privatelink.blob.core.windows.net' "
        "? 'NxDomainRedirect' : 'Default'" in template
    )


def test_shared_component_references_registry_model_and_team_identity():
    shared = module()
    job = shared.consumer_job("mlr-test", "1", "team-2", "/own/storage", "/peer/storage")
    node = job.jobs["consume"]
    assert (
        node.inputs["model"].path == "azureml://registries/mlr-test/models/telco-shared/versions/1"
    )
    assert node.component == (
        "azureml://registries/mlr-test/components/verify_shared_model/versions/3"
    )
    assert node.identity.type == "managed_identity"
    assert node.compute == "cpu-secure"
    assert job.tags["team"] == "team-2"
    assert job.outputs["report"].type == "uri_folder"
    assert job._to_dict()["jobs"]["consume"]["outputs"]["report"] == "${{parent.outputs.report}}"


def test_cost_report_keeps_empty_actual_cost_distinct_from_zero():
    shared = module()
    empty = shared.cost_rows({"properties": {"columns": [], "rows": []}})
    assert empty == []
    actual = shared.cost_rows(
        {
            "properties": {
                "columns": [
                    {"name": "Cost"},
                    {"name": "ResourceGroupName"},
                    {"name": "Currency"},
                ],
                "rows": [[1.25, "rg-kt-mlops-team-1", "USD"]],
            }
        }
    )
    assert actual == [{"Cost": 1.25, "ResourceGroupName": "rg-kt-mlops-team-1", "Currency": "USD"}]


@pytest.mark.parametrize("peer_status", [403, 200])
def test_collect_consumer_report_requires_actual_child_proof(tmp_path, monkeypatch, peer_status):
    shared = module()
    monkeypatch.setattr(shared, "ROOT", tmp_path)
    ml = Mock()
    ml.workspace_name = "workspace"
    ml.jobs.list.return_value = [SimpleNamespace(name="child", status="Completed")]
    proof = {
        "team": "team-1",
        "predictions": [1, 0, 1],
        "own_blob_status": 200,
        "peer_blob_status": peer_status,
        "peer_error": "AuthorizationPermissionMismatch",
        "identity": "compute-managed-identity",
    }
    log = tmp_path / "local" / "workspace" / "parent" / "artifacts" / "user_logs" / "std_log.txt"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(proof), encoding="utf-8")
    if peer_status == 200:
        with pytest.raises(AssertionError, match="verification"):
            shared.collect_consumer_report(ml, "parent", "team-1")
    else:
        assert shared.collect_consumer_report(ml, "parent", "team-1") == proof
        ml.jobs.download.assert_called_once_with(
            "child", download_path=str(tmp_path / "local" / "workspace" / "parent"), all=True
        )
        assert json.loads((log.parents[2] / "verification.json").read_text()) == proof


def test_collect_consumer_report_rejects_silently_skipped_download(tmp_path, monkeypatch):
    shared = module()
    monkeypatch.setattr(shared, "ROOT", tmp_path)
    ml = Mock()
    ml.workspace_name = "workspace"
    ml.jobs.list.return_value = [SimpleNamespace(name="child", status="Completed")]
    with pytest.raises(FileNotFoundError):
        shared.collect_consumer_report(ml, "parent", "team-1")


def test_cost_report_rejects_malformed_rows():
    with pytest.raises(ValueError, match="columns"):
        module().cost_rows({"properties": {"columns": [{"name": "Cost"}], "rows": [[1.0, "USD"]]}})


def test_consumer_probe_is_packaged_without_repository_or_customer_files():
    source = Path(__file__).parents[1] / "demo" / "registry_probe"
    assert source.is_dir(), "The registry component requires an isolated code folder."
    assert (source / "probe.py").is_file()


def test_workspace_client_maps_config_resource_group(monkeypatch):
    shared = module()
    constructor = Mock()
    monkeypatch.setattr(shared, "MLClient", constructor)
    shared.workspace_client(shared.team_configs("sub")[1])
    assert constructor.call_args.args[1:] == ("sub", "rg-kt-mlops-team-2", "mlw-ktmlops-secure-2")


def test_management_throttle_retries_using_server_delay(monkeypatch):
    shared = module()
    credential = Mock()
    credential.get_token.return_value.token = "test-token"
    monkeypatch.setattr(shared, "AzureCliCredential", Mock(return_value=credential))
    limited = Mock(status_code=429, headers={"Retry-After": "2"})
    success = Mock(status_code=200)
    request = Mock(side_effect=[limited, success])
    delay = Mock()
    monkeypatch.setattr(shared.requests, "request", request)
    monkeypatch.setattr(shared.time, "sleep", delay, raising=False)
    assert (
        shared.authorized_request(
            "GET",
            "https://management.azure.com/test",
            audience="https://management.azure.com/.default",
        )
        is success
    )
    delay.assert_called_once_with(2)
    assert request.call_count == 2


def test_costs_collects_every_page_and_common_backing_group(tmp_path, monkeypatch):
    shared = module()
    report = tmp_path / "multiteam.json"
    report.write_text(json.dumps({"registry_managed_group": "registry-backing"}))
    monkeypatch.setattr(shared, "REPORT", report)
    columns = [{"name": "Cost"}, {"name": "ResourceGroupName"}, {"name": "Currency"}]
    pages = [
        {
            "properties": {
                "columns": columns,
                "rows": [[1, "rg-kt-mlops", "USD"]],
                "nextLink": "https://management.azure.com/next",
            }
        },
        {"properties": {"columns": columns, "rows": [[2, "registry-backing", "USD"]]}},
    ]
    request = Mock(side_effect=[Mock(json=Mock(return_value=page)) for page in pages])
    monkeypatch.setattr(shared, "authorized_request", request)
    shared.costs("sub")
    saved = json.loads(report.read_text())
    assert [row["Cost"] for row in saved["actual_cost"]] == [1, 2]
    assert saved["cost_next_link"] is None
    assert request.call_args_list[1].args == ("POST", "https://management.azure.com/next")
    assert (
        "registry-backing"
        in (request.call_args_list[0].kwargs["json"]["dataset"]["filter"]["dimensions"]["values"])
    )


def test_publish_resumes_recorded_shares_without_uploading_code(tmp_path, monkeypatch):
    shared = module()
    reference = "azureml://registries/mlr-test"
    report = tmp_path / "multiteam.json"
    report.write_text(
        json.dumps(
            {
                "model": f"{reference}/models/telco-shared/versions/1",
                "environment": f"{reference}/environments/kt-shared-cpu/versions/1",
            }
        )
    )
    monkeypatch.setattr(shared, "REPORT", report)
    source, registry = Mock(), Mock()
    registry.models.get.return_value.id = f"{reference}/models/telco-shared/versions/1"
    registry.environments.get.return_value.id = f"{reference}/environments/kt-shared-cpu/versions/1"
    registry.components.create_or_update.return_value.id = (
        f"{reference}/components/verify_shared_model/versions/3"
    )
    monkeypatch.setattr(shared, "MLClient", Mock(side_effect=[source, registry]))
    shared.publish("sub", "mlr-test")
    source.models.share.assert_not_called()
    source.environments.share.assert_not_called()
    component = registry.components.create_or_update.call_args.args[0]
    assert component.code is None
    assert "\n" not in component.command, (
        "AML command normalization must not alter Python indentation."
    )
    embedded = shlex.split(re.sub(r" {2,}", " ", component.command))
    assert embedded[:2] == ["python", "-c"]
    captured = []
    exec(embedded[2], {"exec": captured.append})
    source_code = captured[0]
    if isinstance(source_code, bytes):
        source_code = source_code.decode("utf-8")
    assert source_code == (shared.ROOT / "demo" / "registry_probe" / "probe.py").read_text(
        encoding="utf-8"
    )
    compile(source_code, "<registry-probe>", "exec")


def test_prepare_uses_private_team_subnet_without_managed_network_approval(monkeypatch):
    shared = module()
    client = Mock()
    client.subscription_id = "sub"
    client.resource_group_name = "rg-team"
    client.workspace_name = "mlw-ktmlops-secure-1"
    operations = Mock(
        spec=type(shared.MLClient(Mock(), "sub", "rg-team", client.workspace_name).workspaces)
    )
    client.workspaces = operations
    workspace = SimpleNamespace(
        identity=SimpleNamespace(principal_id="workspace-identity"),
        managed_network=SimpleNamespace(isolation_mode="disabled"),
        storage_account="/team/storage/account",
    )
    operations.get.return_value = workspace
    monkeypatch.setattr(shared, "workspace_client", Mock(return_value=client))
    monkeypatch.setattr(shared, "grant_role", Mock())
    monkeypatch.setattr(shared, "AzureCliCredential", Mock())
    monkeypatch.setattr(shared.requests, "put", Mock(return_value=Mock(status_code=201)))
    config = shared.team_configs("sub")[0]
    shared.prepare_team(config, "/registry")
    operations.begin_update.assert_not_called()
    operations.begin_provision_network.assert_not_called()
    compute = client.compute.begin_create_or_update.call_args.args[0]
    assert compute.enable_node_public_ip is False
    assert compute.network_settings.subnet == config["compute_subnet"]
    assert compute.min_instances == 0
    assert compute.max_instances == 1
    assert shared.grant_role.call_args_list[0].args[:3] == (
        "/subscriptions/sub/resourceGroups/rg-team",
        "workspace-identity",
        shared.READER,
    )
