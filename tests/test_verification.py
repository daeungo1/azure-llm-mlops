"""Live verification requires recorded cloud training evidence."""

from unittest.mock import Mock

import pytest

from demo import endpoint


def test_verification_rejects_missing_pipeline_evidence(monkeypatch):
    monkeypatch.setattr(endpoint, "read_state", lambda: {})
    with pytest.raises(AssertionError, match="pipeline"):
        endpoint.verify(Mock())
