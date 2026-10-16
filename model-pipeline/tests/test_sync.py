"""Tests for diff-based population comparison."""

from model_pipeline.populate.sync import _params_differ


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
