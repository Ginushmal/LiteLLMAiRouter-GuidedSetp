"""Tests for the provider key-fallback fetch helper."""

from types import SimpleNamespace

import httpx
import pytest

from model_pipeline.models import Credential
from model_pipeline.providers.base import ProviderAdapter


class _Resp:
    def __init__(self, status: int):
        self.status_code = status
        self.text = f"status {status}"
        self.headers = {"content-type": "application/json"}
        self.request = httpx.Request("GET", "https://provider.example/models")


class _Http:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append(headers)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _Recorder:
    def __init__(self):
        self.records = []

    def record(self, rec, body=""):
        self.records.append(rec)


class _Adapter(ProviderAdapter):
    name = "ours"

    def __init__(self, outcomes):
        self.pcfg = SimpleNamespace(api_key_env="", api_keys_env="TEST_APIS")
        self.http = _Http(outcomes)
        self.recorder = _Recorder()
        self.credentials = [
            Credential(1, "key-a", "TEST_APIS", raw=True),
            Credential(2, "key-b", "TEST_APIS", raw=True),
            Credential(3, "key-c", "TEST_APIS", raw=True),
        ]

    def fetch_models(self):  # pragma: no cover
        return []

    def fetch_pricing(self):  # pragma: no cover
        return {}

    def to_litellm_deployment(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


def test_falls_back_on_auth_payment_authorization_timeout_conflict_rate_limit_and_5xx():
    for status in (401, 402, 403, 408, 409, 429, 500, 503):
        adapter = _Adapter([_Resp(status), _Resp(200)])
        assert adapter.fetch_with_key_fallback("https://provider.example/models").status_code == 200
        assert len(adapter.http.calls) == 2
        assert "key-a" not in str(adapter.recorder.records)
        assert "key-b" not in str(adapter.recorder.records)


def test_falls_back_on_transport_errors():
    adapter = _Adapter([httpx.ConnectError("boom"), _Resp(200)])
    assert adapter.fetch_with_key_fallback("https://provider.example/models").status_code == 200


def test_does_not_fall_back_on_400_or_404():
    for status in (400, 404):
        adapter = _Adapter([_Resp(status), _Resp(200)])
        with pytest.raises(httpx.HTTPStatusError):
            adapter.fetch_with_key_fallback("https://provider.example/models")
        assert len(adapter.http.calls) == 1


def test_all_keys_fail_with_slot_fingerprints_and_no_raw_keys():
    adapter = _Adapter([_Resp(401), _Resp(429), _Resp(500)])
    with pytest.raises(RuntimeError) as exc:
        adapter.fetch_with_key_fallback("https://provider.example/models")

    message = str(exc.value)
    assert "all 3" in message
    assert "slot 1" in message and "slot 2" in message and "slot 3" in message
    for secret in ("key-a", "key-b", "key-c"):
        assert secret not in message


def test_no_credentials_fails_loudly():
    adapter = _Adapter([])
    adapter.credentials = []
    with pytest.raises(RuntimeError, match="no API keys"):
        adapter.fetch_with_key_fallback("https://provider.example/models")
