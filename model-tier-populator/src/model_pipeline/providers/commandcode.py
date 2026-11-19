"""CommandCode (api.commandcode.ai/provider/v1) adapter.

Models come from the Provider API. Prices come from the HTML catalog at
commandcode.ai/models, whose rows currently look like:

    Model | Context | Input | Output | Cache read | Cache write | Caps

The column set is not stable (an Intelligence column sat between Context and
Input until it was removed in November 2026), so columns are located by the
table's header text, never by position. A table that stops publishing any of
the Input, Output, Cache read, or Cache write headers aborts the fetch instead
of parsing shifted prices.

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

# Header text -> pricing field. Matched on lowercased alphanumeric words, so a
# sort glyph or extra decoration around the label does not matter.
_HEADER_FIELDS = {
    "model": "model",
    "input": "input",
    "output": "output",
    "cache read": "cache_read",
    "cache write": "cache_write",
}
_REQUIRED_PRICE_FIELDS = ("input", "output", "cache_read", "cache_write")
_FIELD_LABELS = {
    "input": "Input",
    "output": "Output",
    "cache_read": "Cache read",
    "cache_write": "Cache write",
}
_HEADER_NOISE_RE = re.compile(r"[^a-z0-9]+")


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
        resp = self.fetch_with_key_fallback(self.pcfg.models_url)
        try:
            data = resp.json()
        except Exception as exc:  # record then propagate
            self._record(self.pcfg.models_url, "GET", resp=resp, error=str(exc))
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
        try:
            pricing = parse_commandcode_pricing(resp.text)
        except Exception as exc:
            # Record then propagate: a silent partial parse would stamp wrong
            # prices as provider data.
            self._record(self.pcfg.pricing_url, "GET", resp=resp, error=str(exc))
            raise
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
        self,
        model: RawModel,
        pricing: ResolvedPricing,
        model_group: str,
        order: int,
        credential=None,
    ) -> dict:
        is_messages = model.endpoint_type == ENDPOINT_MESSAGES
        prefix = "anthropic/" if is_messages else "openai/"
        api_base = (
            self.pcfg.litellm["messages_api_base"]
            if is_messages
            else self.pcfg.litellm["openai_api_base"]
        )
        return self._assemble(
            model,
            pricing,
            model_group,
            order,
            f"{prefix}{model.model_id}",
            api_base,
            credential,
        )


def parse_commandcode_pricing(html: str) -> dict[str, ResolvedPricing]:
    result: dict[str, ResolvedPricing] = {}
    table_match = _TABLE_RE.search(html or "")
    if not table_match:
        return result
    rows = _ROW_RE.findall(table_match.group(0))
    if not rows:
        raise ValueError("models page pricing table has no rows (schema change?)")
    # Columns are located by header text, never by position: the page dropped
    # its Intelligence column in November 2026 and a positional parser silently
    # shifted every price into the neighbouring field.
    columns = pricing_column_map(_CELL_RE.findall(rows[0]))
    last_column = max(columns.values())
    name_column = columns.get("model", 0)

    for row_html in rows[1:]:
        cells = _CELL_RE.findall(row_html)
        if len(cells) <= last_column:
            continue
        name_cell = cells[name_column] if name_column < len(cells) else cells[0]
        # Name lives in the cell's anchor; fall back to the raw cell text.
        anchor = _ANCHOR_RE.search(name_cell)
        name = clean_text(anchor.group(1) if anchor else name_cell)
        name = _DISCOUNT_SUFFIX_RE.sub("", name).strip()
        if not name:
            continue

        input_cell = clean_text(cells[columns["input"]])
        pricing = ResolvedPricing(
            input=parse_money(input_cell),
            output=parse_money(clean_text(cells[columns["output"]])),
            cache_read=parse_money(clean_text(cells[columns["cache_read"]])),
            cache_write=parse_money(clean_text(cells[columns["cache_write"]])),
        )
        pricing.provenance = {
            k: "provider"
            for k in ("input", "output", "cache_read", "cache_write")
            if getattr(pricing, k) is not None
        }
        if "Free" in input_cell:
            pricing.normalization.append("free model")
        if len(re.findall(r"\$", input_cell)) > 1:
            pricing.normalization.append("discounted (effective price used)")

        result[normkey(name)] = pricing
        href = _HREF_RE.search(name_cell)
        if href:
            result.setdefault(normkey(href.group(1)), pricing)
    return result


def pricing_column_map(header_cells: list[str]) -> dict[str, int]:
    """Map pricing fields to column indices using the table's header text.

    Header cells carry a sort-marker glyph (``Input ↕``), so only the
    alphanumeric words are compared. ``model`` is optional (the name column is
    assumed first when absent, and the anchor lookup still keys the row); all
    four price columns are required, because a table that stopped publishing
    one of them would otherwise yield provider-stamped prices that are wrong
    or missing.
    """
    columns: dict[str, int] = {}
    for index, cell in enumerate(header_cells):
        field = _HEADER_FIELDS.get(_header_key(cell))
        if field is not None:
            columns.setdefault(field, index)
    missing = [
        _FIELD_LABELS[field]
        for field in _REQUIRED_PRICE_FIELDS
        if field not in columns
    ]
    if missing:
        raise ValueError(
            "models page pricing table is missing required column(s): "
            f"{', '.join(missing)} (page schema change?)"
        )
    return columns


def _header_key(cell_html: str) -> str:
    """Header cell text as lowercased alphanumeric words (glyphs dropped)."""
    return _HEADER_NOISE_RE.sub(" ", clean_text(cell_html).lower()).strip()


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

