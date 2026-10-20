"""Configuration and environment loading.

Secrets live in the repo-root ``.env`` (never in git). ``config.yaml`` holds
everything else and references secrets only by environment-variable name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# model-pipeline/ is two levels above this file (src/model_pipeline/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def find_repo_root(start: Path) -> Path:
    """Walk up from ``start`` looking for a ``.env`` file (the repo root)."""
    for candidate in [start, *start.parents]:
        if (candidate / ".env").exists():
            return candidate
    # Fall back to the parent of the project directory.
    return PROJECT_ROOT.parent


def load_env(repo_root: Path | None = None) -> dict[str, str]:
    """Load ``KEY=VALUE`` pairs from ``.env`` (does not override real env vars)."""
    repo_root = repo_root or find_repo_root(PROJECT_ROOT)
    values: dict[str, str] = {}
    env_file = repo_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    # Real environment variables win over the file.
    for key in list(values):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


@dataclass
class TaskProfile:
    input: int
    cached: int
    output: int
    reasoning: int
    cache_write: int
    requests_per_task: int
    cache_hit_rate: float
    input_output_ratio: float
    reasoning_price_multiplier: float


@dataclass
class NmbConfig:
    tier_lambdas: dict[str, float]
    # One share per tier, or a single value applied to every tier. The share is
    # scale-free: each tier's NMB lives on its own scale (lambda multiplies
    # intelligence), so a raw dollar-per-second weight would mean different
    # things per tier. mu is derived from it at score time.
    latency_rho: float | dict[str, float]
    tier_floors: dict[str, float]
    top_k_per_tier: int

    @property
    def tier_names(self) -> list[str]:
        return list(self.tier_floors.keys())

    def rho_for(self, tier: str) -> float:
        """The latency share for one tier (a scalar config applies to all)."""
        rho = self.latency_rho
        if isinstance(rho, dict):
            if tier not in rho:
                raise ValueError(
                    f"nmb.latency_rho has no entry for tier {tier!r}; "
                    f"configured tiers: {sorted(rho)}"
                )
            return float(rho[tier])
        return float(rho)


@dataclass
class PricingPolicy:
    context_tier_policy: str
    active_window_utc: tuple[str, str]
    active_days: list[int]
    peak_windows_utc: list[tuple[str, str]]


@dataclass
class AaConfig:
    free_url: str
    pro_url: str
    api_key_env: str
    page_size: int


@dataclass
class JevConfig:
    endpoint: str
    model: str
    api_key_env: str
    timeout_seconds: int
    review_confidence_threshold: float
    candidate_shortlist_size: int


@dataclass
class DedupConfig:
    strip_suffixes: list[str]
    speed_suffixes: list[str]
    effort_tokens: list[str]


@dataclass
class ProviderConfig:
    name: str
    enabled: bool
    api_base: str
    models_url: str
    api_key_env: str
    pricing_url: str
    litellm: dict[str, str] = field(default_factory=dict)
    extra_headers: dict[str, str] = field(default_factory=dict)
    supported_endpoints: list[str] = field(default_factory=list)
    # models.dev provider id(s) that publish this provider's models. Provider
    # metadata only — the model identities themselves come from the APIs.
    models_dev_provider_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelsDevConfig:
    api_url: str


@dataclass
class LitellmConfig:
    base_url: str
    master_key_env: str
    tier_model_groups: dict[str, str]


@dataclass
class Config:
    data: dict[str, Any]
    env: dict[str, str]
    repo_root: Path

    task_profile: TaskProfile
    nmb: NmbConfig
    pricing: PricingPolicy
    aa: AaConfig
    jev: JevConfig
    dedup: DedupConfig
    exclude_patterns: list[str]
    # Tier name (same keys as ``nmb.tier_floors``) -> extra patterns applied to
    # that tier only. Empty everywhere means "no tier-scoped filtering".
    exclude_tier_patterns: dict[str, list[str]]
    # Tier name -> ordered canonical slugs force-included at the top of that
    # tier's order chain. Empty everywhere means "no pins".
    pin_slugs: dict[str, list[str]]
    providers: dict[str, ProviderConfig]
    litellm: LitellmConfig
    models_dev: ModelsDevConfig
    output_dir: Path
    raw_dir: Path
    logs_dir: Path

    def secret(self, env_name: str) -> str:
        value = self.env.get(env_name)
        if not value:
            raise RuntimeError(
                f"Missing secret '{env_name}'. Add it to {self.repo_root / '.env'}."
            )
        return value

    def resolve_path(self, relative: str) -> Path:
        return (PROJECT_ROOT / relative).resolve()


def _pattern_list(value: Any, key: str) -> list[str]:
    """Normalise one exclusion pattern list.

    A bare string is rejected rather than iterated character by character,
    which would otherwise turn ``Pro: "gpt-5"`` into a set of one-letter
    patterns that match almost every model.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list of patterns, got {type(value).__name__}")
    return [str(pattern) for pattern in value if str(pattern).strip()]


def _tier_pattern_map(raw: Any) -> dict[str, list[str]]:
    """Normalise ``exclude.tiers`` (tier name -> pattern list)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TypeError("exclude.tiers must be a mapping of tier name -> pattern list")
    return {
        str(tier): _pattern_list(patterns, f"exclude.tiers.{tier}")
        for tier, patterns in raw.items()
    }


def _pin_map(raw: Any) -> dict[str, list[str]]:
    """Normalise ``pins.tiers`` (tier name -> ordered canonical slugs).

    A bare string is rejected: a pin list is an ordered sequence, and iterating
    a string would silently pin its characters. Blank entries are dropped.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TypeError("pins.tiers must be a mapping of tier name -> list of canonical slugs")
    pins: dict[str, list[str]] = {}
    for tier, slugs in raw.items():
        if slugs is None:
            pins[str(tier)] = []
            continue
        if not isinstance(slugs, list):
            raise TypeError(
                f"pins.tiers.{tier} must be a list of canonical slugs, "
                f"got {type(slugs).__name__}"
            )
        clean: list[str] = []
        for slug in slugs:
            if not isinstance(slug, str):
                raise TypeError(
                    f"pins.tiers.{tier} must contain only canonical slug strings, "
                    f"got {type(slug).__name__}"
                )
            slug = slug.strip()
            if slug:
                clean.append(slug)
        pins[str(tier)] = clean
    return pins


def _validate_tier_names(
    tier_patterns: dict[str, list[str]],
    tier_floors: dict[str, float],
    key: str = "exclude.tiers",
) -> None:
    """Reject tier names no ranking tier defines, so a typo is never silent."""
    unknown = sorted(set(tier_patterns) - set(tier_floors))
    if unknown:
        raise ValueError(
            f"{key} names unknown tier(s): {', '.join(unknown)}; "
            f"valid tiers are: {', '.join(tier_floors)}"
        )


def load_config(config_path: Path | str | None = None) -> Config:
    config_path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    repo_root = find_repo_root(PROJECT_ROOT)
    env = load_env(repo_root)

    tp = data["task_profile"]
    pr = tp["per_request"]

    providers: dict[str, ProviderConfig] = {}
    for name, raw in data["providers"].items():
        providers[name] = ProviderConfig(
            name=name,
            enabled=raw.get("enabled", True),
            api_base=raw["api_base"].rstrip("/"),
            models_url=raw["models_url"],
            api_key_env=raw["api_key_env"],
            pricing_url=raw["pricing_url"],
            litellm=raw.get("litellm", {}),
            extra_headers=raw.get("extra_headers", {}),
            supported_endpoints=raw.get("supported_endpoints", []),
            models_dev_provider_ids=raw.get("models_dev_provider_ids", []),
        )

    paths = data.get("paths", {})
    win = data["pricing"]["active_window_utc"]

    nmb = NmbConfig(
        tier_lambdas=data["nmb"]["tier_lambdas"],
        latency_rho=data["nmb"]["latency_rho"],
        tier_floors=data["nmb"]["tier_floors"],
        top_k_per_tier=data["nmb"]["top_k_per_tier"],
    )
    # Fail fast: a per-tier mapping must cover every tier, otherwise that tier
    # would silently rank without the penalty the config promises.
    for tier_name in nmb.tier_floors:
        nmb.rho_for(tier_name)

    # Tier-scoped exclusions are additive to the global patterns above; their
    # keys must be real ranking tiers so a typo cannot silently do nothing.
    tier_patterns = _tier_pattern_map((data.get("exclude") or {}).get("tiers"))
    _validate_tier_names(tier_patterns, nmb.tier_floors)

    # Manual tier pins: ordered canonical slugs force-included ahead of NMB
    # selection. Their tier names are validated exactly like exclude.tiers.
    pin_slugs = _pin_map((data.get("pins") or {}).get("tiers"))
    _validate_tier_names(pin_slugs, nmb.tier_floors, "pins.tiers")

    return Config(
        data=data,
        env=env,
        repo_root=repo_root,
        task_profile=TaskProfile(
            input=pr["input"],
            cached=pr["cached"],
            output=pr["output"],
            reasoning=pr["reasoning"],
            cache_write=pr["cache_write"],
            requests_per_task=tp["requests_per_task"],
            cache_hit_rate=tp["cache_hit_rate"],
            input_output_ratio=tp["input_output_ratio"],
            reasoning_price_multiplier=tp["reasoning_price_multiplier"],
        ),
        nmb=nmb,
        pricing=PricingPolicy(
            context_tier_policy=data["pricing"]["context_tier_policy"],
            active_window_utc=(win["start"], win["end"]),
            active_days=data["pricing"]["active_days"],
            peak_windows_utc=[tuple(w) for w in data["pricing"]["peak_windows_utc"]],
        ),
        aa=AaConfig(**data["aa"]),
        jev=JevConfig(**data["jev"]),
        dedup=DedupConfig(**data["dedup"]),
        exclude_patterns=data.get("exclude", {}).get("patterns", []) or [],
        exclude_tier_patterns=tier_patterns,
        pin_slugs=pin_slugs,
        providers=providers,
        litellm=LitellmConfig(**data["litellm"]),
        models_dev=ModelsDevConfig(**data["models_dev"]),
        output_dir=PROJECT_ROOT / paths.get("output", "output"),
        raw_dir=PROJECT_ROOT / paths.get("raw_scrapes", "data/raw"),
        logs_dir=PROJECT_ROOT / paths.get("logs", "data/logs"),
    )
