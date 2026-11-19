"""Tests for multi-key expansion and credential identity."""

from types import SimpleNamespace

from model_pipeline.config import load_config
from model_pipeline.emit.html_report import build_html
from model_pipeline.emit.output import build_markdown, build_payload
from model_pipeline.models import (
    CanonicalModel,
    Credential,
    Mapping,
    RawModel,
    ResolvedPricing,
    deployment_id,
    fingerprint_key,
)
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.scoring.pipeline import score


def test_deployment_id_keeps_slot_one_legacy_and_suffixes_later_keys():
    legacy = deployment_id("pro-tier", "commandcode", "xiaomi/mimo")
    slot_one = deployment_id("pro-tier", "commandcode", "xiaomi/mimo", 1)
    slot_two = deployment_id("pro-tier", "commandcode", "xiaomi/mimo", 2)

    assert slot_one == legacy
    assert slot_two == "mp::pro-tier::commandcode::key-2::xiaomi-mimo"
    assert "/" not in slot_two


def test_fingerprint_is_stable_and_non_secret():
    first = fingerprint_key("sk-secret")
    assert first == fingerprint_key("sk-secret")
    assert len(first) == 16
    assert "sk-secret" not in first


class _AssembleAdapter(ProviderAdapter):
    """Adapter that only exercises the shared payload assembly."""

    name = "ours"

    def __init__(self):
        self.pcfg = SimpleNamespace(api_key_env="", api_keys_env="OURS_APIS", extra_headers={})
        self.cfg = SimpleNamespace(
            litellm=SimpleNamespace(
                num_retries=32, allowed_fails=0, cooldown_time=1800
            )
        )
        self.credentials = [
            Credential(1, "key-a", "OURS_APIS", raw=True),
            Credential(2, "key-b", "OURS_APIS", raw=True),
        ]

    def fetch_models(self):
        return []

    def fetch_pricing(self):
        return {}

    def to_litellm_deployment(self, model, pricing, model_group, order, credential=None):
        return self._assemble(
            model,
            pricing,
            model_group,
            order,
            f"openai/{model.model_id}",
            "https://api.example/v1",
            credential,
        )


def _model(capabilities=None):
    return RawModel(
        provider="ours",
        model_id="gpt-x",
        display_name="GPT X",
        input_tokens=1000,
        output_tokens=100,
        capabilities=capabilities or {"supports_vision": True},
    )


def test_assemble_emits_raw_key_slots_without_storing_the_key():
    adapter = _AssembleAdapter()
    first = adapter._assemble(
        _model(), ResolvedPricing(input=1.0, output=2.0), "pro-tier", 2,
        "openai/gpt-x", "https://api.example/v1", adapter.credentials[0],
    )
    second = adapter._assemble(
        _model(), ResolvedPricing(input=1.0, output=2.0), "pro-tier", 2,
        "openai/gpt-x", "https://api.example/v1", adapter.credentials[1],
    )

    assert first["model_info"]["id"] == "mp::pro-tier::ours::gpt-x"
    assert second["model_info"]["id"] == "mp::pro-tier::ours::key-2::gpt-x"
    for payload, credential in ((first, adapter.credentials[0]), (second, adapter.credentials[1])):
        assert "api_key" not in payload["litellm_params"]  # resolved at populate
        assert payload["litellm_params"]["num_retries"] == 32
        assert payload["litellm_params"]["order"] == 2
        assert payload["model_info"]["credential_slot"] == credential.slot
        assert payload["model_info"]["api_key_fingerprint"] == credential.fingerprint
        assert payload["model_info"]["allowed_fails"] == 0
        assert payload["model_info"]["cooldown_time"] == 1800
        assert payload["model_info"]["mode"] == "chat"
        assert payload["model_info"]["supports_vision"] is True
        assert "key-a" not in str(payload) and "key-b" not in str(payload)


class _ExpandAdapter:
    """Fake adapter for score() with a configurable key count."""

    def __init__(self, keys):
        self.pcfg = SimpleNamespace(api_key_env="", api_keys_env="TEST_APIS")
        self.credentials = [
            Credential(slot=i, value=key, env_name="TEST_APIS", raw=True)
            for i, key in enumerate(keys, start=1)
        ]

    def to_litellm_deployment(self, model, pricing, model_group, order, credential=None):
        slot = credential.slot if credential else 1
        return {
            "model_name": model_group,
            "litellm_params": {
                "model": "openai/gpt-x",
                "api_base": "http://stub",
                "order": order,
                "num_retries": 32,
            },
            "model_info": {
                "id": deployment_id(model_group, "p1", model.model_id, slot),
                "credential_slot": slot,
                "api_key_fingerprint": credential.fingerprint if credential else "",
            },
        }


def _score_with_keys(keys):
    cfg = load_config()
    mappings = [
        Mapping(provider="p1", model_id="gpt-x", canonical_slug="a", canonical_name="A")
    ]
    models = {
        ("p1", "gpt-x"): RawModel(
            provider="p1",
            model_id="gpt-x",
            display_name="A",
            pricing=ResolvedPricing(input=1.0, output=2.0),
        )
    }
    canonical = [
        CanonicalModel(
            slug="a", name="A", intelligence=50, aa_input=1.0, aa_output=2.0
        )
    ]
    adapters = {"p1": _ExpandAdapter(keys)}
    return score(mappings, models, canonical, adapters, cfg)


def test_multi_key_expansion_after_selection_preserves_order_and_ranking():
    one = _score_with_keys(["key-a"])
    three = _score_with_keys(["key-a", "key-b", "key-c"])

    one_tier = one.tiers[0]
    three_tier = three.tiers[0]
    assert len(one_tier.deployments) == 1
    assert len(three_tier.deployments) == 3
    assert {d.order for d in three_tier.deployments} == {d.order for d in one_tier.deployments}
    assert [r.order for r in three_tier.ranking] == [r.order for r in one_tier.ranking]
    assert {d.credential_slot for d in three_tier.deployments} == {1, 2, 3}
    assert {d.credential_count for d in three_tier.deployments} == {3}


def test_score_emits_capability_and_failover_fields_on_every_key():
    cfg = load_config()
    mappings = [
        Mapping(provider="p1", model_id="gpt-x", canonical_slug="a", canonical_name="A")
    ]
    models = {
        ("p1", "gpt-x"): RawModel(
            provider="p1",
            model_id="gpt-x",
            display_name="A",
            pricing=ResolvedPricing(input=1.0, output=2.0),
            capabilities={
                "supports_vision": True,
                "supports_reasoning": True,
                "reasoning_effort_levels": ["low", "high"],
            },
            capabilities_source="models.dev:p1",
        )
    }
    canonical = [
        CanonicalModel(
            slug="a", name="A", intelligence=50, aa_input=1.0, aa_output=2.0
        )
    ]
    result = score(mappings, models, canonical, {"p1": _AssembleAdapter()}, cfg)
    deployments = result.tiers[0].deployments
    assert len(deployments) == 2

    for deployment in deployments:
        payload = deployment.litellm_params
        assert payload["litellm_params"]["num_retries"] == 32
        info = payload["model_info"]
        assert info["supports_vision"] is True
        assert info["supports_reasoning"] is True
        assert info["reasoning_effort_levels"] == ["low", "high"]
        assert info["allowed_fails"] == 0
        assert info["cooldown_time"] == 1800
        assert info["credential_slot"] in {1, 2}
        assert info["api_key_fingerprint"]
        assert deployment.credential_count == 2


def test_artifact_and_reports_show_credential_counts_without_keys():
    result = _score_with_keys(["key-a", "key-b", "key-c"])
    payload = build_payload(result, load_config())
    tier = payload["tiers"][0]
    assert len(tier["deployments"]) == 3
    for deployment in tier["deployments"]:
        assert deployment["credential_slot"] in {1, 2, 3}
        assert deployment["api_key_fingerprint"]
        assert deployment["credential_count"] == 3
        assert "key-a" not in str(deployment)

    markdown = build_markdown(payload)
    assert "| Keys |" in markdown
    assert "3 | `gpt-x`" in markdown

    page = build_html(result)
    assert "<th>Keys</th>" in page
    assert "key-a" not in page
