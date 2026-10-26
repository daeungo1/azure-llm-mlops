"""Train the same MLflow-instrumented program locally, on AML, or on external compute."""

import argparse
import json
import logging
from pathlib import Path
from typing import Literal

import matplotlib
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from demo.data import FEATURES

matplotlib.use("Agg")
LOGGER = logging.getLogger(__name__)
Algorithm = Literal["logistic", "forest"]


def train(
    source: Path, destination: Path, algorithm: Algorithm, data_version: str
) -> dict[str, float]:
    if algorithm not in ("logistic", "forest"):
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    train_data = pd.read_csv(source / "train.csv")
    test_data = pd.read_csv(source / "test.csv")
    estimator = (
        make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=42))
        if algorithm == "logistic"
        else RandomForestClassifier(
            n_estimators=100, max_depth=6, min_samples_leaf=8, random_state=42, n_jobs=2
        )
    )
    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "algorithm": algorithm,
                "data_asset": "telco-churn",
                "data_version": data_version,
                "seed": 42,
                "holdout_fraction": 0.25,
                "train_rows": len(train_data),
                "test_rows": len(test_data),
            }
        )
        mlflow.set_tags({"scenario": "synthetic-telco-churn", "data_classification": "synthetic"})
        estimator.fit(train_data[FEATURES], train_data.churn)
        predicted = estimator.predict(test_data[FEATURES])
        probability = estimator.predict_proba(test_data[FEATURES])[:, 1]
        metrics = {
            "accuracy": float(accuracy_score(test_data.churn, predicted)),
            "f1": float(f1_score(test_data.churn, predicted)),
            "roc_auc": float(roc_auc_score(test_data.churn, probability)),
        }
        mlflow.log_metrics(metrics)
        display = ConfusionMatrixDisplay.from_predictions(test_data.churn, predicted)
        mlflow.log_figure(display.figure_, "evaluation/confusion_matrix.png")
        import matplotlib.pyplot as plt

        plt.close(display.figure_)
        example = train_data[FEATURES].head(3)
        signature = infer_signature(example, estimator.predict(example))
        mlflow.sklearn.log_model(
            estimator, artifact_path="model", signature=signature, input_example=example
        )
        mlflow.sklearn.save_model(
            estimator, path=str(destination), signature=signature, input_example=example
        )
        mlflow.log_dict(metrics, "evaluation/metrics.json")
        LOGGER.info("MLflow run %s: %s", run.info.run_id, json.dumps(metrics))
        return metrics


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--algorithm", choices=["logistic", "forest"], default="logistic")
    parser.add_argument("--data-version", default="1")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = create_parser().parse_args()
    train(args.source, args.destination, args.algorithm, args.data_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
