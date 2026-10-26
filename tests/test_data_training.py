"""Contract tests for synthetic data and reproducible MLflow packaging."""

from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import pytest

from demo.data import FEATURES, generate_data, prepare
from demo.training import train


def test_synthetic_data_is_reproducible_and_contains_no_identifiers():
    first = generate_data(1200, 42)
    pd.testing.assert_frame_equal(first, generate_data(1200, 42))
    assert list(first.columns) == [*FEATURES, "churn"]
    assert set(first.churn.unique()) == {0, 1}
    assert first.isna().sum().sum() == 0
    assert 0.1 < first.churn.mean() < 0.8
    assert not first.equals(generate_data(1200, 43))


@pytest.mark.parametrize("rows", [0, -1, 1, 9])
def test_reject_too_few_rows(rows):
    with pytest.raises(ValueError):
        generate_data(rows, 42)


@pytest.mark.parametrize("algorithm", ["logistic", "forest"])
def test_training_roundtrip_and_holdout_metrics(tmp_path: Path, algorithm: str):
    raw = tmp_path / "raw.csv"
    generate_data(1500, 42).to_csv(raw, index=False)
    split_dir = tmp_path / "split"
    prepare(raw, split_dir)
    training = pd.read_csv(split_dir / "train.csv")
    test = pd.read_csv(split_dir / "test.csv")
    assert len(training) + len(test) == 1500
    mlflow.set_tracking_uri((tmp_path / "tracking").as_uri())
    mlflow.set_experiment(f"unit-{algorithm}")
    result = train(split_dir, tmp_path / "model", algorithm, data_version="1")
    assert result["roc_auc"] >= 0.65
    assert (tmp_path / "model" / "MLmodel").exists()
    restored = mlflow.pyfunc.load_model(str(tmp_path / "model"))
    predictions = restored.predict(test[FEATURES].head(3))
    assert len(predictions) == 3
    assert set(np.asarray(predictions)) <= {0, 1}


def test_invalid_training_schema_fails(tmp_path: Path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"churn": [0, 1]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="columns"):
        prepare(path, tmp_path / "out")
