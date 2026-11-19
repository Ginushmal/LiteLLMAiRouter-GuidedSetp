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
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from model_pipeline.config import Config, ProviderConfig
from model_pipeline.http import HttpClient, ScrapeRecord, ScrapeRecorder
from model_pipeline.models import Credential, RawModel, ResolvedPricing, deployment_id
from model_pipeline.textutil import normkey

# Statuses that mean "try the next API key". 400/404 are request/endpoint
# problems, not key problems, so they stay terminal.
_KEY_FALLBACK_STATUSES = frozenset({401, 402, 403, 408, 409, 429})


@dataclass
class FetchCensus:
    """What a provider advertised vs what survived the pre-dedup filters."""

    provider: str
    advertised: int = 0
    extracted: int = 0
    unsupported_protocol: list[str] = field(default_factory=list)
    no_pricing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "advertised": self.advertised,
            "extracted": self.extracted,
            "unsupported_protocol": self.unsupported_protocol,
            "no_pricing": self.no_pricing,
        }


class ProviderAdapter(ABC):
    name: str = ""

    def __init__(self, cfg: Config, http: HttpClient, recorder: ScrapeRecorder):
        self.cfg = cfg
        self.pcfg: ProviderConfig = cfg.providers[self.name]
        self.http = http
        self.recorder = recorder
        if hasattr(cfg, "provider_credentials"):
            self.credentials: list[Credential] = cfg.provider_credentials(self.name)
        else:
            # Lightweight test/config doubles predate the key-list API.
            legacy = getattr(self.pcfg, "api_key_env", "")
            value = cfg.secret(legacy) if legacy and hasattr(cfg, "secret") else ""
            self.credentials = (
                [Credential(1, value, legacy, raw=False)] if legacy else []
            )
        # Kept for adapters/tests that reference a single key; the fetch path
        # always uses ``self.credentials`` so the list is authoritative.
        self.api_key = self.credentials[0].value if self.credentials else ""
        # Populated by fetch_all(); consumed immediately by the fetch CLI.
        self.last_census: FetchCensus | None = None

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

    def fetch_with_key_fallback(
        self, url: str, *, timeout: float | None = None
    ) -> httpx.Response:
        """GET ``url`` with the provider's keys in order.

        Authentication, payment, authorization, timeout/conflict, rate-limit,
        server, and transport failures move to the next slot. A 400/404 means
        the request or endpoint is wrong, so it is raised immediately. Only the
        slot and fingerprint are recorded; the raw key never reaches a log.
        """
        if not self.credentials:
            raise RuntimeError(
                f"{self.name}: no API keys configured (api_keys_env/api_key_env)"
            )

        errors: list[str] = []
        for credential in self.credentials:
            label = f"slot {credential.slot} ({credential.fingerprint})"
            headers = {"Authorization": f"Bearer {credential.value}"}
            try:
                resp = self.http.get(url, headers=headers)
            except httpx.RequestError as exc:
                message = f"{label}: {type(exc).__name__}: {exc}"
                self._record(url, "GET", error=message)
                errors.append(message)
                continue

            if 200 <= resp.status_code < 300:
                return resp

            retryable = (
                resp.status_code in _KEY_FALLBACK_STATUSES or resp.status_code >= 500
            )
            message = f"{label}: HTTP {resp.status_code}"
            self._record(url, "GET", resp=resp, error=message)
            errors.append(message)
            if not retryable:
                # The request or endpoint is wrong; another key cannot fix it.
                raise httpx.HTTPStatusError(
                    f"{self.name} {url} returned {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )

        raise RuntimeError(
            f"{self.name} {url} failed for all {len(self.credentials)} configured "
            "key slot(s): " + "; ".join(errors)
        )

    # -- interface ---------------------------------------------------------
    @abstractmethod
    def fetch_models(self) -> list[RawModel]:
        """Return the models this provider advertises."""

    @abstractmethod
    def fetch_pricing(self) -> dict[str, ResolvedPricing]:
        """Return prices keyed by ``normkey(display_name)``."""

    def available(self, model: RawModel) -> bool:
        """Whether we can serve this model given the protocols we support.

        Adapters that translate a native protocol to a supported deployment
        protocol (OpenCode responses/google -> chat) set ``endpoint_type`` to
        the deployment protocol, so this filter only sees protocols the adapter
        can actually emit.
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
        credential: Credential | None = None,
    ) -> dict:
        """Build the LiteLLM ``/model/new`` payload for one deployment."""

    # -- convenience -------------------------------------------------------
    def fetch_all(self) -> list[RawModel]:
        models = self.fetch_models()
        pricing = self.fetch_pricing()
        census = FetchCensus(provider=self.name, advertised=len(models))
        out: list[RawModel] = []
        for m in models:
            m.pricing = pricing.get(normkey(m.display_name)) or pricing.get(
                normkey(m.model_id)
            )
            if m.pricing is None:
                census.no_pricing.append(m.model_id)
            elif not self.available(m):
                census.unsupported_protocol.append(m.model_id)
            else:
                out.append(m)
        census.extracted = len(out)
        self.last_census = census
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
        credential: Credential | None = None,
    ) -> dict:
        litellm_params: dict = {
            "model": model_param,
            "api_base": api_base,
            "order": order,
        }
        # New list mode sends the raw key to /model/new (resolved by the
        # populate phase, never stored in tier-output.json). Legacy mode keeps
        # the proxy-side os.environ reference.
        if credential is not None and not credential.raw:
            litellm_params["api_key"] = f"os.environ/{credential.env_name}"
        elif credential is None and self.pcfg.api_key_env:
            litellm_params["api_key"] = f"os.environ/{self.pcfg.api_key_env}"

        litellm_params.update(self._price_params(pricing))
        if self.pcfg.extra_headers:
            litellm_params["extra_headers"] = dict(self.pcfg.extra_headers)
        litellm_settings = getattr(getattr(self, "cfg", None), "litellm", None)
        if litellm_settings is not None:
            num_retries = getattr(litellm_settings, "num_retries", None)
            if num_retries is not None:
                litellm_params["num_retries"] = int(num_retries)

        slot = credential.slot if credential is not None else 1
        model_info = {
            "id": deployment_id(model_group, self.name, model.model_id, slot),
            "base_model": model_param,
            "provider": self.name,
            "model_group": model_group,
            "provider_model_name": model.display_name,
            "mode": "chat",
            "credential_slot": slot,
        }
        if credential is not None:
            model_info["api_key_fingerprint"] = credential.fingerprint
        if litellm_settings is not None:
            allowed_fails = getattr(litellm_settings, "allowed_fails", None)
            cooldown_time = getattr(litellm_settings, "cooldown_time", None)
            if allowed_fails is not None:
                model_info["allowed_fails"] = int(allowed_fails)
            if cooldown_time is not None:
                model_info["cooldown_time"] = int(cooldown_time)

        # Capabilities resolved from the provider's own models.dev entry. Empty
        # means unknown, so nothing is written (never invent a capability).
        model_info.update(model.capabilities)

        # Emit the real token limits. Without them LiteLLM's model-info
        # discovery mirrors the context window into max_output_tokens, which is
        # what made clients ask for completions no model can serve.
        # ``max_tokens`` mirrors the output cap (LiteLLM's own convention) so the
        # discovery fill cannot leak it into responses either.
        if model.input_tokens is not None:
            model_info["max_input_tokens"] = model.input_tokens
        if model.output_tokens is not None:
            model_info["max_output_tokens"] = model.output_tokens
            model_info["max_tokens"] = model.output_tokens
        return {
            "model_name": model_group,
            "litellm_params": litellm_params,
            "model_info": model_info,
        }
