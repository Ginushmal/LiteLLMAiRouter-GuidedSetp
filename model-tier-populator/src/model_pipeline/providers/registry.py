"""Provider adapter registry."""

from __future__ import annotations

from model_pipeline.config import Config
from model_pipeline.http import HttpClient, ScrapeRecorder
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.providers.commandcode import CommandCodeAdapter
from model_pipeline.providers.opencode import OpenCodeAdapter

_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "commandcode": CommandCodeAdapter,
    "opencode": OpenCodeAdapter,
}


def build_adapters(
    cfg: Config, http: HttpClient, recorder: ScrapeRecorder
) -> list[ProviderAdapter]:
    adapters: list[ProviderAdapter] = []
    for name, cls in _REGISTRY.items():
        provider_cfg = cfg.providers.get(name)
        if provider_cfg and provider_cfg.enabled:
            adapters.append(cls(cfg, http, recorder))
    return adapters
