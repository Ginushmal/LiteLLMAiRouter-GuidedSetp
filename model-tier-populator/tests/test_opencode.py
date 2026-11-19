"""Tests for the OpenCode Go adapter and its live-catalog metadata."""

import json
from pathlib import Path
from types import SimpleNamespace

from model_pipeline.config import ProviderConfig
from model_pipeline.emit.snapshot import models_from_json, models_to_json
from model_pipeline.http import ScrapeRecorder
from model_pipeline.models import (
    ENDPOINT_CHAT,
    ENDPOINT_GOOGLE,
    ENDPOINT_MESSAGES,
    ENDPOINT_RESPONSES,
    ResolvedPricing,
)
from model_pipeline.providers.opencode import OpenCodeAdapter
from model_pipeline.textutil import normkey

FIXTURE = Path(__file__).parent / "fixtures" / "opencode_models.json"
MODELS = json.loads(FIXTURE.read_text(encoding="utf-8"))
MODEL_IDS = [m["id"] for m in MODELS]


class _Response:
    status_code = 200
    headers = {"content-type": "application/json"}

    def __init__(self, data):
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        return None


class _FakeHttp:
    def __init__(self, data):
        self.data = data

    def get(self, url, headers=None):
        return _Response(self.data)


def _adapter(tmp_path, supported=("chat", "messages")):
    pcfg = ProviderConfig(
        name="opencode",
        enabled=True,
        api_base="https://opencode.ai/inference/go/v1",
        models_url="https://opencode.ai/inference/go/v1/models",
        api_key_env="OPENCODE_API_KEY",
        pricing_url="https://opencode.ai/v2/docs/console/go",
        litellm={
            "chat_completions_api_base": "https://opencode.ai/inference/go/v1",
            "messages_api_base": "https://opencode.ai/inference/go",
        },
        supported_endpoints=list(supported),
        models_dev_provider_ids=["opencode-go", "opencode"],
    )
    cfg = SimpleNamespace(
        providers={"opencode": pcfg},
        pricing=SimpleNamespace(
            context_tier_policy="average",
            active_window_utc=("00:00", "24:00"),
            active_days=[0, 1, 2, 3, 4, 5, 6],
            peak_windows_utc=[],
            time_price_mode="average",
            as_of=None,
        ),
        secret=lambda name: "test-key",
    )
    http = _FakeHttp({"data": MODELS})
    recorder = ScrapeRecorder(tmp_path / "raw", tmp_path / "logs")
    return OpenCodeAdapter(cfg, http, recorder)


def _pricing(ids=None):
    return {
        normkey(mid): ResolvedPricing(input=1.0, output=2.0)
        for mid in (ids if ids is not None else MODEL_IDS)
    }


def _models_by_id(adapter):
    return {m.model_id: m for m in adapter.fetch_models()}


def test_fetch_models_reads_live_metadata(tmp_path):
    models = _models_by_id(_adapter(tmp_path))

    assert len(models) == 30
    deepseek = models["deepseek-v4.1-flash"]
    assert deepseek.display_name == "DeepSeek V4.1 Flash 1017"
    assert deepseek.canonical_hint == "deepseek/deepseek-v4.1-flash-1017"
    assert (deepseek.context_tokens, deepseek.output_tokens) == (1_000_000, 384_000)
    assert deepseek.native_protocol == ENDPOINT_CHAT
    assert deepseek.endpoint_type == ENDPOINT_CHAT

    # The docs-only MiMo 2.5 entries are deprecated and must not be synthesized.
    assert "mimo-v2.5" not in models
    assert "mimo-v2.5-pro" not in models


def test_fetch_models_maps_native_protocols_to_deployment(tmp_path):
    models = _models_by_id(_adapter(tmp_path))

    assert models["grok-4.7"].native_protocol == ENDPOINT_RESPONSES
    assert models["grok-4.7"].endpoint_type == ENDPOINT_CHAT

    assert models["gemini-4-argon"].native_protocol == ENDPOINT_GOOGLE
    assert models["gemini-4-argon"].endpoint_type == ENDPOINT_CHAT

    assert models["claude-haiku-5-5"].native_protocol == ENDPOINT_MESSAGES
    assert models["claude-haiku-5-5"].endpoint_type == ENDPOINT_MESSAGES

    assert models["glm-5.3"].native_protocol == ENDPOINT_CHAT
    assert models["glm-5.3"].endpoint_type == ENDPOINT_CHAT


def test_to_litellm_deployment_uses_chat_for_responses_and_native_messages(tmp_path):
    adapter = _adapter(tmp_path)
    models = _models_by_id(adapter)
    pricing = ResolvedPricing(input=1.0, output=2.0)

    chat = adapter.to_litellm_deployment(models["grok-4.7"], pricing, "pro-tier", 1)
    assert chat["litellm_params"]["model"] == "openai/grok-4.7"
    assert chat["litellm_params"]["api_base"] == "https://opencode.ai/inference/go/v1"

    messages = adapter.to_litellm_deployment(
        models["claude-haiku-5-5"], pricing, "pro-tier", 1
    )
    assert messages["litellm_params"]["model"] == "anthropic/claude-haiku-5-5"
    assert messages["litellm_params"]["api_base"] == "https://opencode.ai/inference/go"


def test_fetch_all_extracts_all_live_models_and_counts_census(tmp_path):
    adapter = _adapter(tmp_path)
    adapter.fetch_pricing = lambda: _pricing()

    models = adapter.fetch_all()
    census = adapter.last_census

    assert len(models) == 30
    assert census.provider == "opencode"
    assert (census.advertised, census.extracted) == (30, 30)
    assert census.unsupported_protocol == []
    assert census.no_pricing == []


def test_fetch_all_counts_models_without_pricing(tmp_path):
    adapter = _adapter(tmp_path)
    pricing = _pricing()
    pricing.pop(normkey("glm-5.2"))
    adapter.fetch_pricing = lambda: pricing

    models = adapter.fetch_all()

    assert "glm-5.2" not in {m.model_id for m in models}
    assert adapter.last_census.no_pricing == ["glm-5.2"]
    assert adapter.last_census.extracted == 29


def test_fetch_all_counts_unsupported_protocol(tmp_path):
    adapter = _adapter(tmp_path, supported=("messages",))
    adapter.fetch_pricing = lambda: _pricing()

    models = adapter.fetch_all()

    assert {m.model_id for m in models} == {
        "claude-haiku-5-5",
        "minimax-m3",
        "qwen3.8-max",
        "qwen3.8-flash",
        "qwen3.7-plus",
    }
    assert len(adapter.last_census.unsupported_protocol) == 25
    assert "grok-4.7" in adapter.last_census.unsupported_protocol


def test_snapshot_round_trip_keeps_native_protocol_and_hint(tmp_path):
    model = _models_by_id(_adapter(tmp_path))["deepseek-v4.1-flash"]

    restored = models_from_json(models_to_json([model]))[0]

    assert restored.native_protocol == ENDPOINT_CHAT
    assert restored.canonical_hint == "deepseek/deepseek-v4.1-flash-1017"
