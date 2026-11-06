"""CommandCode (api.commandcode.ai/provider/v1) adapter.

Models come from the Provider API. Prices come from the HTML catalog at
commandcode.ai/models, whose rows look like:

    Model | Context | Intelligence | Input | Output | Cache read | Cache write | Caps

Price cells carry plan markers ("$0.10 + 1") and, for discounted models, a
strikethrough list price followed by the effective price ("$0.80 $0.14").
We keep the effective (last) dollar figure.

The same page also publishes each model's *minimum subscription plan*
(``minPlanName`` in its embedded loader data). The Provider API lists every
model the gateway can serve, not what your plan pays for, so ``/models`` alone
over-reports availability: premium models need Pro or Max even when the API
accepts their id. When ``providers.commandcode.plan`` is set, models whose
minimum plan is above it are dropped before they reach the tiers.
"""

from __future__ import annotations

import json
import re
from typing import Any

from model_pipeline.models import (
    ENDPOINT_CHAT,
    ENDPOINT_MESSAGES,
    RawModel,
    ResolvedPricing,
)
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.textutil import clean_text, normkey, parse_money

# Subscription plans in ascending order: a plan includes every model served by
# a lower plan. Verified against the catalog's own tab counts (2026-11-02):
# Go 58, GOAT 71 (= 58 + 13), Pro 87 (= 71 + 16), all 97 (= 87 + 10). A plan
# name we do not know ranks as "unverified", never as available.
_PLAN_RANK = {"GO": 0, "GOAT": 1, "PRO": 2, "MAX": 3}

# The models page ships its data as a React Router single-fetch stream.
_STREAM_MARKER = "streamController.enqueue("

_ROW_RE = re.compile(r"<tr.*?</tr>", re.S)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_TABLE_RE = re.compile(r"<table.*?</table>", re.S)
_ANCHOR_RE = re.compile(r"<a[^>]*>(.*?)</a>", re.S)
_HREF_RE = re.compile(r'href="/models/([a-z0-9\-]+)"')
_DISCOUNT_SUFFIX_RE = re.compile(r"\s*-\d+%\s*$")


class CommandCodeAdapter(ProviderAdapter):
    name = "commandcode"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configured = (self.pcfg.plan or "").strip().upper()
        # "all" = pay-as-you-go: the Provider API can serve premium models too.
        self.plan = "" if configured in ("", "ALL") else configured
        if self.plan and self.plan not in _PLAN_RANK:
            raise ValueError(
                f"providers.{self.name}.plan must be one of "
                f"{', '.join(_PLAN_RANK)} or 'all' (no filter); got {self.pcfg.plan!r}"
            )
        # Filled from the pricing page by fetch_pricing(); keyed like prices.
        self._min_plans: dict[str, str] = {}
        self.plan_excluded: list[tuple[str, str]] = []
        self.plan_unverified: list[str] = []

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def available(self, model: RawModel) -> bool:
        """Servable = protocol supported AND the plan includes the model.

        The Provider API advertises models a lower plan cannot use, so the
        catalog's own per-model minimum plan decides. A model with no plan
        entry is treated as unavailable — this pipeline never guesses access.
        """
        if not super().available(model):
            return False
        if not self.plan:
            return True
        required = self._min_plans.get(normkey(model.display_name)) or self._min_plans.get(
            normkey(model.model_id)
        )
        rank = _plan_rank(required or "")
        if rank is None:
            self.plan_unverified.append(model.model_id)
            return False
        if rank > _PLAN_RANK[self.plan]:
            self.plan_excluded.append((model.model_id, required))
            return False
        return True

    def fetch_models(self) -> list[RawModel]:
        try:
            resp = self.http.get(self.pcfg.models_url, headers=self._auth_headers())
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # record then propagate
            self._record(self.pcfg.models_url, "GET", error=str(exc))
            raise
        models: list[RawModel] = []
        for m in data.get("data", []):
            eps = m.get("supported_endpoints", []) or []
            endpoint_type = ENDPOINT_MESSAGES if "/messages" in eps else ENDPOINT_CHAT
            models.append(
                RawModel(
                    provider=self.name,
                    model_id=m["id"],
                    display_name=m.get("name") or m["id"],
                    endpoint_type=endpoint_type,
                    context_tokens=m.get("context_length"),
                    supported_endpoints=eps,
                )
            )
        self._record(self.pcfg.models_url, "GET", resp=resp, parsed_count=len(models))
        return models

    def fetch_pricing(self) -> dict[str, ResolvedPricing]:
        try:
            resp = self.http.get(self.pcfg.pricing_url)
            resp.raise_for_status()
        except Exception as exc:
            self._record(self.pcfg.pricing_url, "GET", error=str(exc))
            raise
        pricing = parse_commandcode_pricing(resp.text)
        if self.plan:
            # Same page, same fetch: fail loudly if the page stops publishing
            # plan data, because silence would let premium models through.
            try:
                self._min_plans = parse_commandcode_plans(resp.text)
            except Exception as exc:
                self._record(self.pcfg.pricing_url, "GET", resp=resp, error=f"plan data: {exc}")
                raise
        self._record(self.pcfg.pricing_url, "GET", resp=resp, parsed_count=len(pricing))
        return pricing

    def to_litellm_deployment(
        self, model: RawModel, pricing: ResolvedPricing, model_group: str, order: int
    ) -> dict:
        is_messages = model.endpoint_type == ENDPOINT_MESSAGES
        prefix = "anthropic/" if is_messages else "openai/"
        api_base = (
            self.pcfg.litellm["messages_api_base"]
            if is_messages
            else self.pcfg.litellm["openai_api_base"]
        )
        return self._assemble(
            model, pricing, model_group, order, f"{prefix}{model.model_id}", api_base
        )


def parse_commandcode_pricing(html: str) -> dict[str, ResolvedPricing]:
    result: dict[str, ResolvedPricing] = {}
    table_match = _TABLE_RE.search(html or "")
    if not table_match:
        return result
    for row_match in _ROW_RE.finditer(table_match.group(0)):
        cells = _CELL_RE.findall(row_match.group(0))
        if len(cells) < 7:
            continue
        # Name lives in the first anchor; fall back to the raw cell text.
        anchor = _ANCHOR_RE.search(cells[0])
        name = clean_text(anchor.group(1) if anchor else cells[0])
        name = _DISCOUNT_SUFFIX_RE.sub("", name).strip()
        if not name or name.lower().startswith("model"):
            continue

        pricing = ResolvedPricing(
            input=parse_money(clean_text(cells[3])),
            output=parse_money(clean_text(cells[4])),
            cache_read=parse_money(clean_text(cells[5])),
            cache_write=parse_money(clean_text(cells[6])),
        )
        pricing.provenance = {
            k: "provider"
            for k in ("input", "output", "cache_read", "cache_write")
            if getattr(pricing, k) is not None
        }
        if "Free" in clean_text(cells[3]):
            pricing.normalization.append("free model")
        if "$" in clean_text(cells[3]) and len(re.findall(r"\$", clean_text(cells[3]))) > 1:
            pricing.normalization.append("discounted (effective price used)")

        result[normkey(name)] = pricing
        href = _HREF_RE.search(cells[0])
        if href:
            result.setdefault(normkey(href.group(1)), pricing)
    return result


def _string_end(text: str, quote_at: int) -> int:
    """Index just past the closing quote of the JS string literal at ``quote_at``."""
    i = quote_at + 1
    escaped = False
    while i < len(text):
        ch = text[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return i + 1
        i += 1
    raise ValueError("unterminated stream payload")


def _stream_values(html: str) -> list:
    """Decode the page's React Router single-fetch stream into its value table.

    The page enqueues one (or more) JS string literals whose concatenation is a
    JSON array; objects in that array reference keys/values by table index
    (``{"_109": 390}``) so repeated strings are stored once.
    """
    text = html or ""
    chunks: list[str] = []
    pos = 0
    while True:
        at = text.find(_STREAM_MARKER, pos)
        if at < 0:
            break
        quote = at + len(_STREAM_MARKER)
        if quote >= len(text) or text[quote] != '"':
            pos = quote
            continue
        end = _string_end(text, quote)
        chunks.append(json.loads(text[quote:end]))
        pos = end
    if not chunks:
        raise ValueError("models page carries no stream payload")
    try:
        values = json.loads("".join(chunks))
    except json.JSONDecodeError as exc:
        raise ValueError(f"models page stream is not valid JSON: {exc}") from exc
    if not isinstance(values, list):
        raise TypeError("models page stream is not a value table")
    return values


def _plan_rank(name: str) -> int | None:
    """Rank of a published plan name, or None when the name is unknown."""
    return _PLAN_RANK.get((name or "").strip().upper())


def _stricter(current: str | None, candidate: str) -> str:
    """Keep whichever plan is stricter; an unknown plan always wins.

    Unknown names cannot be ranked, so they must never loosen access: the model
    then reports as unverified and is dropped instead of deployed.
    """
    if current is None:
        return candidate
    current_rank, candidate_rank = _plan_rank(current), _plan_rank(candidate)
    if current_rank is None:
        return current
    if candidate_rank is None:
        return candidate
    return candidate if candidate_rank > current_rank else current


def _table_key(key: Any, values: list) -> Any:
    """Resolve an object key (``"_109"``) to the table string it points at."""
    if isinstance(key, str) and key.startswith("_") and key[1:].isdigit():
        index = int(key[1:])
        if 0 <= index < len(values) and isinstance(values[index], str):
            return values[index]
        return None
    return key


def parse_commandcode_plans(html: str) -> dict[str, str]:
    """Map ``normkey`` of a model's name/slug to its minimum subscription plan.

    Read from the catalog page's own loader data (the ``minPlanName`` field),
    so no plan knowledge is invented here. A model missing from the result is
    unknown, and the adapter refuses to deploy it rather than assume access.
    """
    values = _stream_values(html)
    plans: dict[str, str] = {}
    for record in values:
        if not isinstance(record, dict):
            continue
        fields: dict[Any, Any] = {}
        for key, value in record.items():
            name = _table_key(key, values)
            if name not in ("slug", "name", "minPlanName"):
                continue
            fields[name] = (
                values[value] if isinstance(value, int) and 0 <= value < len(values) else value
            )
        plan = fields.get("minPlanName")
        if not isinstance(plan, str) or not plan.strip():
            continue
        for label in (fields.get("name"), fields.get("slug")):
            if not isinstance(label, str) or not label.strip():
                continue
            key = normkey(label)
            # Two catalog rows can normalize to the same key; keep the stricter
            # plan so a duplicate can never loosen access.
            plans[key] = _stricter(plans.get(key), plan.strip())
    if not plans:
        raise ValueError("models page carried no per-model plan data (schema change?)")
    return plans

