"""Provider adapter interface.

Each provider implements the same four operations:
  fetch_models()           -> the models it advertises (from its /models API)
  fetch_pricing()          -> normalized prices keyed by normkey(name)
  available(model)         -> whether we can currently serve that model
  to_litellm_deployment()  -> the LiteLLM /model/new payload for one model

Adapters own all provider-specific quirks (endpoint protocols, HTML shapes,
auth headers). Everything downstream works on the normalized models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from model_pipeline.config import Config, ProviderConfig
from model_pipeline.http import HttpClient, ScrapeRecorder, ScrapeRecord
from model_pipeline.models import RawModel, ResolvedPricing
from model_pipeline.textutil import normkey


class ProviderAdapter(ABC):
    name: str = ""

    def __init__(self, cfg: Config, http: HttpClient, recorder: ScrapeRecorder):
        self.cfg = cfg
        self.pcfg: ProviderConfig = cfg.providers[self.name]
        self.http = http
        self.recorder = recorder
        self.api_key = cfg.secret(self.pcfg.api_key_env)

    # -- fetch forensics ---------------------------------------------------
    def _record(
        self,
        url: str,
        method: str,
        resp=None,
        error: str = "",
        parsed_count: int | None = None,
        notes: str = "",
    ) -> None:
        rec = ScrapeRecord(
            provider=self.name,
            url=url,
            method=method,
            status=(resp.status_code if resp is not None else None),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            content_type=(resp.headers.get("content-type", "") if resp is not None else ""),
            parsed_count=parsed_count,
            error=error,
            notes=notes,
        )
        self.recorder.record(rec, body=(resp.text if resp is not None else ""))

    # -- interface ---------------------------------------------------------
    @abstractmethod
    def fetch_models(self) -> list[RawModel]:
        """Return the models this provider advertises."""

    @abstractmethod
    def fetch_pricing(self) -> dict[str, ResolvedPricing]:
        """Return prices keyed by ``normkey(display_name)``."""

    def available(self, model: RawModel) -> bool:
        """Whether we can serve this model given the protocols we support.

        Models whose endpoint protocol is deferred (OpenCode responses/google)
        are excluded here rather than silently mis-routed.
        """
        supported = self.pcfg.supported_endpoints
        if not supported:
            return True
        return model.endpoint_type in supported

    @abstractmethod
    def to_litellm_deployment(
        self,
        model: RawModel,
        pricing: ResolvedPricing,
        model_group: str,
        order: int,
    ) -> dict:
        """Build the LiteLLM ``/model/new`` payload for one deployment."""

    # -- convenience -------------------------------------------------------
    def fetch_all(self) -> list[RawModel]:
        models = self.fetch_models()
        pricing = self.fetch_pricing()
        out: list[RawModel] = []
        for m in models:
            m.pricing = pricing.get(normkey(m.display_name)) or pricing.get(
                normkey(m.model_id)
            )
            if m.pricing is not None and self.available(m):
                out.append(m)
        return out

    # -- shared deployment assembly ---------------------------------------
    @staticmethod
    def _price_params(pricing: ResolvedPricing) -> dict:
        """Convert $/1M prices to LiteLLM's $/token params."""
        params: dict = {}
        if pricing.input is not None:
            params["input_cost_per_token"] = pricing.input / 1e6
        if pricing.output is not None:
            params["output_cost_per_token"] = pricing.output / 1e6
        if pricing.cache_read is not None:
            params["cache_read_input_token_cost"] = pricing.cache_read / 1e6
        if pricing.cache_write is not None:
            params["cache_creation_input_token_cost"] = pricing.cache_write / 1e6
        return params

    def _assemble(
        self,
        model: RawModel,
        pricing: ResolvedPricing,
        model_group: str,
        order: int,
        model_param: str,
        api_base: str,
    ) -> dict:
        litellm_params: dict = {
            "model": model_param,
            "api_base": api_base,
            "api_key": f"os.environ/{self.pcfg.api_key_env}",
            "order": order,
        }
        litellm_params.update(self._price_params(pricing))
        if self.pcfg.extra_headers:
            litellm_params["extra_headers"] = dict(self.pcfg.extra_headers)

        model_info = {
            "id": f"mp::{model_group}::{self.name}::{model.model_id}",
            "base_model": model_param,
            "provider": self.name,
            "model_group": model_group,
            "provider_model_name": model.display_name,
        }
        if model.context_tokens:
            model_info["max_input_tokens"] = model.context_tokens
        return {
            "model_name": model_group,
            "litellm_params": litellm_params,
            "model_info": model_info,
        }
