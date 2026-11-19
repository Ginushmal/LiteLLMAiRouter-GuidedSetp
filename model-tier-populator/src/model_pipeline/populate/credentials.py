"""Resolve credential slots to raw keys immediately before population.

``tier-output.json`` never carries raw API keys. Each deployment records the
provider and ``credential_slot``; populate reads the provider key list from
``.env`` and fills ``litellm_params.api_key`` for the request to LiteLLM.

Legacy single-key deployments already carry ``api_key: os.environ/...`` and are
left untouched, so the proxy keeps resolving them itself.
"""

from __future__ import annotations

from model_pipeline.config import Config


def resolve_payload_credentials(payload: dict, cfg: Config) -> int:
    """Fill raw keys for slot-based deployments; return the number resolved."""
    resolved = 0
    for tier in payload.get("tiers", []):
        for dep in tier.get("deployments", []):
            params = dep.setdefault("litellm_params", {})
            info = dep.setdefault("model_info", {})
            if params.get("api_key"):
                continue

            provider = dep.get("provider") or info.get("provider")
            slot = dep.get("credential_slot") or info.get("credential_slot")
            if not provider or not slot:
                # Legacy/synthetic payloads may predate credential slots and
                # carry no key reference. Leave them untouched; a real new
                # artifact always records both fields.
                continue

            credentials = cfg.provider_credentials(str(provider))
            if slot < 1 or slot > len(credentials):
                raise RuntimeError(
                    f"{provider}: credential slot {slot} does not exist in the "
                    f"configured key list ({len(credentials)} key(s)); re-run score"
                )
            params["api_key"] = credentials[slot - 1].value
            resolved += 1
    return resolved
