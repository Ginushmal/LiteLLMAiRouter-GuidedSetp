"""Tests for diff-based population comparison and the PATCH update path."""

from types import SimpleNamespace

from model_pipeline.models import deployment_id
from model_pipeline.populate.litellm_client import LiteLLMClient
from model_pipeline.populate.sync import (
    _info_differ,
    _params_differ,
    _update_body,
    apply_plan,
    build_plan,
    param_warnings,
)


def test_ignores_masked_api_key():
    # /model/info never returns api_key, so a matching model must read unchanged.
    desired = {"model": "openai/x", "api_base": "u", "api_key": "os.environ/K", "order": 1}
    current = {"model": "openai/x", "api_base": "u", "order": 1, "use_litellm_proxy": False}
    assert not _params_differ(desired, current)


def test_detects_real_change():
    assert _params_differ({"order": 2}, {"order": 1})
    assert _params_differ({"api_base": "https://a"}, {"api_base": "https://b"})


def test_float_tolerance():
    assert not _params_differ({"input_cost_per_token": 4e-06}, {"input_cost_per_token": 4.0000000000000004e-06})


def test_detects_extra_header_change():
    assert _params_differ(
        {"extra_headers": {"x-opencode-session": "a"}},
        {"extra_headers": {"x-opencode-session": "b"}},
    )


# -- model_info convergence ----------------------------------------------
INFO = {
    "base_model": "openai/gpt-6-luna",
    "model_group": "pro-tier",
    "max_input_tokens": 922000,
    "max_output_tokens": 128000,
    "max_tokens": 128000,
}


def test_info_diff_ignores_server_managed_fields():
    current = {**INFO, "id": "mp::x", "member_auto_router": False, "db_model": False}
    assert not _info_differ(INFO, current)


def test_info_diff_detects_missing_and_stale_limits():
    # Stored rows predating this change carry only a context-sized input limit.
    stale = {"base_model": "openai/gpt-6-luna", "max_input_tokens": 1050000, "model_group": "pro-tier"}
    assert _info_differ(INFO, stale)
    # ...and no output limit at all.
    assert _info_differ({"max_output_tokens": 128000}, {"max_output_tokens": None})
    assert _info_differ({"max_tokens": 128000}, {})


def test_info_diff_ignores_a_field_we_do_not_set():
    # Unresolved limits must not cause a permanent diff.
    assert not _info_differ({"max_output_tokens": None}, {"max_output_tokens": 999})


def test_update_body_carries_only_pipeline_owned_fields():
    desired = {
        "model_name": "pro-tier",
        "litellm_params": {"model": "openai/gpt-6-luna", "order": 1},
        "model_info": {
            "id": "mp::pro-tier::commandcode::gpt-6-luna",
            "base_model": "openai/gpt-6-luna",
            "model_group": "pro-tier",
            "provider": "commandcode",
            "provider_model_name": "GPT-6 Luna",
            "max_input_tokens": 922000,
            "max_output_tokens": 128000,
            "max_tokens": 128000,
        },
    }
    body = _update_body(desired)
    assert set(body["model_info"]) == {
        "id",
        "base_model",
        "model_group",
        "max_input_tokens",
        "max_output_tokens",
        "max_tokens",
    }
    assert "provider_model_name" not in body["model_info"]
    assert body["litellm_params"] == desired["litellm_params"]
    assert body["model_name"] == "pro-tier"


def test_deployment_ids_are_url_safe():
    # A "/" would split the PATCH route, so it must never reach the id.
    assert deployment_id("pro-tier", "commandcode", "xiaomi/mimo-v2.6-pro") == (
        "mp::pro-tier::commandcode::xiaomi-mimo-v2.6-pro"
    )
    assert "/" not in deployment_id("pro-tier", "commandcode", "google/gemini-4-argon")


# -- PATCH client ---------------------------------------------------------
def test_info_diff_detects_capabilities_and_failover_fields():
    desired = {
        "supports_vision": True,
        "supports_audio_output": False,
        "modalities": {"input": ["text", "image"], "output": ["text"]},
        "supports_reasoning": True,
        "reasoning_effort_levels": ["low", "high"],
        "supports_low_reasoning_effort": True,
        "supports_high_reasoning_effort": True,
        "allowed_fails": 0,
        "cooldown_time": 1800,
        "api_key_fingerprint": "new",
        "credential_slot": 1,
    }
    assert _info_differ(desired, {})
    assert _info_differ({"supports_vision": False}, {"supports_vision": True})
    assert _info_differ({"allowed_fails": 0}, {"allowed_fails": 5})
    assert _info_differ({"api_key_fingerprint": "new"}, {"api_key_fingerprint": "old"})
    assert not _info_differ(desired, dict(desired))
    # Omitted unknown values stay untouched.
    assert not _info_differ({"supports_vision": None}, {"supports_vision": True})


def test_update_body_carries_capabilities_failover_and_fingerprint():
    desired = {
        "model_name": "pro-tier",
        "litellm_params": {
            "model": "openai/x",
            "order": 2,
            "num_retries": 32,
            "api_key": "raw-key",
        },
        "model_info": {
            "id": "mp::pro-tier::p::key-2::x",
            "supports_vision": True,
            "supports_audio_output": False,
            "allowed_fails": 0,
            "cooldown_time": 1800,
            "api_key_fingerprint": "abc",
            "credential_slot": 2,
            "unknown_server_field": "keep-me-out",
        },
    }
    body = _update_body(desired)
    assert body["litellm_params"]["num_retries"] == 32
    assert body["litellm_params"]["api_key"] == "raw-key"
    for key in ("supports_vision", "supports_audio_output", "allowed_fails",
                "cooldown_time", "api_key_fingerprint", "credential_slot"):
        assert body["model_info"][key] == desired["model_info"][key]
    assert "unknown_server_field" not in body["model_info"]


def test_resolve_payload_credentials_fills_slots_and_leaves_legacy_env_ref():
    from model_pipeline.models import Credential
    from model_pipeline.populate.credentials import resolve_payload_credentials

    cfg = SimpleNamespace(
        provider_credentials=lambda provider: [
            Credential(1, "key-a", "TEST_APIS", raw=True),
            Credential(2, "key-b", "TEST_APIS", raw=True),
        ]
    )
    payload = {
        "tiers": [
            {
                "deployments": [
                    {
                        "provider": "p1",
                        "credential_slot": 2,
                        "litellm_params": {"model": "openai/x"},
                        "model_info": {"id": "mp::key-2"},
                    },
                    {
                        "provider": "p1",
                        "litellm_params": {"model": "openai/x", "api_key": "os.environ/OLD"},
                        "model_info": {"id": "mp::legacy"},
                    },
                ]
            }
        ]
    }
    assert resolve_payload_credentials(payload, cfg) == 1
    deployments = payload["tiers"][0]["deployments"]
    assert deployments[0]["litellm_params"]["api_key"] == "key-b"
    assert deployments[1]["litellm_params"]["api_key"] == "os.environ/OLD"


def _desired(slot, model_id, fingerprint, provider="p1"):
    mid = deployment_id("pro-tier", provider, model_id, slot)
    return {
        "provider": provider,
        "model_uuid": mid,
        "litellm_params": {
            "model_name": "pro-tier",
            "litellm_params": {
                "model": "openai/x",
                "order": 2,
                "num_retries": 32,
                "api_key": "resolved-key",
            },
            "model_info": {
                "id": mid,
                "credential_slot": slot,
                "api_key_fingerprint": fingerprint,
                "allowed_fails": 0,
                "cooldown_time": 1800,
                "supports_vision": True,
            },
        },
    }


class _PlanClient:
    def __init__(self):
        self.calls = []

    def add_model(self, payload):
        self.calls.append(("add", payload["model_info"]["id"]))
        return SimpleNamespace(status_code=200, text="")

    def patch_model(self, model_id, payload):
        self.calls.append(("patch", model_id, payload))
        return SimpleNamespace(status_code=200, text="")

    def delete_model(self, model_id):
        self.calls.append(("delete", model_id))
        return SimpleNamespace(status_code=200, text="")


def test_rotation_patches_in_place_and_removal_deletes_only_that_slot():
    rotated = _desired(2, "x", "new")
    current = [
        {
            "model_info": {
                "id": rotated["litellm_params"]["model_info"]["id"],
                "api_key_fingerprint": "old",
            },
            "litellm_params": {"model": "openai/x", "order": 2, "num_retries": 32},
        },
        {
            "model_info": {"id": "mp::pro-tier::p1::x"},
            "litellm_params": {"model": "openai/x", "order": 2, "num_retries": 32},
        },
    ]
    plan = build_plan({"tiers": [{"deployments": [rotated]}]}, current)
    assert plan.report.updated == [rotated["litellm_params"]["model_info"]["id"]]
    assert plan.report.deleted == ["mp::pro-tier::p1::x"]

    client = _PlanClient()
    report = apply_plan(client, plan)
    assert report.errors == []
    assert client.calls[0][0] == "patch"
    assert client.calls[0][1] == rotated["litellm_params"]["model_info"]["id"]
    assert client.calls[0][2]["model_info"]["api_key_fingerprint"] == "new"
    assert client.calls[1] == ("delete", "mp::pro-tier::p1::x")

    add_plan = build_plan({"tiers": [{"deployments": [rotated]}]}, [])
    add_client = _PlanClient()
    apply_plan(add_client, add_plan)
    assert add_client.calls[0][0] == "add"


def test_param_warnings_flag_stale_stored_reasoning_params_only():
    def payload(model_id="mp::p", supports=True):
        return {
            "tiers": [
                {
                    "deployments": [
                        {
                            "litellm_params": {
                                "model_name": "pro-tier",
                                "litellm_params": {"model": "openai/x", "order": 2},
                                "model_info": {
                                    "id": model_id,
                                    "supports_reasoning": supports,
                                },
                            }
                        }
                    ]
                }
            ]
        }

    stale = [{
        "model_info": {
            "id": "mp::p",
            "supported_openai_params": ["user", "temperature"],
        },
        "litellm_params": {"model": "openai/x", "order": 2},
    }]
    warnings = param_warnings(payload(), stale)
    assert len(warnings) == 1
    assert "reasoning_effort" in warnings[0]
    assert "1.109.1" in warnings[0]

    current_ok = [{
        "model_info": {
            "id": "mp::p",
            "supported_openai_params": ["user", "reasoning_effort"],
        },
        "litellm_params": {"model": "openai/x", "order": 2},
    }]
    assert param_warnings(payload(), current_ok) == []
    # A new row has no stored list; the running proxy computes one.
    assert param_warnings(payload(model_id="mp::new"), current_ok) == []
    # Non-reasoning rows are irrelevant.
    assert param_warnings(payload(supports=False), stale) == []


def test_patch_model_targets_the_patch_endpoint():
    calls = []

    class FakeHttp:
        def patch_json(self, url, headers=None, payload=None):
            calls.append((url, payload))
            return SimpleNamespace(status_code=200, text="")

    cfg = SimpleNamespace(
        litellm=SimpleNamespace(base_url="http://proxy:4000", master_key_env="K"),
        secret=lambda name: "sk-test",
    )
    client = LiteLLMClient(cfg, FakeHttp())
    client.patch_model("mp::pro-tier::commandcode::gpt-6-luna", {"model_info": {"id": "x"}})

    (url, payload), = calls
    assert url == "http://proxy:4000/model/mp::pro-tier::commandcode::gpt-6-luna/update"
    assert payload == {"model_info": {"id": "x"}}
