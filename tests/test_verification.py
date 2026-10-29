"""Live verification requires recorded cloud training evidence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from demo import endpoint


def test_verification_rejects_missing_pipeline_evidence(monkeypatch):
    monkeypatch.setattr(endpoint, "read_state", lambda: {})
    with pytest.raises(AssertionError, match="pipeline"):
        endpoint.verify(Mock())


@pytest.mark.parametrize("bad_index", [0, 1, 2, None])
def test_online_verification_checks_every_response_without_main_state(monkeypatch, bad_index):
    ml = Mock(subscription_id="sub", resource_group_name="team-rg", workspace_name="team-ws")
    ml.online_endpoints.get.return_value = SimpleNamespace(
        provisioning_state="Succeeded",
        auth_mode="aad_token",
        traffic={"blue": 100},
        scoring_uri="https://example.test/score",
    )
    ml.online_deployments.get.return_value.provisioning_state = "Succeeded"
    credential = Mock()
    credential.get_token.return_value.token = "test-token"
    monkeypatch.setattr(endpoint, "AzureCliCredential", Mock(return_value=credential))
    state = Mock(side_effect=AssertionError("Must not read main state"))
    monkeypatch.setattr(endpoint, "read_state", state)
    responses = []
    for index in range(3):
        body = {
            "model": endpoint.HF_MODEL,
            "embedding_dimension": 384,
            "predictions": [{"intent": name} for name in ["billing", "network", "cancellation"]],
        }
        if index == bad_index:
            body["embedding_dimension"] = 1
        responses.append(Mock(status_code=200, json=Mock(return_value=body)))
    responses += [Mock(status_code=401), Mock(status_code=424)]
    post = Mock(side_effect=responses)
    monkeypatch.setattr(endpoint.requests, "post", post)
    if bad_index is not None:
        with pytest.raises(AssertionError, match="output"):
            endpoint.verify_online(ml, "team-endpoint")
    else:
        report = endpoint.verify_online(ml, "team-endpoint")
        assert report["endpoint"] == "team-endpoint"
        assert report["workspace"] == "team-ws"
        assert len(report["request_seconds"]) == 3
        assert report["anonymous_status"] == 401
        assert report["invalid_input_status"] == 424
        assert post.call_count == 5
    state.assert_not_called()


def test_team_deployment_does_not_overwrite_main_state(monkeypatch):
    ml = Mock(subscription_id="sub", workspace_name="team-ws")
    monkeypatch.setattr(endpoint, "snapshot_download", Mock())
    monkeypatch.setattr(endpoint, "grant_role", Mock())
    state = Mock()
    monkeypatch.setattr(endpoint, "save_state", state)
    endpoint.deploy(ml, endpoint_name="kt-hf-cpu-team-1", record_main_state=False)
    state.assert_not_called()
    created = ml.online_endpoints.begin_create_or_update.call_args_list[0].args[0]
    assert created.name == "kt-hf-cpu-team-1"
    assert created.auth_mode == "aad_token"
    deployment = ml.online_deployments.begin_create_or_update.call_args.args[0]
    assert deployment.endpoint_name == created.name
    assert deployment.instance_count == 1
