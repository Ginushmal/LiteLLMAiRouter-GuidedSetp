"""Tests for the suggested router_settings artifact."""

import yaml

from model_pipeline.config import load_config
from model_pipeline.emit.suggested_router import (
    build_suggested_router,
    write_suggested_router_config,
)


def test_suggested_router_contains_latency_pool_failover():
    cfg = load_config()
    block = build_suggested_router(cfg)["router_settings"]

    assert block["routing_strategy"] == "latency-based-routing"
    assert block["routing_strategy_args"]["lowest_latency_buffer"] == 0.0
    assert block["timeout"] == cfg.litellm.timeout
    assert block["cooldown_time"] == cfg.litellm.cooldown_time
    assert block["allowed_fails"] == cfg.litellm.global_allowed_fails
    assert block["retry_policy"]["DefaultRetries"] == cfg.litellm.num_retries
    assert block["retry_policy"]["BadRequestErrorRetries"] == 1
    assert block["retry_policy"]["NotFoundErrorRetries"] == 0


def test_suggested_router_file_parses_and_explains_the_walk_formula(tmp_path):
    cfg = load_config()
    path = tmp_path / "suggested_router_config.yaml"
    write_suggested_router_config(path, cfg)

    text = path.read_text(encoding="utf-8")
    assert "max_keys_per_order" in text
    assert "not applied" in text or "never applies" in text or "never applying" in text
    parsed = yaml.safe_load(text)
    assert parsed["router_settings"]["routing_strategy"] == "latency-based-routing"
