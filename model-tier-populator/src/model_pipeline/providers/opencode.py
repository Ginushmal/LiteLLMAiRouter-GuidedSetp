"""OpenCode Go (opencode.ai/inference/go/v1) adapter.

The /models endpoint is the live catalog: each entry carries the display name,
canonical id, native API map, and token limits. The docs page supplies the
pricing table (Model | Input | Output | Cached Read | Cached Write).

Native protocols are metadata only. OpenCode's gateway translates every text
model to every API, so models whose native protocol is responses or Google
generateContent are deployed through chat/completions; messages-native models
keep the native Anthropic path.

Pricing rows encode tiers in the model name:
  * context tiers:  "Qwen3.7 Plus (\u2264 256K tokens)" + "(\u003e 256K tokens)"
  * peak/off-peak:  "DeepSeek V4.1 Flash (Off-Peak)" + "(Peak)"

Both are collapsed into one effective price (context = configured policy,
peak = the configured time price mode: today / average / instant).

OpenCode also requires an ``x-opencode-session`` header on every request; the
adapter injects a static one via ``extra_headers`` at deployment time.
"""

from __future__ import annotations

import re
from collections import defaultdict

from model_pipeline.models import (
    ENDPOINT_CHAT,
    ENDPOINT_GOOGLE,
    ENDPOINT_MESSAGES,
    ENDPOINT_RESPONSES,
    RawModel,
    ResolvedPricing,
)
from model_pipeline.pricing import normalize_context_tiers, weighted_price
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.textutil import clean_text, normkey, parse_money

_TABLE_RE = re.compile(r"<table.*?</table>", re.S)
_ROW_RE = re.compile(r"<tr.*?</tr>", re.S)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_SUFFIX_RE = re.compile(r"^(.*?)\s*\((.+)\)\s*$")


def _native_protocol(api: dict | None) -> str:
    """The protocol the provider advertises for a model, from its ``api`` map."""
    api = api or {}
    if "messages" in api:
        return ENDPOINT_MESSAGES
    if "responses" in api:
        return ENDPOINT_RESPONSES
    if "generate-content" in api:
        return ENDPOINT_GOOGLE
    return ENDPOINT_CHAT


def _deploy_endpoint(native: str) -> str:
    """The protocol used for the LiteLLM deployment.

    OpenCode's gateway translates every text model to every API, so only the
    native Anthropic path is kept; every other native protocol uses chat.
    """
    return ENDPOINT_MESSAGES if native == ENDPOINT_MESSAGES else ENDPOINT_CHAT


def _split_suffix(name: str) -> tuple[str, str]:
    m = _SUFFIX_RE.match(name.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return name.strip(), ""


class OpenCodeAdapter(ProviderAdapter):
    name = "opencode"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._docs_html: str | None = None

    def _docs(self) -> str:
        if self._docs_html is None:
            resp = self.http.get(self.pcfg.pricing_url)
            resp.raise_for_status()
            self._docs_html = resp.text
            self._record(self.pcfg.pricing_url, "GET", resp=resp, notes="docs page cached")
        return self._docs_html

    def fetch_models(self) -> list[RawModel]:
        resp = self.fetch_with_key_fallback(self.pcfg.models_url)
        try:
            data = resp.json()
        except Exception as exc:
            self._record(self.pcfg.models_url, "GET", resp=resp, error=str(exc))
            raise

        models: list[RawModel] = []
        for m in data.get("data", []):
            mid = m["id"]
            limit = m.get("limit") or {}
            native = _native_protocol(m.get("api"))
            models.append(
                RawModel(
                    provider=self.name,
                    model_id=mid,
                    display_name=m.get("name") or mid,
                    endpoint_type=_deploy_endpoint(native),
                    context_tokens=limit.get("context"),
                    output_tokens=limit.get("output"),
                    native_protocol=native,
                    canonical_hint=m.get("canonical_id") or "",
                )
            )
        self._record(self.pcfg.models_url, "GET", resp=resp, parsed_count=len(models))
        return models

    def fetch_pricing(self) -> dict[str, ResolvedPricing]:
        html = self._docs()
        pricing = parse_opencode_pricing(
            html,
            context_policy=self.cfg.pricing.context_tier_policy,
            active_window=self.cfg.pricing.active_window_utc,
            active_days=self.cfg.pricing.active_days,
            peak_windows=self.cfg.pricing.peak_windows_utc,
            time_price_mode=self.cfg.pricing.time_price_mode,
            as_of=self.cfg.pricing.as_of,
        )
        self._record(
            self.pcfg.pricing_url + "#pricing",
            "GET",
            parsed_count=len(pricing),
            notes="parsed from cached docs page",
        )
        return pricing

    def to_litellm_deployment(
        self,
        model: RawModel,
        pricing: ResolvedPricing,
        model_group: str,
        order: int,
        credential=None,
    ) -> dict:
        if model.endpoint_type == ENDPOINT_MESSAGES:
            prefix = "anthropic/"
            api_base = self.pcfg.litellm["messages_api_base"]
        else:
            prefix = "openai/"
            api_base = self.pcfg.litellm["chat_completions_api_base"]
        return self._assemble(
            model,
            pricing,
            model_group,
            order,
            f"{prefix}{model.model_id}",
            api_base,
            credential,
        )


def parse_opencode_pricing(
    html: str,
    context_policy: str,
    active_window: tuple[str, str],
    active_days: list[int],
    peak_windows: list[tuple[str, str]],
    time_price_mode: str = "average",
    as_of=None,
) -> dict[str, ResolvedPricing]:
    table = None
    for t in _TABLE_RE.findall(html or ""):
        if "Input" in t and "Monthly limit" in t:
            table = t
            break
    if table is None:
        return {}

    groups: dict[str, list[tuple[str, ResolvedPricing]]] = defaultdict(list)
    for row in _ROW_RE.finditer(table):
        cells = [clean_text(c) for c in _CELL_RE.findall(row.group(0))]
        if len(cells) < 5 or cells[0].lower() == "model":
            continue
        base, tag = _split_suffix(cells[0])
        price = ResolvedPricing(
            input=parse_money(cells[1]),
            output=parse_money(cells[2]),
            cache_read=parse_money(cells[3]),
            cache_write=parse_money(cells[4]),
        )
        groups[normkey(base)].append((tag, price))

    def collapse(peak_value, off_value):
        """Peak/off-peak at the configured evaluation mode (None stays None)."""
        if peak_value is None or off_value is None:
            return off_value
        return weighted_price(
            peak_value,
            off_value,
            peak_windows,
            active_window,
            active_days,
            mode=time_price_mode,
            as_of=as_of,
        )

    result: dict[str, ResolvedPricing] = {}
    for key, items in groups.items():
        tags = [t.lower() for t in (tag for tag, _ in items)]
        is_peak = any("peak" in t and "off" not in t for t in tags) and any(
            "off" in t for t in tags
        )
        is_context = not is_peak and any(("\u2264" in t or ">" in t or "token" in t) for t in tags)

        if is_peak:
            off = next(p for t, p in items if "off" in t.lower())
            peak = next(
                p for t, p in items if "peak" in t.lower() and "off" not in t.lower()
            )
            pr = ResolvedPricing(
                input=collapse(peak.input, off.input),
                output=collapse(peak.output, off.output),
                cache_read=collapse(peak.cache_read, off.cache_read),
                cache_write=off.cache_write,
            )
            pr.normalization.append(f"peak/off-peak collapsed (time={time_price_mode})")
        elif is_context:
            pr = ResolvedPricing(
                input=normalize_context_tiers([p.input for _, p in items], context_policy),
                output=normalize_context_tiers([p.output for _, p in items], context_policy),
                cache_read=normalize_context_tiers([p.cache_read for _, p in items], context_policy),
                cache_write=normalize_context_tiers([p.cache_write for _, p in items], context_policy),
            )
            pr.normalization.append(f"context tiers averaged ({context_policy})")
        else:
            src = items[0][1]
            pr = ResolvedPricing(
                input=src.input,
                output=src.output,
                cache_read=src.cache_read,
                cache_write=src.cache_write,
            )

        pr.provenance = {
            k: "provider"
            for k in ("input", "output", "cache_read", "cache_write")
            if getattr(pr, k) is not None
        }
        result[key] = pr
    return result
