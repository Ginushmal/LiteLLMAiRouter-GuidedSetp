"""CommandCode (api.commandcode.ai/provider/v1) adapter.

Models come from the Provider API. Prices come from the HTML catalog at
commandcode.ai/models, whose rows look like:

    Model | Context | Intelligence | Input | Output | Cache read | Cache write | Caps

Price cells carry plan markers ("$0.10 + 1") and, for discounted models, a
strikethrough list price followed by the effective price ("$0.80 $0.14").
We keep the effective (last) dollar figure.
"""

from __future__ import annotations

import re

from model_pipeline.models import (
    ENDPOINT_CHAT,
    ENDPOINT_MESSAGES,
    RawModel,
    ResolvedPricing,
)
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.textutil import clean_text, normkey, parse_money

_ROW_RE = re.compile(r"<tr.*?</tr>", re.S)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_TABLE_RE = re.compile(r"<table.*?</table>", re.S)
_ANCHOR_RE = re.compile(r"<a[^>]*>(.*?)</a>", re.S)
_HREF_RE = re.compile(r'href="/models/([a-z0-9\-]+)"')
_DISCOUNT_SUFFIX_RE = re.compile(r"\s*-\d+%\s*$")


class CommandCodeAdapter(ProviderAdapter):
    name = "commandcode"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

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
