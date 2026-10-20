"""Tests for diff-based population comparison and the PATCH update path."""

from types import SimpleNamespace

from model_pipeline.models import deployment_id
from model_pipeline.populate.litellm_client import LiteLLMClient
from model_pipeline.populate.sync import _info_differ, _params_differ, _update_body


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
