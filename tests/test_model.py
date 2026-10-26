"""Optional real-model smoke tests. Set HF_MODEL_DIR to the downloaded snapshot."""

import json
import os

import pytest

from demo.serving import score


@pytest.mark.model
@pytest.mark.skipif(
    not os.environ.get("HF_MODEL_DIR"), reason="Set HF_MODEL_DIR for real CPU tests."
)
def test_real_cpu_model_routes_three_tickets(monkeypatch):
    monkeypatch.setenv("AZUREML_MODEL_DIR", os.environ["HF_MODEL_DIR"])
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    score.init()
    result = score.run(
        json.dumps(
            {
                "texts": [
                    "My invoice includes unexpected charges and I need a refund.",
                    "My mobile internet is very slow and calls keep dropping.",
                    "Please cancel my subscription and close my account.",
                ]
            }
        )
    )
    assert result["embedding_dimension"] == 384
    assert [p["intent"] for p in result["predictions"]] == ["billing", "network", "cancellation"]


def test_bad_input_returns_client_error():
    result = score.run('{"texts":[]}')
    assert result.status_code == 400
