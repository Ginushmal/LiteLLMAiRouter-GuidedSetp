"""Tests for the CommandCode adapter: pricing parsing + subscription-plan gating.

The Provider API advertises every model the gateway can serve, including the
premium ones a GOAT plan cannot use (e.g. GPT-6.1 Terra needs Pro). The models
page publishes the gate as a per-model ``minPlanName``; these tests cover
reading it, enforcing it, and refusing to guess when it is missing.

The page's column set is not stable: it published ``Model | Context |
Intelligence | Input | Output | Cache read | Cache write | Caps`` until
November 2026, then dropped the Intelligence column and every price shifted one
slot left under a positional parser. Prices are therefore located by header
text, and a table that stops publishing a required price header fails loudly.
"""

import json
from types import SimpleNamespace

import pytest

from model_pipeline.config import ProviderConfig
from model_pipeline.http import ScrapeRecorder
from model_pipeline.providers.commandcode import (
    CommandCodeAdapter,
    parse_commandcode_pricing,
    parse_commandcode_plans,
    pricing_column_map,
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


# Header texts as published by the live page, including the sort glyph.
_HEADERS = [
    "Model ↕",
    "Context ↕",
    "Input ↕",
    "Output ↕",
    "Cache read ↕",
    "Cache write ↕",
    "Caps",
]
_CELL_VALUES = {
    "context": "1M",
    "intelligence": "40.0",
    "input": "$1.00",
    "output": "$5.00",
    "cache read": "$0.05",
    "cache write": "$1.25",
    "caps": "+1",
}


def _header_key(header):
    words = header.split()
    return " ".join(words[:2]).lower() if header.lower().startswith("cache ") else words[0].lower()


def _pricing_table(rows, headers=None, values=None):
    """Build a models-page pricing table; columns found by header, not position."""
    headers = _HEADERS if headers is None else headers
    cells_by_header = dict(_CELL_VALUES)
    cells_by_header.update(values or {})
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for name, slug in rows:
        cells = [f'<a href="/models/{slug}">{name}</a>']
        cells += [cells_by_header.get(_header_key(h), "-") for h in headers[1:]]
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


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


# -- pricing column mapping ----------------------------------------------
# The page dropped this column in November 2026; prices must not shift with it.
CURRENT_HEADERS = ["Model \u2195", "Context \u2195", "Input \u2195", "Output \u2195",
                   "Cache read \u2195", "Cache write \u2195", "Caps"]
HISTORICAL_HEADERS = ["Model \u2195", "Context \u2195", "Intelligence \u2195", "Input \u2195",
                      "Output \u2195", "Cache read \u2195", "Cache write \u2195", "Caps"]
REORDERED_HEADERS = ["Model \u2195", "Cache write \u2195", "Output \u2195", "Cache read \u2195",
                     "Caps", "Input \u2195", "Context \u2195"]


def test_columns_are_read_from_the_current_header_row():
    columns = pricing_column_map([f"<th>{h}</th>" for h in CURRENT_HEADERS])

    assert columns == {
        "model": 0,
        "input": 2,
        "output": 3,
        "cache_read": 4,
        "cache_write": 5,
    }


def test_columns_follow_the_header_when_intelligence_is_present():
    columns = pricing_column_map([f"<th>{h}</th>" for h in HISTORICAL_HEADERS])

    assert columns["input"] == 3
    assert columns["output"] == 4
    assert columns["cache_read"] == 5
    assert columns["cache_write"] == 6


@pytest.mark.parametrize(
    "headers, missing",
    [
        (["Model \u2195", "Context \u2195", "Input \u2195", "Output \u2195", "Cache write \u2195"],
         "Cache read"),
        (["Model \u2195", "Context \u2195", "Input \u2195", "Cache read \u2195", "Cache write \u2195"],
         "Output"),
    ],
)
def test_missing_price_header_fails_loudly(headers, missing):
    with pytest.raises(ValueError, match=f"{missing}.*schema change"):
        pricing_column_map([f"<th>{h}</th>" for h in headers])


def test_renamed_price_headers_fail_loudly():
    headers = ["Model", "Context", "Cost in", "Cost out", "Cached", "Cache write"]
    with pytest.raises(ValueError, match="Input, Output, Cache read"):
        pricing_column_map([f"<th>{h}</th>" for h in headers])


def test_headerless_table_fails_loudly(tmp_path):
    # A data row parsed as the header row: no price header can be found.
    body = (
        '<tr><td><a href="/models/x">Acme 1</a></td><td>1M</td>'
        "<td>$1.00</td><td>$5.00</td><td>$0.05</td><td>$1.25</td><td>+1</td></tr>"
    )
    with pytest.raises(ValueError, match="schema change"):
        parse_commandcode_pricing(f"<table><tbody>{body}</tbody></table>")
    with pytest.raises(ValueError, match="schema change"):
        _adapter(tmp_path, plan="all", page=f"<table><tbody>{body}</tbody></table>").fetch_pricing()


def test_pricing_failure_is_recorded_in_the_scraping_log(tmp_path):
    adapter = _adapter(tmp_path, plan="all", page="<table><tbody></tbody></table>")

    with pytest.raises(ValueError, match="schema change"):
        adapter.fetch_pricing()

    logs = list((tmp_path / "logs" / "commandcode").glob("*.log"))
    assert logs, "the failed parse must be recorded"
    entries = [json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()]
    assert any("schema change" in e["error"] for e in entries)


@pytest.mark.parametrize("headers", [CURRENT_HEADERS, HISTORICAL_HEADERS, REORDERED_HEADERS])
def test_every_layout_parses_the_same_prices(headers):
    html = _pricing_table([("Acme 1", "acme-1")], headers=headers)

    pricing = parse_commandcode_pricing(html)["acme1"]

    assert (pricing.input, pricing.output, pricing.cache_read, pricing.cache_write) == (
        1.00, 5.00, 0.05, 1.25,
    )


def test_incident_rows_parse_to_their_published_prices():
    """The 2026-11-18 run's exact rows (raw fetch 20261118T060042Z)."""
    html = (
        "<table><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in CURRENT_HEADERS)
        + "</tr></thead><tbody>"
        '<tr><td><a href="/models/qwen4-max">Qwen 4 Max</a></td>'
        "<td>1M</td><td>$1.50</td><td>$4.50</td><td>$0.075</td><td>$1.875</td><td>+ 1</td></tr>"
        '<tr><td><a href="/models/kimi-k31-pro">Kimi K3.1 Pro</a></td>'
        "<td>1M</td><td>$2.00</td><td>$10.00</td><td>$0.20</td><td>\u2014</td><td>+ 1</td></tr>"
        "</tbody></table>"
    )

    pricing = parse_commandcode_pricing(html)

    kimi = pricing["kimik31pro"]
    assert (kimi.input, kimi.output, kimi.cache_read, kimi.cache_write) == (2.00, 10.00, 0.20, None)
    qwen = pricing["qwen4max"]
    assert (qwen.input, qwen.output, qwen.cache_read, qwen.cache_write) == (1.50, 4.50, 0.075, 1.875)
    # Every parsed price is provider-published, never shifted into another field.
    assert qwen.provenance["input"] == "provider"


RAW_INCIDENT_PAGE = (
    __import__("pathlib").Path(__file__).resolve().parent.parent
    / "data/raw/commandcode/20261118T060042Z_https-commandcode-ai-models.html"
)


@pytest.mark.skipif(not RAW_INCIDENT_PAGE.exists(), reason="raw incident page not on disk")
def test_saved_incident_page_parses_correctly():
    pricing = parse_commandcode_pricing(RAW_INCIDENT_PAGE.read_text(encoding="utf-8"))

    assert pricing["kimik31pro"].input == 2.00
    assert pricing["kimik31pro"].output == 10.00
    assert pricing["qwen4max"].input == 1.50
    assert pricing["qwen4max"].output == 4.50
