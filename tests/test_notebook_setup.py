"""Notebook samples must reuse existing training code and target the correct team."""

import ast
import importlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_sample_uses_team_config_and_exact_existing_training_source():
    setup = importlib.import_module("demo.notebook_setup")
    config = {
        "subscription_id": "test-subscription",
        "resource_group": "rg-kt-mlops-team-2",
        "workspace_name": "mlw-ktmlops-secure-2",
    }
    files = setup.sample_files(config)
    assert json.loads(files["config.json"]) == config
    for name in ("__init__.py", "data.py", "training.py"):
        assert files[f"src/demo/{name}"] == (ROOT / "demo" / name).read_bytes()
    notebook = json.loads(files["01_submit_training.ipynb"])
    assert notebook["nbformat"] == 4
    source = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "kt-notebook-training" in source
    assert 'default_compute="cpu-secure"' in source
    assert "ManagedIdentityConfiguration()" in source
    assert "telco-churn-shared/versions/1" in source
    assert "kt-shared-cpu/versions/1" in source
    assert "enable_model_registration = False" in source
    connect = next(cell for cell in notebook["cells"] if cell["id"] == "connect")
    connection_code = ast.unparse(ast.parse("".join(connect["source"])))
    assert (
        "os.environ['AZURE_CLIENT_ID'] = config['notebook_identity_client_id']" in connection_code
    )
    assert "subscription_id" not in source


def test_notebook_code_cells_are_valid_python_and_have_no_saved_outputs():
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if not source.startswith("%pip"):
                ast.parse(source)
            assert cell["execution_count"] is None
            assert cell["outputs"] == []


def test_notebook_credential_allows_slow_azure_cli_token_requests():
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    connect = next(cell for cell in notebook["cells"] if cell["id"] == "connect")
    calls = [
        node
        for node in ast.walk(ast.parse("".join(connect["source"])))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "DefaultAzureCredential"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg: keyword.value for keyword in calls[0].keywords}
    assert "process_timeout" in keywords
    assert ast.literal_eval(keywords["process_timeout"]) == 600
    assert "managed_identity_client_id" in keywords


def test_notebook_connect_checks_workspace_authorization_before_reporting_success():
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    connect = next(cell for cell in notebook["cells"] if cell["id"] == "connect")
    source = "".join(connect["source"])
    tree = ast.parse(source)
    reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "ml.workspaces.get"
    ]
    prints = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "print"
    ]
    assert len(reads) == 1
    assert reads[0].lineno < prints[0].lineno


@pytest.mark.parametrize("final_status", ["Completed", "Failed", "Canceled", "NotResponding"])
def test_notebook_wait_uses_authenticated_status_reads(monkeypatch, final_status):
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    wait = next(cell for cell in notebook["cells"] if cell["id"] == "wait")
    statuses = iter(["Running", final_status])
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    scope = {
        "ml": SimpleNamespace(
            jobs=SimpleNamespace(get=lambda name: SimpleNamespace(status=next(statuses)))
        ),
        "jobs": [SimpleNamespace(name="test-job")],
    }
    if final_status == "Completed":
        exec("".join(wait["source"]), scope)
    else:
        with pytest.raises(RuntimeError, match=f"test-job: {final_status}"):
            exec("".join(wait["source"]), scope)
    assert sleeps == [15]


def test_notebook_wait_times_out_explicitly(monkeypatch):
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    wait = next(cell for cell in notebook["cells"] if cell["id"] == "wait")
    clock = iter([0, 1800])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    scope = {
        "ml": SimpleNamespace(
            jobs=SimpleNamespace(get=lambda name: SimpleNamespace(status="Running"))
        ),
        "jobs": [SimpleNamespace(name="test-job")],
    }
    with pytest.raises(TimeoutError, match="test-job"):
        exec("".join(wait["source"]), scope)


@pytest.mark.parametrize("corrupted", [False, True])
def test_publisher_verifies_share_bytes_and_creates_local_evidence(
    monkeypatch, tmp_path, corrupted
):
    setup = importlib.import_module("demo.notebook_setup")
    stored = {}
    datastore_names = []

    class File:
        def __init__(self, path):
            self.path = path

        def upload_file(self, content):
            stored[self.path] = content

        def download_file(self):
            content = stored[self.path] + (b"tampered" if corrupted else b"")
            return SimpleNamespace(readall=lambda: content)

    class Service:
        def __init__(self, *args, **kwargs):
            assert kwargs["token_intent"] == "backup"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_share_client(self, name):
            assert name == "notebook-share"
            return SimpleNamespace(
                get_directory_client=lambda path: SimpleNamespace(create_directory=lambda: None),
                get_file_client=File,
            )

    def datastore(name):
        datastore_names.append(name)
        return SimpleNamespace(account_name="storage", file_share_name="notebook-share")

    monkeypatch.setattr(setup, "ROOT", tmp_path)
    monkeypatch.setattr(setup, "ShareServiceClient", Service)
    monkeypatch.setattr(setup, "AzureCliCredential", lambda **kwargs: object())
    monkeypatch.setattr(setup, "sample_files", lambda config: {"sample.ipynb": b"notebook"})
    monkeypatch.setattr(
        setup,
        "authorized_request",
        lambda *args, **kwargs: SimpleNamespace(
            json=lambda: {"properties": {"clientId": "notebook-identity"}}
        ),
    )
    monkeypatch.setattr(
        setup,
        "workspace_client",
        lambda config: SimpleNamespace(
            workspace_name="mlw-ktmlops-secure-2", datastores=SimpleNamespace(get=datastore)
        ),
    )
    config = {
        "subscription_id": "test-subscription",
        "resource_group": "rg-kt-mlops-team-2",
        "workspace_name": "mlw-ktmlops-secure-2",
    }
    evidence = tmp_path / "local" / "mlw-ktmlops-secure-2" / "notebook-files.json"
    if corrupted:
        with pytest.raises(RuntimeError, match="verification failed"):
            setup.publish_team(config)
        assert not evidence.exists()
    else:
        proof = setup.publish_team(config)
        assert proof["files_sha256"]["sample.ipynb"]
        assert json.loads(evidence.read_text(encoding="utf-8")) == proof
    assert datastore_names == ["workspaceworkingdirectory"]
