"""Versioned data, environments, components, pipeline jobs and MLflow model assets."""

import json
import logging
from pathlib import Path

import mlflow
from azure.ai.ml import Input, MLClient, Output, command, dsl
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Data, Environment, ManagedIdentityConfiguration, Model

from demo.data import generate_data, prepare
from demo.training import train
from demo.workspace import COMPUTE, ROOT, save_state

LOGGER = logging.getLogger(__name__)
TRAIN_ENV = "kt-sklearn-mlflow"
TRAIN_VERSION = "2"
BASE_IMAGE = "mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest"


def register_assets(ml: MLClient) -> None:
    for version, rows, seed in [("1", 1500, 42), ("2", 1800, 43)]:
        folder = ROOT / "data" / "generated" / f"v{version}"
        folder.mkdir(parents=True, exist_ok=True)
        generate_data(rows, seed, drift=version == "2").to_csv(folder / "telco.csv", index=False)
        (folder / "MLTable").write_text(
            "paths:\n  - file: ./telco.csv\ntransformations:\n"
            "  - read_delimited:\n      delimiter: ','\n      encoding: utf8\n",
            encoding="utf-8",
        )
        tags = {"classification": "synthetic", "rows": str(rows), "seed": str(seed)}
        ml.data.create_or_update(
            Data(
                name="telco-churn",
                version=version,
                type=AssetTypes.URI_FILE,
                path=str(folder / "telco.csv"),
                description="Synthetic telco churn. No customer IDs or real customer information.",
                tags=tags,
            )
        )
        ml.data.create_or_update(
            Data(
                name="telco-churn-table",
                version=version,
                type=AssetTypes.MLTABLE,
                path=str(folder),
                description="Previewable MLTable over the synthetic telco CSV.",
                tags=tags,
            )
        )
    register_components(ml)
    save_state(data_versions=["1", "2"])


def register_components(ml: MLClient) -> None:
    env = ml.environments.create_or_update(
        Environment(
            name=TRAIN_ENV,
            version=TRAIN_VERSION,
            image=BASE_IMAGE,
            conda_file=str(ROOT / "environments" / "training.yml"),
            description="Python 3.11, sklearn 1.6.1 and MLflow 2.22.2 compatibility baseline.",
        )
    )
    prep = command(
        name="prepare_telco_data",
        version=TRAIN_VERSION,
        display_name="Prepare synthetic telco holdout",
        description="Schema validation and deterministic 75/25 stratified split.",
        code=str(ROOT),
        environment=env.id,
        inputs={"data": Input(type=AssetTypes.URI_FILE)},
        outputs={"prepared": Output(type=AssetTypes.URI_FOLDER)},
        command="python -m demo.data --source ${{inputs.data}} --destination ${{outputs.prepared}}",
    )
    training = command(
        name="train_telco_classifier",
        version=TRAIN_VERSION,
        display_name="Train and package an MLflow classifier",
        description="Logs metrics, signature, example input, confusion matrix and MLflow model.",
        code=str(ROOT),
        environment=env.id,
        inputs={
            "data": Input(type=AssetTypes.URI_FOLDER),
            "algorithm": Input(type="string", enum=["logistic", "forest"]),
            "data_version": Input(type="string"),
        },
        outputs={"model": Output(type=AssetTypes.MLFLOW_MODEL)},
        command="python -m demo.training --source ${{inputs.data}} "
        "--destination ${{outputs.model}} --algorithm ${{inputs.algorithm}} "
        "--data-version ${{inputs.data_version}}",
    )
    ml.components.create_or_update(prep.component)
    ml.components.create_or_update(training.component)
    save_state(training_environment=env.id)


def run_pipelines(ml: MLClient) -> None:
    prep = ml.components.get("prepare_telco_data", version=TRAIN_VERSION)
    training = ml.components.get("train_telco_classifier", version=TRAIN_VERSION)

    @dsl.pipeline(
        display_name="Telco reproducible training",
        description="Data asset -> prepare component -> MLflow training -> versioned model.",
        default_compute=COMPUTE,
    )
    def telco_pipeline(data, algorithm: str):
        prepared = prep(data=data)
        prepared.identity = ManagedIdentityConfiguration()
        trained = training(data=prepared.outputs.prepared, algorithm=algorithm, data_version="1")
        trained.identity = ManagedIdentityConfiguration()
        return {"model": trained.outputs.model}

    jobs = []
    for algorithm in ("logistic", "forest"):
        pipeline = telco_pipeline(
            data=Input(type=AssetTypes.URI_FILE, path="azureml:telco-churn:1"), algorithm=algorithm
        )
        pipeline.display_name = f"telco-{algorithm}-data-v1"
        pipeline.tags = {"scenario": "synthetic-telco", "algorithm": algorithm, "data_version": "1"}
        pipeline.settings.force_rerun = True
        job = ml.jobs.create_or_update(pipeline, experiment_name="kt-telco-churn")
        jobs.append({"name": job.name, "algorithm": algorithm, "studio_url": job.studio_url})
        save_state(pipeline_jobs=jobs)
    for version, job in enumerate(jobs, start=1):
        ml.jobs.stream(job["name"])
        completed = ml.jobs.get(job["name"])
        if completed.status != "Completed":
            raise RuntimeError(f"Pipeline {completed.name} ended with {completed.status}.")
        model = ml.models.create_or_update(
            Model(
                name="telco-churn-classifier",
                version=str(version),
                path=f"azureml://jobs/{completed.name}/outputs/model",
                type=AssetTypes.MLFLOW_MODEL,
                description=f"Synthetic telco {job['algorithm']}; identical v1 holdout.",
                tags={"algorithm": job["algorithm"], "data_version": "1", "data": "synthetic"},
            )
        )
        LOGGER.info("Registered %s:%s from %s.", model.name, model.version, completed.name)
    save_state(churn_model_versions=["1", "2"])


def external_tracking(ml: MLClient) -> None:
    workspace = ml.workspaces.get(ml.workspace_name)
    mlflow.set_tracking_uri(workspace.mlflow_tracking_uri)
    mlflow.set_experiment("kt-external-mlflow")
    from tempfile import TemporaryDirectory

    local = ROOT / "local"
    local.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="external-", dir=local) as workdir:
        folder = Path(workdir)
        source = ROOT / "data" / "generated" / "v2" / "telco.csv"
        if not source.exists():
            raise FileNotFoundError("Run the 'assets' command before external training.")
        prepare(source, folder / "prepared")
        metrics = train(folder / "prepared", folder / "model", "logistic", data_version="2")
        run = mlflow.last_active_run()
        mlflow.MlflowClient().set_tag(run.info.run_id, "execution_source", "external-local-cpu")
        registered = mlflow.register_model(f"runs:/{run.info.run_id}/model", "telco-churn-external")
        save_state(
            external_run_id=run.info.run_id,
            external_model_version=registered.version,
            external_metrics=metrics,
        )
        LOGGER.info("External run and model recorded: %s", json.dumps(metrics))
