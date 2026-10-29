"""Notebook samples must reuse existing training code and target the correct team."""

import ast
import importlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_public_notebook_configs_preserve_groups_and_select_supported_workspaces():
    setup = importlib.import_module("demo.notebook_setup")
    private = setup.notebook_configs("test-subscription")
    public = setup.notebook_configs("test-subscription", public_workspaces=True)
    assert [item["resource_group"] for item in public] == [
        item["resource_group"] for item in private
    ]
    assert [item["workspace_name"] for item in public] == [
        f"mlw-ktmlops-public-{number}" for number in range(1, 4)
    ]
    assert [item["compute_instance"] for item in public] == [
        f"ci-kt-public{number}" for number in range(1, 4)
    ]
    assert all(item["subscription_id"] == "test-subscription" for item in public)
    assert all(item["notebook_folder"] == f"{setup.FOLDER}-public" for item in public)


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


def test_notebook_connect_uses_open_sample_folder_when_private_sample_also_exists(
    monkeypatch, tmp_path
):
    private = tmp_path / "cloudfiles" / "code" / "Users" / "kt-demo" / "kt-mlops-training"
    private.mkdir(parents=True)
    (private / "config.json").write_text('{"workspace_name": "private"}', encoding="utf-8")
    public = tmp_path / "kt-mlops-training-public"
    public.mkdir()
    (public / "config.json").write_text('{"workspace_name": "public"}', encoding="utf-8")
    monkeypatch.chdir(public)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    connect = next(cell for cell in notebook["cells"] if cell["id"] == "connect")
    statements = []
    for node in ast.parse("".join(connect["source"])).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "config" for target in node.targets
        ):
            break
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            statements.append(node)
    scope = {"Path": Path}
    exec(compile(ast.Module(body=statements, type_ignores=[]), "sample-path", "exec"), scope)
    assert scope["sample"] == public


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


def test_metrics_reads_train_child_run_directly_without_waiting_for_search_index():
    notebook = json.loads(
        (ROOT / "notebooks" / "01_submit_training.ipynb").read_text(encoding="utf-8")
    )
    metrics = next(cell for cell in notebook["cells"] if cell["id"] == "metrics")
    reads = []
    run = SimpleNamespace(
        info=SimpleNamespace(run_id="train-id"),
        data=SimpleNamespace(
            params={"algorithm": "forest"},
            metrics={"accuracy": 0.73, "f1": 0.55, "roc_auc": 0.78},
        ),
    )

    def get_run(run_id):
        reads.append(run_id)
        return run

    scope = {
        "json": json,
        "jobs": [SimpleNamespace(name="parent-id")],
        "mlflow": SimpleNamespace(
            set_tracking_uri=lambda uri: None,
            MlflowClient=lambda: SimpleNamespace(get_run=get_run),
        ),
        "ml": SimpleNamespace(
            workspace_name="public-workspace",
            workspaces=SimpleNamespace(
                get=lambda name: SimpleNamespace(mlflow_tracking_uri="tracking-uri")
            ),
            jobs=SimpleNamespace(
                list=lambda **kwargs: [
                    SimpleNamespace(name="prepare-id", display_name="prepared"),
                    SimpleNamespace(name="train-id", display_name="trained"),
                ]
            ),
        ),
    }
    exec("".join(metrics["source"]), scope)
    assert reads == ["train-id"]
    assert scope["results"][0]["train_run"] == "train-id"
    assert scope["results"][0]["roc_auc"] == 0.78


@pytest.mark.parametrize("compute_name", [None, "ci-kt-public2"])
@pytest.mark.parametrize("corrupted", [False, True])
def test_publisher_verifies_share_bytes_and_creates_local_evidence(
    monkeypatch, tmp_path, corrupted, compute_name
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
    if compute_name:
        config["compute_instance"] = compute_name
        config["notebook_folder"] = f"{setup.FOLDER}-public"
    evidence = tmp_path / "local" / "mlw-ktmlops-secure-2" / "notebook-files.json"
    if corrupted:
        with pytest.raises(RuntimeError, match="verification failed"):
            setup.publish_team(config)
        assert not evidence.exists()
    else:
        proof = setup.publish_team(config)
        assert proof["compute_instance"] == (compute_name or "ci-kt-team2")
        assert proof["folder"] == config.get("notebook_folder", setup.FOLDER)
        assert proof["files_sha256"]["sample.ipynb"]
        assert json.loads(evidence.read_text(encoding="utf-8")) == proof
    assert datastore_names == ["workspaceworkingdirectory"]
