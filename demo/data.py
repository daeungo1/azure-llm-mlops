"""Generate synthetic telco data and prepare a deterministic stratified holdout."""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

FEATURES = [
    "tenure_months",
    "monthly_charges",
    "support_calls",
    "network_issues",
    "contract_months",
]
LOGGER = logging.getLogger(__name__)


def generate_data(rows: int, seed: int, drift: bool = False) -> pd.DataFrame:
    if rows < 10:
        raise ValueError("At least 10 synthetic rows are required.")
    rng = np.random.default_rng(seed)
    data = pd.DataFrame(
        {
            "tenure_months": rng.integers(1, 73, rows),
            "monthly_charges": rng.uniform(25, 130, rows).round(2),
            "support_calls": rng.poisson(2.4 if drift else 1.5, rows),
            "network_issues": rng.poisson(1.8 if drift else 0.8, rows),
            "contract_months": rng.choice([1, 12, 24], rows, p=[0.5, 0.3, 0.2]),
        }
    )
    log_odds = (
        -2.3
        - 0.035 * data.tenure_months
        + 0.022 * data.monthly_charges
        + 0.65 * data.support_calls
        + 0.8 * data.network_issues
        - 0.055 * data.contract_months
    )
    data["churn"] = rng.binomial(1, 1 / (1 + np.exp(-log_odds)))
    return data


def prepare(source: Path, destination: Path) -> None:
    data = pd.read_csv(source)
    if set(data.columns) != {*FEATURES, "churn"}:
        raise ValueError(f"Expected columns {[*FEATURES, 'churn']}; got {list(data.columns)}.")
    if data.isna().any().any() or not set(data.churn.unique()) <= {0, 1}:
        raise ValueError("Training data must contain no nulls and a binary churn target.")
    train, test = train_test_split(data, test_size=0.25, stratify=data.churn, random_state=42)
    destination.mkdir(parents=True, exist_ok=True)
    train.to_csv(destination / "train.csv", index=False)
    test.to_csv(destination / "test.csv", index=False)
    LOGGER.info("Prepared %d train and %d test rows.", len(train), len(test))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = create_parser().parse_args()
    prepare(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
