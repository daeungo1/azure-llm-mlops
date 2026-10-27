"""Role assignment conflicts must be verified, not silently ignored."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from demo import workspace


@pytest.mark.parametrize("existing_principal", ["principal", "another-principal"])
def test_existing_role_is_verified(monkeypatch, existing_principal):
    credential = Mock()
    credential.get_token.return_value = SimpleNamespace(token="test-token")
    monkeypatch.setattr(workspace, "AzureCliCredential", Mock(return_value=credential))
    conflict = Mock(status_code=409)
    conflict.json.return_value = {"error": {"code": "RoleAssignmentExists"}}
    conflict.raise_for_status.side_effect = requests.HTTPError("conflict")
    monkeypatch.setattr(workspace.requests, "put", Mock(return_value=conflict))
    listing = Mock()
    listing.json.return_value = {
        "value": [
            {
                "properties": {
                    "principalId": existing_principal,
                    "roleDefinitionId": (
                        "/subscriptions/sub/providers/Microsoft.Authorization/roleDefinitions/role"
                    ),
                    "scope": "/scope",
                }
            }
        ]
    }
    monkeypatch.setattr(workspace.requests, "get", Mock(return_value=listing))
    if existing_principal == "principal":
        workspace.grant_role("/scope", "principal", "role", "sub")
    else:
        with pytest.raises(requests.HTTPError):
            workspace.grant_role("/scope", "principal", "role", "sub")
