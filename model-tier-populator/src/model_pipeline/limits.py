"""Token-limit resolution from the public models.dev catalog.

Providers publish a *context window* and nothing else. LiteLLM, when it has to
discover a model's limits itself, mirrors that context window into the model's
*output* limit, so clients compute completion budgets no real model can serve.
models.dev publishes a real per-model output limit, so that is where the
pipeline gets one.

Resolution order, most specific first:

1. the pipeline provider's own catalog entry, exact model id;
2. a normalized model-id match inside the pipeline provider's entries;
3. the exact model id anywhere in the catalog;
4. a normalized model-id match anywhere in the catalog.

Normalization ignores case, punctuation, a vendor prefix and serving suffixes
(``-fast``/``-ultraspeed``/``:free``/...), so ``google/gemini-4-argon``,
``Gemini 4 Argon`` and ``gemini-4-argon-free`` land on the same key. Inside a
fallback step the model vendor's own entry wins (``xiaomi`` for
``xiaomi/mimo-v2.6-pro``), then entries are taken in a stable order so runs are
reproducible.

The input limit is *derived* as ``context - output``. The provider-published
context window stays the authority for context (the catalog agrees: where it
publishes both, ``input == context - output``, e.g. 1050000-128000=922000).
Nothing is invented: when no entry publishes an output limit the model is
flagged ``unresolved`` and the value stays unset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from model_pipeline.config import Config
from model_pipeline.http import HttpClient, ScrapeRecord, ScrapeRecorder
from model_pipeline.models import RawModel

# Scrape artifact directory / log name for the catalog itself.
CATALOG_PROVIDER = "modelsdev"

# Report flags. ``unresolved`` is set by the resolver; the other two are set
# when a value exists but looks wrong, so a reviewer can audit it.
FLAG_UNRESOLVED = "unresolved"
FLAG_OUTPUT_EQUALS_CONTEXT = "output_equals_context"
FLAG_OUTPUT_NOT_BELOW_CONTEXT = "output_not_below_context"


@dataclass
class ResolvedLimits:
    """One model's resolved output limit plus where the value came from."""

    output: Optional[int] = None
    source: str = ""  # "models.dev:<provider>" | "models.dev-fallback:<provider>"
    flags: list[str] = field(default_factory=list)


def _output(entry: Optional[dict[str, Any]]) -> Optional[int]:
    """The entry's published output limit, or None when it publishes none."""
    limit = (entry or {}).get("limit") or {}
    value = limit.get("output")
    return value if isinstance(value, int) and value > 0 else None


def _context(entry: Optional[dict[str, Any]]) -> Optional[int]:
    limit = (entry or {}).get("limit") or {}
    value = limit.get("context")
    return value if isinstance(value, int) and value > 0 else None


def normalize_model_id(
    model_id: str,
    strip_suffixes: Iterable[str] = (),
    speed_suffixes: Iterable[str] = (),
) -> str:
    """Case/punctuation/vendor-prefix/serving-suffix insensitive lookup key."""
    key = model_id.strip().lower().split(":", 1)[0]  # ":free"-style plan suffix
    key = key.rsplit("/", 1)[-1]  # vendor prefix (google/gemini-4-argon)
    suffixes = sorted(
        {s.strip().lower() for s in [*strip_suffixes, *speed_suffixes] if s.strip()},
        key=len,
        reverse=True,
    )
    # Strip repeatedly: "model-free-preview" carries two suffixes.
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if len(key) > len(suffix) and key.endswith(suffix):
                key = key[: -len(suffix)]
                changed = True
    return re.sub(r"[^a-z0-9]", "", key)


class LimitResolver:
    """Lookups over one parsed models.dev catalog (``https://models.dev/api.json``)."""

    def __init__(
        self,
        catalog: dict[str, Any],
        strip_suffixes: Iterable[str] = (),
        speed_suffixes: Iterable[str] = (),
    ):
        self._strip = list(strip_suffixes)
        self._speed = list(speed_suffixes)
        self._by_provider: dict[str, dict[str, dict]] = {}
        self._norm_by_provider: dict[str, dict[str, list[tuple[str, dict]]]] = {}
        self._norm_global: dict[str, list[tuple[str, str, dict]]] = {}
        self.model_count = 0
        for provider_id, provider in (catalog or {}).items():
            models = (provider or {}).get("models") or {}
            self._by_provider[provider_id] = models
            norm_index: dict[str, list[tuple[str, dict]]] = {}
            for model_id, entry in models.items():
                key = self._norm(model_id)
                norm_index.setdefault(key, []).append((model_id, entry))
                self._norm_global.setdefault(key, []).append((provider_id, model_id, entry))
                self.model_count += 1
            self._norm_by_provider[provider_id] = norm_index

    def _norm(self, model_id: str) -> str:
        return normalize_model_id(model_id, self._strip, self._speed)

    # -- resolution --------------------------------------------------------
    def resolve(self, provider_ids: list[str], model_id: str) -> ResolvedLimits:
        """Resolve ``model_id`` for a pipeline provider, most specific source first."""
        # 1. our provider's own entry, exact id.
        for provider_id in provider_ids:
            entry = self._by_provider.get(provider_id, {}).get(model_id)
            if _output(entry) is not None:
                return self._hit(entry, f"models.dev:{provider_id}")

        # 2. our provider's entry, matched after normalization.
        key = self._norm(model_id)
        for provider_id in provider_ids:
            for _matched_id, entry in self._norm_by_provider.get(provider_id, {}).get(key, []):
                if _output(entry) is not None:
                    return self._hit(entry, f"models.dev:{provider_id}")

        # 3./4. another provider's entry: the model vendor's own entry first,
        # then an exact id match, then a normalized match.
        fallback = self._fallback(key, model_id)
        if fallback is not None:
            return fallback
        return ResolvedLimits(flags=[FLAG_UNRESOLVED])

    def _vendor(self, model_id: str) -> str:
        """The vendor prefix of a model id (``xiaomi`` for ``xiaomi/mimo-v2.6-pro``)."""
        return model_id.rsplit("/", 1)[0].strip().lower() if "/" in model_id else ""

    def _rank(self, candidates: list[tuple[str, str, dict]], model_id: str) -> list[tuple[str, str, dict]]:
        """Model vendor's own entry first, then an exact id, then a stable order."""
        vendor = self._vendor(model_id)
        return sorted(
            candidates,
            key=lambda c: (c[0] != vendor, c[1] != model_id, c[0], c[1]),
        )

    def _fallback(self, key: str, model_id: str) -> Optional[ResolvedLimits]:
        seen: set[tuple[str, str]] = set()
        candidates: list[tuple[str, str, dict]] = []
        for provider_id, models in self._by_provider.items():
            entry = models.get(model_id)
            if _output(entry) is not None:
                candidates.append((provider_id, model_id, entry))
                seen.add((provider_id, model_id))
        for provider_id, matched_id, entry in self._norm_global.get(key, []):
            if (provider_id, matched_id) in seen or _output(entry) is None:
                continue
            candidates.append((provider_id, matched_id, entry))
        for provider_id, _matched_id, entry in self._rank(candidates, model_id):
            return self._hit(entry, f"models.dev-fallback:{provider_id}")
        return None

    @staticmethod
    def _hit(entry: dict, source: str) -> ResolvedLimits:
        value = _output(entry)
        flags: list[str] = []
        context = _context(entry)
        if value is not None and context is not None and value == context:
            # Looks like the context window was copied into the output cap.
            flags.append(FLAG_OUTPUT_EQUALS_CONTEXT)
        return ResolvedLimits(output=value, source=source, flags=flags)


# -- fetch + apply ---------------------------------------------------------
def models_dev_ids(cfg: Config) -> dict[str, list[str]]:
    """pipeline provider -> models.dev provider id(s), from the provider blocks."""
    return {
        name: (pcfg.models_dev_provider_ids or [name])
        for name, pcfg in cfg.providers.items()
    }


def fetch_catalog(
    cfg: Config, http: HttpClient, recorder: ScrapeRecorder
) -> Optional[LimitResolver]:
    """Fetch, record, and index the models.dev catalog.

    Returns None when the catalog cannot be fetched: callers then resolve every
    model as ``unresolved`` (an audible warning) and keep going — a catalog
    outage must not block scoring or population.
    """
    url = cfg.models_dev.api_url
    try:
        resp = http.get(url)
        resp.raise_for_status()
        catalog = resp.json()
    except Exception as exc:
        recorder.record(
            ScrapeRecord(
                provider=CATALOG_PROVIDER,
                url=url,
                method="GET",
                status=None,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                error=str(exc)[:300],
            )
        )
        return None

    resolver = LimitResolver(catalog, cfg.dedup.strip_suffixes, cfg.dedup.speed_suffixes)
    recorder.record(
        ScrapeRecord(
            provider=CATALOG_PROVIDER,
            url=url,
            method="GET",
            status=resp.status_code,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            content_type=resp.headers.get("content-type", ""),
            parsed_count=resolver.model_count,
            notes=f"{len(catalog)} providers",
        ),
        body=resp.text,
    )
    return resolver


def apply_limits(
    models: list[RawModel],
    resolver: Optional[LimitResolver],
    provider_ids: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Annotate each model with resolved limits; return ``provider:model -> flags``.

    ``input_tokens`` is derived from the provider's context window and the
    resolved output limit. With no provider context (OpenCode publishes none)
    the input limit stays unknown rather than guessed.
    """
    flagged: dict[str, list[str]] = {}
    for model in models:
        ids = provider_ids.get(model.provider) or [model.provider]
        limits = (
            resolver.resolve(ids, model.model_id)
            if resolver is not None
            else ResolvedLimits(flags=[FLAG_UNRESOLVED])
        )
        model.output_tokens = limits.output
        model.input_tokens = None
        model.limits_source = limits.source
        model.limits_flags = list(limits.flags)

        if limits.output is not None and model.context_tokens is not None:
            if limits.output >= model.context_tokens:
                model.limits_flags.append(FLAG_OUTPUT_NOT_BELOW_CONTEXT)
            else:
                model.input_tokens = model.context_tokens - limits.output

        if model.limits_flags:
            flagged[f"{model.provider}:{model.model_id}"] = model.limits_flags
    return flagged
