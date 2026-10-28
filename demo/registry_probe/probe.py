"""Run inside each team compute identity; never use the operator's Azure credentials."""

import argparse
import json
import os
from pathlib import Path

import mlflow.pyfunc
import pandas as pd
import requests
from azure.identity import ManagedIdentityCredential


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--team", required=True)
    parser.add_argument("--own-blob", required=True)
    parser.add_argument("--peer-blob", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    model = mlflow.pyfunc.load_model(str(args.model))
    sample = pd.DataFrame(
        {
            "tenure_months": [12, 48, 3],
            "monthly_charges": [70.0, 40.0, 120.0],
            "support_calls": [2, 0, 5],
            "network_issues": [1, 0, 4],
            "contract_months": [12, 24, 1],
        }
    )
    predictions = model.predict(sample).tolist()
    if len(predictions) != 3 or not set(predictions) <= {0, 1}:
        raise AssertionError(f"Unexpected real-model predictions: {predictions}")
    credential = ManagedIdentityCredential(client_id=os.environ.get("DEFAULT_IDENTITY_CLIENT_ID"))
    token = credential.get_token("https://storage.azure.com/.default")
    headers = {"Authorization": f"Bearer {token.token}", "x-ms-version": "2023-11-03"}
    own = requests.get(args.own_blob, headers=headers, timeout=60)
    own.raise_for_status()
    if own.text != args.team:
        raise AssertionError("Own Storage marker does not match the team.")
    peer = requests.get(args.peer_blob, headers=headers, timeout=60)
    if peer.status_code != 403 or peer.headers.get("x-ms-error-code") != (
        "AuthorizationPermissionMismatch"
    ):
        raise AssertionError(
            f"Expected peer RBAC denial, got {peer.status_code}: "
            f"{peer.headers.get('x-ms-error-code')}"
        )
    report = {
        "team": args.team,
        "predictions": predictions,
        "own_blob_status": own.status_code,
        "peer_blob_status": peer.status_code,
        "peer_error": peer.headers["x-ms-error-code"],
        "identity": "compute-managed-identity",
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
