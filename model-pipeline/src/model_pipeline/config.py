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
    latency_penalty_mu: float
    tier_floors: dict[str, float]
    top_k_per_tier: int

    @property
    def tier_names(self) -> list[str]:
        return list(self.tier_floors.keys())


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
    extra: dict[str, Any] = field(default_factory=dict)


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
    providers: dict[str, ProviderConfig]
    litellm: LitellmConfig
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
        )

    paths = data.get("paths", {})
    win = data["pricing"]["active_window_utc"]

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
        nmb=NmbConfig(
            tier_lambdas=data["nmb"]["tier_lambdas"],
            latency_penalty_mu=data["nmb"]["latency_penalty_mu"],
            tier_floors=data["nmb"]["tier_floors"],
            top_k_per_tier=data["nmb"]["top_k_per_tier"],
        ),
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
        providers=providers,
        litellm=LitellmConfig(**data["litellm"]),
        output_dir=PROJECT_ROOT / paths.get("output", "output"),
        raw_dir=PROJECT_ROOT / paths.get("raw_scrapes", "data/raw"),
        logs_dir=PROJECT_ROOT / paths.get("logs", "data/logs"),
    )
