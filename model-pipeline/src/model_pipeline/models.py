"""Shared data models for the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Endpoint format a provider model speaks. Determines the LiteLLM provider
# prefix and the api_base path used when populating.
ENDPOINT_CHAT = "chat"          # OpenAI /chat/completions
ENDPOINT_RESPONSES = "responses"  # OpenAI /responses
ENDPOINT_MESSAGES = "messages"  # Anthropic /messages
ENDPOINT_GOOGLE = "google"      # Google generateContent style


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


@dataclass
class CanonicalModel:
    """A model identity from Artificial Analysis (the canonical hub)."""

    slug: str
    name: str
    creator: str = ""
    variant: str = ""
    intelligence: Optional[float] = None
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
    context_tokens: Optional[int] = None
    nmb: float = 0.0
    tier: str = ""
    model_group: str = ""
    order: int = 0
    pareto_frontier: bool = False
    is_backup: bool = False
    effective_prices: dict[str, Any] = field(default_factory=dict)
    provider_pricing: Optional[ResolvedPricing] = None
    litellm_params: dict[str, Any] = field(default_factory=dict)

    # Stable identity used for diff-based population.
    @property
    def deployment_id(self) -> str:
        return f"mp::{self.model_group}::{self.provider}::{self.model_id}"

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
            "intelligence": self.intelligence,
            "cost_per_task": self.cost_per_task,
            "cost_method": self.cost_method,
            "nmb": self.nmb,
            "tier": self.tier,
            "model_group": self.model_group,
            "order": self.order,
            "pareto_frontier": self.pareto_frontier,
            "is_backup": self.is_backup,
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
