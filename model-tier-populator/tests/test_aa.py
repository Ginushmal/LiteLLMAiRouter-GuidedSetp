"""Tests for the Artificial Analysis client's on-disk snapshot cache."""

from __future__ import annotations

import json

from model_pipeline.config import load_config
from model_pipeline.scoring.aa import AaClient


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict):
        self._payload = payload
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        return json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeHttp:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def get(self, url: str, headers: dict | None = None) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(self.payload)


class _NullRecorder:
    def record(self, rec, body: str = ""):
        return rec


def _client(tmp_path, payload: dict) -> tuple[AaClient, _FakeHttp]:
    cfg = load_config()
    # Point at a directory that does not exist, reproducing a fresh checkout
    # where output/ has been deleted.
    cfg.output_dir = tmp_path / "output"
    cfg.env = {cfg.aa.api_key_env: "test-key"}
    http = _FakeHttp(payload)
    return AaClient(cfg, http, _NullRecorder()), http


def test_fetch_raw_creates_missing_output_dir(tmp_path):
    rows = [{"slug": "model-a", "name": "Model A"}]
    client, _http = _client(tmp_path, {"data": rows, "pagination": {"has_more": False}})
    assert not (tmp_path / "output").exists()

    assert client.fetch_raw(use_cache=False) == rows

    cache = tmp_path / "output" / "aa_snapshot.json"
    assert json.loads(cache.read_text(encoding="utf-8")) == rows


def test_fetch_raw_reuses_existing_cache_without_calling_the_api(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    rows = [{"slug": "cached", "name": "Cached"}]
    (output_dir / "aa_snapshot.json").write_text(json.dumps(rows), encoding="utf-8")
    client, http = _client(tmp_path, {"data": [], "pagination": {"has_more": False}})

    assert client.fetch_raw() == rows
    assert http.calls == 0
