"""Suggested LiteLLM ``router_settings`` for same-order latency-pool failover.

The pipeline never edits the root ``config.yaml``. It writes this reviewable
block so the operator can copy it into ``router_settings`` after checking it
against the deployment.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from model_pipeline.config import Config


def build_suggested_router(cfg: Config) -> dict:
    litellm = cfg.litellm
    retries = int(litellm.num_retries)
    return {
        "router_settings": {
            "routing_strategy": "latency-based-routing",
            "routing_strategy_args": {
                "lowest_latency_buffer": float(litellm.lowest_latency_buffer)
            },
            "timeout": int(litellm.timeout),
            "cooldown_time": int(litellm.cooldown_time),
            "allowed_fails": int(litellm.global_allowed_fails),
            "retry_policy": {
                "DefaultRetries": retries,
                "RateLimitErrorRetries": retries,
                "InternalServerErrorRetries": retries,
                "AuthenticationErrorRetries": retries,
                "BadRequestErrorRetries": 1,
                "NotFoundErrorRetries": 0,
            },
        }
    }


def write_suggested_router_config(path: Path, cfg: Config) -> None:
    header = (
        "# Suggested LiteLLM router_settings for the populated model groups.\n"
        "# Review and copy into the root config.yaml; the pipeline never applies it.\n"
        "#\n"
        "# Why these values:\n"
        "# - routing_strategy: latency-based-routing picks the fastest healthy key\n"
        "#   at the current order; same-order keys form one latency pool.\n"
        "# - per-deployment model_info.allowed_fails: 0 (emitted on every model)\n"
        "#   benches a failed key on its first counted failure.\n"
        "# - num_retries is the retry budget for the current order. Set it to at\n"
        "#   least the largest same-order key count - 1 so every sibling is tried.\n"
        "# - cooldown_time must exceed the worst-case walk:\n"
        "#       max_keys_per_order x attempts_per_key x timeout\n"
        "#   With allowed_fails: 0 and InternalServerErrorAllowedFails: 1,\n"
        "#   attempts_per_key is 2. Increase cooldown_time or decrease timeout\n"
        "#   when raising the key count.\n"
        "# - DefaultRetries is what makes 402 (payment required) retry the same\n"
        "#   request on another key; 402 is non-retryable by default in LiteLLM.\n"
        "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        header + yaml.safe_dump(build_suggested_router(cfg), sort_keys=False),
        encoding="utf-8",
    )
