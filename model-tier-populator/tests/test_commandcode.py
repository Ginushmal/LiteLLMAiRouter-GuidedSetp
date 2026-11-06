"""Tests for the CommandCode adapter: subscription-plan gating + pricing join.

The Provider API advertises every model the gateway can serve, including the
premium ones a GOAT plan cannot use (e.g. GPT-6.1 Terra needs Pro). The models
page publishes the gate as a per-model ``minPlanName``; these tests cover
reading it, enforcing it, and refusing to guess when it is missing.
"""

import json
from types import SimpleNamespace

import pytest

from model_pipeline.config import ProviderConfig
from model_pipeline.http import ScrapeRecorder
from model_pipeline.providers.commandcode import (
    CommandCodeAdapter,
    parse_commandcode_plans,
)

API = "https://api.commandcode.ai/provider/v1/models"
PRICING = "https://commandcode.ai/models"

CATALOG = [
    {
        "id": "deepseek/deepseek-v4.1-flash",
        "name": "DeepSeek V4.1 Flash",
        "context_length": 1000000,
        "supported_endpoints": ["/chat/completions"],
    },
    {
        "id": "gpt-6.1-terra",
        "name": "GPT-6.1 Terra",
        "context_length": 1100000,
        "supported_endpoints": ["/chat/completions", "/messages"],
    },
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "context_length": 1000000,
        "supported_endpoints": ["/chat/completions"],
    },
    {
        # Real catalog/API mismatch: the API id is not the catalog slug.
        "id": "tencent/hy3-paid",
        "name": "Tencent Hy3",
        "context_length": 262144,
        "supported_endpoints": ["/chat/completions"],
    },
]

# name, catalog slug, minimum plan
CATALOG_PLANS = [
    ("DeepSeek V4.1 Flash", "deepseek-v4-1-flash", "Go"),
    ("GPT-6.1 Terra", "gpt-6-1-terra", "Pro"),
    ("Claude Opus 5", "claude-opus-5", "Max"),
    ("Tencent Hy3", "hy3-paid", "Go"),
]


def _stream_page(records):
    """Build a models-page-like HTML carrying a React Router stream payload."""
    strings = []
    for record in records:
        for key, value in record.items():
            for item in (key, str(value)):
                if item not in strings:
                    strings.append(item)

    def index(value):
        return strings.index(str(value))

    table = strings + [{f"_{index(k)}": index(v) for k, v in r.items()} for r in records]
    # The page enqueues a JS string literal whose content is the JSON payload.
    literal = json.dumps(json.dumps(table))
    return (
        "<script>window.__reactRouterContext.streamController"
        f".enqueue({literal});</script>"
    )


def _pricing_table(rows):
    body = "".join(
        f'<tr><td><a href="/models/{slug}">{name}</a></td>'
        "<td>1M</td><td>40.0</td><td>$1.00</td><td>$5.00</td>"
        "<td>$0.05</td><td>$1.25</td><td>+1</td></tr>"
        for name, slug in rows
    )
    return f"<table><tbody>{body}</tbody></table>"


def _page(plans=None, pricing=None):
    plans = CATALOG_PLANS if plans is None else plans
    pricing = [(name, slug) for name, slug, _ in CATALOG_PLANS] if pricing is None else pricing
    return _stream_page(
        [{"slug": slug, "name": name, "minPlanName": plan} for name, slug, plan in plans]
    ) + _pricing_table(pricing)


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text
        self.headers = {"content-type": "text/html"}

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        return None


class _FakeHttp:
    def __init__(self, by_url):
        self.by_url = by_url

    def get(self, url, headers=None):
        return _Response(self.by_url[url])


def _adapter(tmp_path, plan="GOAT", page=None, catalog=None, endpoints=("chat", "messages")):
    pcfg = ProviderConfig(
        name="commandcode",
        enabled=True,
        api_base="https://api.commandcode.ai/provider/v1",
        models_url=API,
        api_key_env="COMMANDCODE_API_KEY",
        pricing_url=PRICING,
        litellm={
            "openai_api_base": "https://api.commandcode.ai/provider/v1",
            "messages_api_base": "https://api.commandcode.ai/provider",
        },
        supported_endpoints=list(endpoints),
        plan=plan,
    )
    cfg = SimpleNamespace(providers={"commandcode": pcfg}, secret=lambda name: "test-key")
    http = _FakeHttp(
        {
            API: json.dumps({"data": CATALOG if catalog is None else catalog}),
            PRICING: _page() if page is None else page,
        }
    )
    recorder = ScrapeRecorder(tmp_path / "raw", tmp_path / "logs")
    return CommandCodeAdapter(cfg, http, recorder)


# -- plan data ------------------------------------------------------------
def test_plan_parser_maps_names_and_slugs_to_min_plan():
    plans = parse_commandcode_plans(_page())

    assert plans["gpt61terra"] == "Pro"  # display name
    assert plans["deepseekv41flash"] == "Go"
    assert plans["claudeopus5"] == "Max"
    # Slug-only key: the API's id is `tencent/hy3-paid`, the catalog slug is
    # `hy3-paid`, and the display name normalizes to something else entirely.
    assert plans["hy3paid"] == "Go"


def test_plan_parser_fails_loudly_when_the_page_stops_publishing_it():
    with pytest.raises(ValueError, match="no stream payload"):
        parse_commandcode_plans("<html><body>nothing</body></html>")

    # A payload that decodes but carries no per-model plan data is a schema
    # change too: silence would let premium models through.
    with pytest.raises(ValueError, match="plan data"):
        parse_commandcode_plans(_stream_page([{"slug": "x", "name": "X"}]))


def test_duplicate_normalized_names_keep_the_stricter_plan():
    page = _stream_page(
        [
            {"slug": "acme-1", "name": "Acme 1", "minPlanName": "Go"},
            {"slug": "acme-1-pro", "name": "Acme 1", "minPlanName": "Pro"},
        ]
    )

    assert parse_commandcode_plans(page)["acme1"] == "Pro"


# -- enforcement ----------------------------------------------------------
def test_goat_plan_drops_models_that_need_a_higher_plan(tmp_path):
    adapter = _adapter(tmp_path, plan="GOAT")
    models = {m.model_id: m for m in adapter.fetch_all()}

    assert set(models) == {"deepseek/deepseek-v4.1-flash", "tencent/hy3-paid"}
    assert ("gpt-6.1-terra", "Pro") in adapter.plan_excluded
    assert ("claude-opus-5", "Max") in adapter.plan_excluded
    assert adapter.plan_unverified == []


def test_plan_all_keeps_every_servable_model(tmp_path):
    models = {m.model_id: m for m in _adapter(tmp_path, plan="all").fetch_all()}

    assert set(models) == {m["id"] for m in CATALOG}


def test_unknown_plan_name_is_a_config_error(tmp_path):
    with pytest.raises(ValueError, match="plan must be one of"):
        _adapter(tmp_path, plan="PLATINUM")


def test_model_without_plan_data_is_dropped_not_assumed(tmp_path):
    # Priced and protocol-servable, but the plan data does not mention it.
    page = _page(plans=[p for p in CATALOG_PLANS if p[0] != "Claude Opus 5"])
    adapter = _adapter(tmp_path, plan="GOAT", page=page)
    models = {m.model_id: m for m in adapter.fetch_all()}

    assert "claude-opus-5" not in models
    assert adapter.plan_unverified == ["claude-opus-5"]


def test_unsupported_endpoint_still_excluded_before_the_plan_check(tmp_path):
    # `/messages`-only model while the provider config serves chat only.
    catalog = [
        {
            "id": "claude-opus-5",
            "name": "Claude Opus 5",
            "context_length": 1000000,
            "supported_endpoints": ["/messages"],
        }
    ]
    adapter = _adapter(tmp_path, plan="all", catalog=catalog, endpoints=["chat"])

    assert adapter.fetch_all() == []
    # Filtered by protocol, so it never reaches the plan bookkeeping.
    assert adapter.plan_excluded == []
    assert adapter.plan_unverified == []


def test_unknown_published_plan_name_is_dropped_not_guessed(tmp_path):
    catalog = [CATALOG[0]]  # DeepSeek V4.1 Flash
    page = _page(
        plans=[("DeepSeek V4.1 Flash", "deepseek-v4-1-flash", "Ultra")],
        pricing=[("DeepSeek V4.1 Flash", "deepseek-v4-1-flash")],
    )
    adapter = _adapter(tmp_path, plan="MAX", page=page, catalog=catalog)

    assert adapter.fetch_all() == []
    assert adapter.plan_unverified == ["deepseek/deepseek-v4.1-flash"]


def test_fetch_reports_plan_exclusions(capsys, tmp_path):
    from model_pipeline.cli import _print_plan_warnings

    adapter = _adapter(tmp_path, plan="GOAT")
    adapter.fetch_all()
    _print_plan_warnings(adapter)

    out = capsys.readouterr().out
    assert "2 model(s) need a higher commandcode plan than GOAT" in out
    assert "gpt-6.1-terra (needs Pro)" in out
    assert "claude-opus-5 (needs Max)" in out


def test_deployments_carry_the_openai_or_anthropic_seam(tmp_path):
    adapter = _adapter(tmp_path, plan="Pro")
    models = {m.model_id: m for m in adapter.fetch_all()}

    terra = models["gpt-6.1-terra"]
    payload = adapter.to_litellm_deployment(terra, terra.pricing, "pro-tier", 1)
    assert payload["litellm_params"]["model"].startswith("anthropic/")
    assert payload["litellm_params"]["api_key"] == "os.environ/COMMANDCODE_API_KEY"
