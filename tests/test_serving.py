"""Validate endpoint input limits without downloading a model."""

import json

import pytest

from demo.serving.score import parse_request


def test_valid_batch():
    assert parse_request(json.dumps({"texts": ["My mobile data is slow"]})) == [
        "My mobile data is slow"
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"texts": []},
        {"texts": "hello"},
        {"texts": [12]},
        {"texts": [" "]},
        {"texts": ["x" * 2001]},
        {"texts": ["hi"] * 17},
        {"texts": ["hello"], "unexpected": True},
        [],
    ],
)
def test_bad_payload_is_explicitly_rejected(payload):
    with pytest.raises(ValueError):
        parse_request(json.dumps(payload))


def test_invalid_json():
    with pytest.raises(ValueError):
        parse_request("not json")
