"""Shared data models for the pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Endpoint format a provider model speaks. Determines the LiteLLM provider
# prefix and the api_base path used when populating.
ENDPOINT_CHAT = "chat"          # OpenAI /chat/completions
ENDPOINT_RESPONSES = "responses"  # OpenAI /responses
ENDPOINT_MESSAGES = "messages"  # Anthropic /messages
ENDPOINT_GOOGLE = "google"      # Google generateContent style

# Prefix shared by every deployment the pipeline manages in LiteLLM's DB.
ID_PREFIX = "mp::"


def safe_id_part(value: str) -> str:
    """Fold one identity component into a URL-path-safe string.

    LiteLLM addresses a stored model by its id *in the URL*
    (``PATCH /model/{model_id}/update``), and the ASGI server decodes the path
    before routing, so an id containing ``/`` splits the route and can never be
    addressed (the Admin UI cannot edit such a row either). Provider model ids
    sometimes carry a vendor prefix (``xiaomi/mimo-v2.6-pro``), so unsafe
    characters are folded to ``-``.
    """
    return re.sub(r"[^A-Za-z0-9._:-]+", "-", value).strip("-") or "model"


def deployment_id(
    model_group: str,
    provider: str,
    model_id: str,
    credential_slot: int | None = None,
) -> str:
    """Stable, URL-safe identity for one (tier, provider, model) deployment.

    Slot 1 (and ``None``) keeps the historical id so existing single-key
    deployments are not recreated. Additional keys append ``key-<n>`` so each
    credential has its own row while the first key keeps its spend history.
    """
    base = (
        f"{ID_PREFIX}{safe_id_part(model_group)}::{safe_id_part(provider)}"
    )
    if credential_slot is not None and credential_slot > 1:
        return f"{base}::key-{credential_slot}::{safe_id_part(model_id)}"
    return f"{base}::{safe_id_part(model_id)}"


def fingerprint_key(value: str) -> str:
    """Non-secret, stable identity for one API key (SHA-256 prefix)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Credential:
    """One provider API key and the slot it occupies in the key list.

    ``value`` is deliberately excluded from repr: it is the raw secret and must
    never appear in logs, artifacts, or exception messages. ``raw`` selects how
    the payload references it: ``True`` means "resolve to ``value`` when
    populating"; ``False`` means "send ``os.environ/<env_name>`` and let LiteLLM
    resolve it" (legacy single-key behavior).
    """

    slot: int
    value: str = field(repr=False)
    env_name: str = ""
    raw: bool = True
    fingerprint: str = field(default="")

    def __post_init__(self) -> None:
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", fingerprint_key(self.value))


@dataclass
class ResolvedPricing:
    """One normalized price set in dollars per 1M tokens.

    ``provenance`` records, per component, where the value came from:
    ``provider`` (scraped directly) or ``aa_fallback`` (estimated from AA).
    ``normalization`` is a human-readable list of the choices that produced
    these numbers (context-tier policy, peak weighting, discount, ...).
    """

    input: Optional[float] = None
    output: Optional[float] = None
    cache_read: Optional[float] = None
    cache_write: Optional[float] = None
    provenance: dict[str, str] = field(default_factory=dict)
    normalization: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "provenance": self.provenance,
            "normalization": self.normalization,
        }


@dataclass
class RawModel:
    """A model as advertised by one provider, before canonical mapping."""

    provider: str
    model_id: str
    display_name: str
    endpoint_type: str = ENDPOINT_CHAT
    context_tokens: Optional[int] = None
    supported_endpoints: list[str] = field(default_factory=list)
    pricing: Optional[ResolvedPricing] = None
    # Token limits resolved from the models.dev catalog (see limits.py).
    # ``output_tokens`` is the catalog's real per-model output cap;
    # ``input_tokens`` is derived as ``context_tokens - output_tokens`` and stays
    # None when the provider publishes no context window.
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    limits_source: str = ""  # e.g. "models.dev:commandcode" / "models.dev-fallback:xiaomi"
    limits_flags: list[str] = field(default_factory=list)  # "unresolved", "output_equals_context", ...
    # Capability fields ready to merge into LiteLLM's model_info. Empty means
    # the provider's models.dev entry did not declare them (never invented).
    capabilities: dict[str, Any] = field(default_factory=dict)
    capabilities_source: str = ""
    capabilities_flags: list[str] = field(default_factory=list)


@dataclass
class CanonicalModel:
    """A model identity from Artificial Analysis (the canonical hub)."""

    slug: str
    name: str
    creator: str = ""
    variant: str = ""
    intelligence: Optional[float] = None
    # AA median end-to-end response time in seconds (None when AA publishes none).
    latency_seconds: Optional[float] = None
    coding_index: Optional[float] = None
    aa_input: Optional[float] = None  # $/1M
    aa_output: Optional[float] = None  # $/1M
    aa_cache_read: Optional[float] = None
    aa_cache_write: Optional[float] = None
    aa_cost_per_task: Optional[float] = None
    # Pro-tier only (may be absent on the free tier).
    aa_token_counts: Optional[dict[str, Any]] = None
    aa_cost_breakdown: Optional[dict[str, Any]] = None


@dataclass
class Mapping:
    """Result of mapping one provider model to a canonical identity."""

    provider: str
    model_id: str
    canonical_slug: Optional[str]
    canonical_name: Optional[str]
    variant: str = ""
    method: str = "unmapped"  # exact | jev | override | unmapped
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    override: str = ""  # human-supplied canonical slug (wins over computed)
    low_confidence: bool = False

    @property
    def effective_slug(self) -> Optional[str]:
        """The slug that actually applies, honouring a manual override."""
        return self.override or self.canonical_slug


@dataclass
class Deployment:
    """A fully scored (model x provider) unit ready for emit/populate."""

    canonical_slug: str
    canonical_name: str
    provider: str
    model_id: str
    display_name: str
    endpoint_type: str
    api_base: str
    api_key_env: str
    intelligence: float
    cost_per_task: float
    cost_method: str = ""
    # AA median end-to-end response time (seconds); None when AA publishes none.
    latency_seconds: Optional[float] = None
    context_tokens: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    limits_source: str = ""
    limits_flags: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    capabilities_source: str = ""
    capabilities_flags: list[str] = field(default_factory=list)
    # Credential identity for multi-key providers. Slot 1 keeps the legacy id.
    credential_slot: int = 1
    api_key_fingerprint: str = ""
    credential_count: int = 1
    nmb: float = 0.0
    tier: str = ""
    model_group: str = ""
    order: int = 0
    pareto_frontier: bool = False
    is_backup: bool = False
    # Force-included by `pins.tiers`; distinct from primary/backup NMB picks.
    is_pinned: bool = False
    effective_prices: dict[str, Any] = field(default_factory=dict)
    provider_pricing: Optional[ResolvedPricing] = None
    litellm_params: dict[str, Any] = field(default_factory=dict)

    # Stable identity used for diff-based population.
    @property
    def deployment_id(self) -> str:
        return deployment_id(
            self.model_group, self.provider, self.model_id, self.credential_slot
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_slug": self.canonical_slug,
            "canonical_name": self.canonical_name,
            "provider": self.provider,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "endpoint_type": self.endpoint_type,
            "api_base": self.api_base,
            "api_key_env": self.api_key_env,
            "context_tokens": self.context_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "limits_source": self.limits_source,
            "limits_flags": self.limits_flags,
            "capabilities_source": self.capabilities_source,
            "capabilities_flags": self.capabilities_flags,
            "credential_slot": self.credential_slot,
            "api_key_fingerprint": self.api_key_fingerprint,
            "credential_count": self.credential_count,
            "intelligence": self.intelligence,
            "latency_seconds": self.latency_seconds,
            "cost_per_task": self.cost_per_task,
            "cost_method": self.cost_method,
            "nmb": self.nmb,
            "tier": self.tier,
            "model_group": self.model_group,
            "order": self.order,
            "pareto_frontier": self.pareto_frontier,
            "is_backup": self.is_backup,
            "is_pinned": self.is_pinned,
            "effective_prices": self.effective_prices,
            "litellm_params": self.litellm_params,
        }


@dataclass
class RankedModel:
    """One tier-ranking row for the explainability report (one NMB group)."""

    canonical_slug: str
    canonical_name: str
    display_name: str
    providers: list[str]
    intelligence: float
    cost_per_task: float
    nmb: float
    on_frontier: bool
    status: str  # "primary" | "backup" | "cut"
    order: int = 0
    latency_seconds: Optional[float] = None
