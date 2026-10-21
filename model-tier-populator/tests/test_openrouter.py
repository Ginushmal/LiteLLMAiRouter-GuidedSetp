"""Tests for the OpenRouter adapter (catalog parsing, eligibility, schedules).

The catalog fixture mirrors real 2026-10-21 entries: per-token price strings,
per-model overrides (Tencent-style daily windows, DeepSeek-style weekday
windows), `:free` variants, `:batch` variants, and the `openrouter/free` router.
"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from model_pipeline.config import PricingPolicy, ProviderConfig
from model_pipeline.http import ScrapeRecorder
from model_pipeline.providers.openrouter import OpenRouterAdapter

TEXT = {"output_modalities": ["text"]}

WEEKEND = ["saturday", "sunday"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

CATALOG = {
    "data": [
        {
            "id": "acme/alpha-1",
            "name": "Acme: Alpha 1",
            "context_length": 200000,
            "architecture": TEXT,
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000002",
                "input_cache_read": "0.0000001",
                "input_cache_write": "0.0000002",
            },
        },
        {
            "id": "acme/alpha-1:free",
            "name": "Acme: Alpha 1 (free)",
            "context_length": 200000,
            "architecture": TEXT,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "acme/alpha-1:batch",
            "name": "Acme: Alpha 1 (batch)",
            "context_length": 200000,
            "architecture": TEXT,
            "pricing": {"prompt": "0.0000005", "completion": "0.000001"},
        },
        {
            "id": "openrouter/free",
            "name": "Free Models Router",
            "context_length": 200000,
            "architecture": TEXT,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "tencent/hy3",
            "name": "Tencent: HY3",
            "context_length": 262144,
            "architecture": TEXT,
            "pricing": {
                "prompt": "0.0000000825",
                "completion": "0.00000033",
                "input_cache_read": "0.000000020625",
                "overrides": [
                    {
                        "utc_start": 0,
                        "utc_end": 1600,
                        "prompt": "0.000000132",
                        "completion": "0.000000528",
                        "input_cache_read": "0.000000033",
                    },
                    {
                        "utc_start": 1600,
                        "utc_end": 0,
                        "prompt": "0.0000000825",
                        "completion": "0.00000033",
                        "input_cache_read": "0.000000020625",
                    },
                ],
            },
        },
        {
            "id": "deepseek/flash-1",
            "name": "DeepSeek: Flash 1",
            "context_length": 128000,
            "architecture": TEXT,
            "pricing": {
                "prompt": "0.00000015",
                "completion": "0.0000006",
                "input_cache_read": "0.000000003",
                "overrides": [
                    {
                        "utc_days": WEEKEND,
                        "prompt": "0.00000015",
                        "completion": "0.0000006",
                        "input_cache_read": "0.000000003",
                    },
                    {
                        "utc_days": WEEKDAYS,
                        "utc_start": 0,
                        "utc_end": 100,
                        "prompt": "0.00000015",
                        "completion": "0.0000006",
                        "input_cache_read": "0.000000003",
                    },
                    {
                        "utc_days": WEEKDAYS,
                        "utc_start": 100,
                        "utc_end": 400,
                        "prompt": "0.0000003",
                        "completion": "0.0000012",
                        "input_cache_read": "0.000000006",
                    },
                    {
                        "utc_days": WEEKDAYS,
                        "utc_start": 400,
                        "utc_end": 600,
                        "prompt": "0.00000015",
                        "completion": "0.0000006",
                        "input_cache_read": "0.000000003",
                    },
                    {
                        "utc_days": WEEKDAYS,
                        "utc_start": 600,
                        "utc_end": 1000,
                        "prompt": "0.0000003",
                        "completion": "0.0000012",
                        "input_cache_read": "0.000000006",
                    },
                    {
                        "utc_days": WEEKDAYS,
                        "utc_start": 1000,
                        "utc_end": 0,
                        "prompt": "0.00000015",
                        "completion": "0.0000006",
                        "input_cache_read": "0.000000003",
                    },
                ],
            },
        },
        {
            "id": "acme/ctx-tier",
            "name": "Acme: Context Tier",
            "context_length": 400000,
            "architecture": TEXT,
            "pricing": {
                "prompt": "0.0000001",
                "completion": "0.000001",
                "overrides": [
                    {
                        "min_prompt_tokens": 100000,
                        "prompt": "0.0000005",
                        "completion": "0.000002",
                    }
                ],
            },
        },
    ]
}


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = json.dumps(payload)
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeHttp:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, headers=None):
        return _FakeResponse(self.payload)


def _adapter(tmp_path, mode="today", as_of=None, catalog=None):
    pcfg = ProviderConfig(
        name="openrouter",
        enabled=True,
        api_base="https://openrouter.ai/api/v1",
        models_url="https://openrouter.ai/api/v1/models",
        api_key_env="OPEN_ROUTER_API_KEY",
        pricing_url="",
        litellm={"chat_completions_api_base": "https://openrouter.ai/api/v1"},
        supported_endpoints=["chat"],
        models_dev_provider_ids=["openrouter"],
    )
    cfg = SimpleNamespace(
        providers={"openrouter": pcfg},
        pricing=PricingPolicy(
            context_tier_policy="average",
            active_window_utc=("02:30", "12:30"),
            active_days=[0, 1, 2, 3, 4],
            peak_windows_utc=[("01:00", "04:00"), ("06:00", "10:00")],
            time_price_mode=mode,
            as_of=as_of,
        ),
        secret=lambda name: "test-key",
    )
    http = _FakeHttp(CATALOG if catalog is None else catalog)
    recorder = ScrapeRecorder(tmp_path / "raw", tmp_path / "logs")
    return OpenRouterAdapter(cfg, http, recorder)


def _priced(tmp_path, mode="today", as_of=None, catalog=None):
    adapter = _adapter(tmp_path, mode, as_of, catalog)
    return {m.model_id: m for m in adapter.fetch_all()}


def _utc(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


# -- catalog + eligibility ------------------------------------------------
def test_fetch_models_excludes_batch_and_keeps_free(tmp_path):
    models = {m.model_id: m for m in _adapter(tmp_path).fetch_models()}

    assert "acme/alpha-1:batch" not in models
    assert "acme/alpha-1:free" in models
    # `openrouter/free` is chat-servable; dropping it is config's call.
    assert "openrouter/free" in models
    assert models["acme/alpha-1"].context_tokens == 200000
    assert models["acme/alpha-1"].endpoint_type == "chat"


def test_free_variant_keeps_zero_prices_and_paid_sibling_its_own(tmp_path):
    models = _priced(tmp_path)

    free = models["acme/alpha-1:free"]
    assert (free.pricing.input, free.pricing.output) == (0.0, 0.0)
    assert "free model" in free.pricing.normalization

    # The free id must not inherit the paid price (both normalize identically
    # except for the suffix).
    assert models["acme/alpha-1"].pricing.input == 1.0
    assert models["acme/alpha-1"].pricing.output == 2.0


def test_per_token_strings_become_dollars_per_million(tmp_path):
    paid = _priced(tmp_path)["acme/alpha-1"]
    assert paid.pricing.input == 1.0
    assert paid.pricing.output == 2.0
    assert paid.pricing.cache_read == pytest.approx(0.1)
    assert paid.pricing.cache_write == pytest.approx(0.2)
    assert paid.pricing.provenance["input"] == "provider"


def test_batch_entries_never_reach_pricing(tmp_path):
    assert "acme/alpha-1:batch" not in _adapter(tmp_path).fetch_pricing()


# -- schedules ------------------------------------------------------------
def test_daily_windows_use_the_models_own_bands_in_all_modes(tmp_path):
    # 10:00 Wednesday is inside tencent's 00:00-16:00 band.
    pricing = _priced(tmp_path, "instant", _utc(21, 10))["tencent/hy3"].pricing
    assert pricing.input == pytest.approx(0.132)

    # 20:00 is in the 16:00-00:00 band, which equals the base price.
    pricing = _priced(tmp_path, "instant", _utc(21, 20))["tencent/hy3"].pricing
    assert pricing.input == pytest.approx(0.0825)

    # `today` weights the whole 02:30-12:30 window, which is entirely peak.
    pricing = _priced(tmp_path, "today", _utc(21, 20))["tencent/hy3"].pricing
    assert pricing.input == pytest.approx(0.132)

    # `average` over Mon-Fri is the same, because the bands cover every day.
    pricing = _priced(tmp_path, "average", _utc(21, 20))["tencent/hy3"].pricing
    assert pricing.input == pytest.approx(0.132)


def test_weekday_and_weekend_schedules(tmp_path):
    saturday_noon = _utc(24, 12)
    wednesday_morning = _utc(21, 9)

    # Weekday-only peak bands -> plain off-peak on Saturday.
    pricing = _priced(tmp_path, "today", saturday_noon)["deepseek/flash-1"].pricing
    assert pricing.input == pytest.approx(0.15)

    # Wednesday's active window is 5.5 peak hours out of 10.
    pricing = _priced(tmp_path, "today", wednesday_morning)["deepseek/flash-1"].pricing
    assert pricing.input == pytest.approx(0.2325)

    # `instant` is the exact billable rate.
    pricing = _priced(tmp_path, "instant", wednesday_morning)["deepseek/flash-1"].pricing
    assert pricing.input == pytest.approx(0.30)
    pricing = _priced(tmp_path, "instant", _utc(21, 18))["deepseek/flash-1"].pricing
    assert pricing.input == pytest.approx(0.15)

    # `average` ignores the run date: same weighted week.
    pricing = _priced(tmp_path, "average", saturday_noon)["deepseek/flash-1"].pricing
    assert pricing.input == pytest.approx(0.2325)


def test_schedule_metadata_records_the_mode_and_instant(tmp_path):
    pricing = _priced(tmp_path, "today", _utc(24, 12))["deepseek/flash-1"].pricing
    note = pricing.normalization[0]
    assert "time=today" in note
    assert "as_of=2026-10-24T12:00Z" in note


def test_context_threshold_tiers_collapse_with_the_policy(tmp_path):
    pricing = _priced(tmp_path, "today", _utc(21, 9))["acme/ctx-tier"].pricing
    # Base 0.10 and >=100k-token 0.50 -> average 0.30.
    assert pricing.input == pytest.approx(0.30)
    assert pricing.output == pytest.approx((1.0 + 2.0) / 2)
    assert "context=average" in pricing.normalization[0]


def test_malformed_schedule_fails_loudly(tmp_path):
    broken = {
        "data": [
            {
                "id": "acme/broken",
                "name": "Acme: Broken",
                "context_length": 1000,
                "architecture": TEXT,
                "pricing": {
                    "prompt": "0.000001",
                    "completion": "0.000001",
                    "overrides": [{"utc_days": ["someday"], "prompt": "0.000002"}],
                },
            }
        ]
    }
    with pytest.raises(ValueError, match="openrouter pricing"):
        _adapter(tmp_path, catalog=broken).fetch_all()


# -- deployment payload ---------------------------------------------------
def test_deployment_payload_matches_the_openai_seam(tmp_path):
    adapter = _adapter(tmp_path)
    model = {m.model_id: m for m in adapter.fetch_all()}["acme/alpha-1"]

    payload = adapter.to_litellm_deployment(model, model.pricing, "pro-tier", 2)
    params = payload["litellm_params"]

    assert payload["model_name"] == "pro-tier"
    assert params["model"] == "openai/acme/alpha-1"
    assert params["api_base"] == "https://openrouter.ai/api/v1"
    assert params["api_key"] == "os.environ/OPEN_ROUTER_API_KEY"
    assert params["order"] == 2
    assert params["input_cost_per_token"] == pytest.approx(1e-6)
    assert params["output_cost_per_token"] == pytest.approx(2e-6)
    assert params["cache_read_input_token_cost"] == pytest.approx(1e-7)
    assert params["cache_creation_input_token_cost"] == pytest.approx(2e-7)
    assert payload["model_info"]["id"] == "mp::pro-tier::openrouter::acme-alpha-1"
    assert payload["model_info"]["provider"] == "openrouter"
