"""OpenRouter (openrouter.ai/api/v1) adapter.

One public JSON catalog carries **both** models and prices, so there is no
pricing page to scrape. Each entry has:

  * ``id`` (vendor-prefixed, e.g. ``anthropic/claude-opus-4.5``) and ``name``,
  * ``context_length`` and ``architecture.output_modalities``,
  * per-token USD **strings** (``"0.000005"`` = $5/M), and
  * optional ``pricing.overrides[]``: per-model price schedules.

Model eligibility:

  * ``:batch`` variants are dropped here - they serve OpenRouter's Batch API,
    not chat traffic, so no config could make them servable.
  * ``:free`` variants ARE models: they keep their published $0 prices and map
    to the same canonical identity as their paid sibling (the dedup layer
    strips the plan suffix).
  * ``openrouter/free`` ("Free Models Router") stays: it is chat-servable, and
    dropping it is a policy call made in ``exclude.patterns``.

Override shapes (verified live 2026-10-21):

  * context tier: ``{"min_prompt_tokens": 100000, "prompt": "..."}``
  * time band:    ``{"utc_start": 1600, "utc_end": 0, "prompt": "..."}``
    (HHMM numbers; ``utc_end: 0`` means end of day; ``utc_days`` may name the
    weekdays, and an entry with only ``utc_days`` applies all day on them)

Bands are always the model's own. The global ``pricing.peak_windows_utc`` is
never applied here: providers differ (e.g. ``tencent/hy3`` peaks 00:00-16:00
daily, unlike the DeepSeek weekday windows).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from model_pipeline.models import ENDPOINT_CHAT, RawModel, ResolvedPricing
from model_pipeline.pricing import (
    PriceBand,
    band_price,
    collapse_tiers,
    days_from_names,
)
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.textutil import normkey

# ResolvedPricing component -> OpenRouter pricing key.
_COMPONENTS = {
    "input": "prompt",
    "output": "completion",
    "cache_read": "input_cache_read",
    "cache_write": "input_cache_write",
}

_BATCH_SUFFIX = ":batch"


def _per_million(value: Any) -> float | None:
    """OpenRouter publishes USD per token as a string; we work in $/1M."""
    if value is None:
        return None
    try:
        return float(value) * 1e6
    except (TypeError, ValueError):
        # A non-numeric price is missing data, never zero.
        return None


def _is_chat_servable(entry: dict[str, Any]) -> bool:
    """False for entries that can never be a chat deployment."""
    model_id = str(entry.get("id") or "").strip()
    if not model_id or model_id.endswith(_BATCH_SUFFIX):
        return False
    outputs = (entry.get("architecture") or {}).get("output_modalities")
    return outputs is None or "text" in outputs


@dataclass(frozen=True)
class _Override:
    """One parsed ``pricing.overrides[]`` entry."""

    prices: dict[str, float] = field(default_factory=dict)
    start: int | str | None = None
    end: int | str | None = None
    days: frozenset[int] | None = None
    min_prompt_tokens: int | None = None

    @property
    def is_time_band(self) -> bool:
        return self.start is not None or self.end is not None or self.days is not None


def _parse_override(raw: dict[str, Any]) -> _Override:
    prices: dict[str, float] = {}
    for component, key in _COMPONENTS.items():
        price = _per_million(raw.get(key))
        if price is not None:
            prices[component] = price
    days_raw = raw.get("utc_days")
    return _Override(
        prices=prices,
        start=raw.get("utc_start"),
        end=raw.get("utc_end"),
        days=frozenset(days_from_names(days_raw)) if days_raw else None,
        min_prompt_tokens=raw.get("min_prompt_tokens"),
    )


class OpenRouterAdapter(ProviderAdapter):
    name = "openrouter"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._catalog: dict[str, Any] | None = None

    # -- catalog -----------------------------------------------------------
    def _catalog_data(self) -> dict[str, Any]:
        if self._catalog is None:
            try:
                # The catalog is public; only the chat endpoint needs the key.
                resp = self.http.get(self.pcfg.models_url)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:  # record then propagate
                self._record(self.pcfg.models_url, "GET", error=str(exc))
                raise
            self._record(
                self.pcfg.models_url,
                "GET",
                resp=resp,
                parsed_count=len(data.get("data") or []),
                notes="catalog: models + pricing",
            )
            self._catalog = data
        return self._catalog

    def _entries(self) -> list[dict[str, Any]]:
        return [e for e in (self._catalog_data().get("data") or []) if _is_chat_servable(e)]

    def _model_from(self, entry: dict[str, Any]) -> RawModel:
        model_id = str(entry.get("id"))
        return RawModel(
            provider=self.name,
            model_id=model_id,
            display_name=str(entry.get("name") or model_id),
            endpoint_type=ENDPOINT_CHAT,
            context_tokens=entry.get("context_length"),
            supported_endpoints=[ENDPOINT_CHAT],
        )

    # -- interface ---------------------------------------------------------
    def fetch_models(self) -> list[RawModel]:
        models = [self._model_from(entry) for entry in self._entries()]
        self._record(
            self.pcfg.models_url + "#models",
            "GET",
            parsed_count=len(models),
            notes="parsed from cached catalog",
        )
        return models

    def fetch_pricing(self) -> dict[str, ResolvedPricing]:
        pricing: dict[str, ResolvedPricing] = {}
        for entry in self._entries():
            resolved = self._priced(entry)
            model_id = str(entry.get("id"))
            pricing.setdefault(normkey(model_id), resolved)
            if entry.get("name"):
                pricing.setdefault(normkey(str(entry["name"])), resolved)
        self._record(
            self.pcfg.models_url + "#pricing",
            "GET",
            parsed_count=len(pricing),
            notes="parsed from cached catalog",
        )
        return pricing

    def fetch_all(self) -> list[RawModel]:
        """One catalog read for models **and** prices.

        The generic two-step lookup cannot be used safely here: a ``:free`` id
        and its paid sibling normalize to the same ``normkey(model_id)``, so a
        free row could inherit the paid price.
        """
        models: list[RawModel] = []
        for entry in self._entries():
            model = self._model_from(entry)
            model.pricing = self._priced(entry)
            if self.available(model):
                models.append(model)
        return models

    def to_litellm_deployment(
        self, model: RawModel, pricing: ResolvedPricing, model_group: str, order: int
    ) -> dict:
        api_base = self.pcfg.litellm["chat_completions_api_base"]
        return self._assemble(
            model, pricing, model_group, order, f"openai/{model.model_id}", api_base
        )

    # -- pricing -----------------------------------------------------------
    def _priced(self, entry: dict[str, Any]) -> ResolvedPricing:
        """Parse one catalog entry into a ResolvedPricing; fail loudly."""
        try:
            return self._resolve_pricing(entry)
        except ValueError as exc:
            message = f"openrouter pricing for {entry.get('id')!r}: {exc}"
            self._record(self.pcfg.models_url, "GET", error=message)
            raise ValueError(message) from exc

    def _resolve_pricing(self, entry: dict[str, Any]) -> ResolvedPricing:
        raw = entry.get("pricing") or {}
        base = {component: _per_million(raw.get(key)) for component, key in _COMPONENTS.items()}
        overrides = [_parse_override(o) for o in (raw.get("overrides") or [])]

        time_bands = [o for o in overrides if o.is_time_band]
        context_bands = [o for o in overrides if o.min_prompt_tokens is not None]
        thresholds = sorted(
            {o.min_prompt_tokens for o in context_bands if o.min_prompt_tokens is not None}
        )

        policy = self.cfg.pricing
        instant = policy.as_of or datetime.now(timezone.utc)
        resolved = ResolvedPricing()

        for component in _COMPONENTS:
            base_price = base[component]
            if base_price is None:
                continue

            tiers: list[tuple[float, list[PriceBand]]] = [
                (
                    base_price,
                    self._bands(
                        component,
                        base_price,
                        [o for o in time_bands if o.min_prompt_tokens is None],
                    ),
                )
            ]
            for threshold in thresholds:
                tier = [o for o in context_bands if o.min_prompt_tokens == threshold]
                plain = [o for o in tier if not o.is_time_band]
                tier_base = (
                    plain[0].prices.get(component, base_price) if plain else base_price
                )
                tiers.append(
                    (
                        tier_base,
                        self._bands(
                            component,
                            tier_base,
                            [o for o in tier if o.is_time_band],
                        ),
                    )
                )

            setattr(
                resolved,
                component,
                collapse_tiers(
                    tiers,
                    mode=policy.time_price_mode,
                    active_window=policy.active_window_utc,
                    active_days=policy.active_days,
                    as_of=instant,
                    policy=policy.context_tier_policy,
                ),
            )

        resolved.provenance = {
            component: "provider"
            for component in _COMPONENTS
            if getattr(resolved, component) is not None
        }

        if overrides:
            parts = [f"time={policy.time_price_mode}"]
            if policy.time_price_mode in ("today", "instant"):
                parts.append(f"as_of={instant.astimezone(timezone.utc):%Y-%m-%dT%H:%MZ}")
            if thresholds:
                parts.append(f"context={policy.context_tier_policy}")
            resolved.normalization.append(
                "per-model schedule collapsed (" + ", ".join(parts) + ")"
            )
        if base["input"] == 0 and base["output"] == 0:
            resolved.normalization.append("free model")
        return resolved

    @staticmethod
    def _bands(
        component: str, fallback_price: float, overrides: list[_Override]
    ) -> list[PriceBand]:
        bands: list[PriceBand] = []
        for override in overrides:
            bands.append(
                band_price(
                    override.prices.get(component, fallback_price),
                    override.start,
                    override.end,
                    override.days,
                )
            )
        return bands
