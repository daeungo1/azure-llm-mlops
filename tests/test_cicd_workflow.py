import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-cpu-cicd.yml"


def load_workflow():
    assert WORKFLOW.is_file(), "The HF CPU CI/CD example workflow is missing"
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_workflow_requires_manual_opt_in_for_azure():
    workflow = load_workflow()
    assert set(workflow["on"]) == {"workflow_dispatch"}
    deploy = workflow["on"]["workflow_dispatch"]["inputs"]["deploy_azure"]
    assert deploy["type"] == "boolean"
    assert deploy["default"] == "false"
    assert workflow["concurrency"]["cancel-in-progress"] == "false"


def test_ci_runs_without_azure_authentication():
    workflow = load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    ci = workflow["jobs"]["ci"]
    assert ci["runs-on"] == "ubuntu-latest"
    commands = "\n".join(step.get("run", "") for step in ci["steps"])
    assert "uv sync --locked --extra serving --python 3.11" in commands
    assert "ruff check ." in commands
    assert "ruff format --check ." in commands
    assert "pytest -q" in commands
    assert not any(step.get("uses", "").startswith("azure/login@") for step in ci["steps"])


def test_cd_requires_ci_main_oidc_and_private_runner():
    deploy = load_workflow()["jobs"]["deploy"]
    assert deploy["needs"] == "ci"
    assert "github.ref == 'refs/heads/main'" in deploy["if"]
    assert "inputs.deploy_azure" in deploy["if"]
    assert deploy["environment"] == "azureml-demo"
    assert deploy["permissions"] == {"contents": "read", "id-token": "write"}
    assert set(deploy["runs-on"]) == {"self-hosted", "linux", "x64", "azureml-team-1"}
    assert all("runner." not in value for value in deploy["env"].values())
    prerequisites = next(
        step["run"]
        for step in deploy["steps"]
        if step.get("name") == "Check deployment prerequisites"
    )
    assert "AZURE_CONFIG_DIR=$RUNNER_TEMP/azureml-demo-az" in prerequisites
    assert '>> "$GITHUB_ENV"' in prerequisites
    login = next(
        step for step in deploy["steps"] if step.get("uses", "").startswith("azure/login@")
    )
    assert login["with"] == {
        "client-id": "${{ env.AZURE_CLIENT_ID }}",
        "tenant-id": "${{ env.AZURE_TENANT_ID }}",
        "subscription-id": "${{ env.AZURE_SUBSCRIPTION_ID }}",
    }


def test_cd_reuses_team_deployment_and_verification(monkeypatch, capsys):
    import demo.multiteam

    calls = []

    def serve_team(config, *, deploy_endpoint):
        calls.append((config, deploy_endpoint))
        return {"endpoint": "kt-hf-cpu-team-1", "request_statuses": [200, 200, 200]}

    monkeypatch.setattr(demo.multiteam, "serve_team", serve_team)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription")
    deploy = load_workflow()["jobs"]["deploy"]
    command = next(step["run"] for step in deploy["steps"] if step.get("id") == "deploy")
    script = command.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    exec(compile(script, str(WORKFLOW), "exec"), {})
    assert calls == [
        (
            {
                "subscription_id": "test-subscription",
                "resource_group": "rg-kt-mlops-team-1",
                "workspace_name": "mlw-ktmlops-secure-1",
            },
            True,
        )
    ]
    assert json.loads(capsys.readouterr().out)["request_statuses"] == [200, 200, 200]


def test_cd_publishes_only_verification_evidence_and_does_not_ignore_failures():
    workflow = load_workflow()
    for job in workflow["jobs"].values():
        assert job.get("continue-on-error", "false") == "false"
        for step in job["steps"]:
            assert step.get("continue-on-error", "false") == "false"
    upload = next(
        step
        for step in workflow["jobs"]["deploy"]["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload["with"]["path"] == "local/mlw-ktmlops-secure-1/online-verification.json"
    assert upload["with"]["if-no-files-found"] == "error"
