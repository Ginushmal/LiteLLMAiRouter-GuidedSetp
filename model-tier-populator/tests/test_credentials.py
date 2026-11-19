"""Tests for provider key-list parsing and credential identity."""

import json

import pytest

from model_pipeline.config import (
    PROJECT_ROOT,
    load_config,
    parse_key_list,
)
from model_pipeline.models import fingerprint_key


def test_json_list_preserves_commas_quotes_and_backslashes():
    raw = json.dumps(["key,one", 'key"two', "key\\three", "key,one", ""])
    keys = parse_key_list(raw)
    assert keys == ["key,one", 'key"two', "key\\three"]


def test_comma_fallback_is_trimmed_and_deduplicated():
    warnings = []
    keys = parse_key_list(" a, b ,, a ", "TEST_APIS", warnings)
    assert keys == ["a", "b"]
    assert warnings and "duplicate" in warnings[0]


def test_invalid_json_is_rejected():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_key_list("[\"unterminated\"", "TEST_APIS")


def test_non_array_json_is_rejected():
    with pytest.raises(ValueError, match="JSON array"):
        parse_key_list('{"key":"value"}', "TEST_APIS")


def _cfg_with_provider(**updates):
    cfg = load_config(PROJECT_ROOT / "config.example.yaml")
    pcfg = cfg.providers["commandcode"]
    pcfg.enabled = True
    pcfg.api_keys_env = "TEST_APIS"
    pcfg.api_key_env = ""
    cfg.env = {}
    for key, value in updates.items():
        setattr(pcfg, key, value)
    return cfg, pcfg


def test_provider_credentials_parse_json_list_with_slots_and_fingerprints():
    cfg, _ = _cfg_with_provider()
    cfg.env = {"TEST_APIS": '["key-a","key-b","key-a",""]'}

    creds = cfg.provider_credentials("commandcode")
    assert [c.slot for c in creds] == [1, 2]
    assert [c.value for c in creds] == ["key-a", "key-b"]
    assert [c.raw for c in creds] == [True, True]
    assert creds[0].fingerprint == fingerprint_key("key-a")
    assert len(creds[0].fingerprint) == 16
    assert any("duplicate" in warning for warning in cfg.warnings)


def test_provider_credentials_keep_legacy_single_key_env_reference():
    cfg, _ = _cfg_with_provider()
    cfg.providers["commandcode"].api_keys_env = ""
    cfg.providers["commandcode"].api_key_env = "TEST_KEY"
    cfg.env = {"TEST_KEY": "only-key"}

    (cred,) = cfg.provider_credentials("commandcode")
    assert cred.slot == 1
    assert cred.raw is False
    assert cred.env_name == "TEST_KEY"
    assert cred.fingerprint == fingerprint_key("only-key")


def test_provider_credentials_fall_back_to_process_environment(monkeypatch):
    cfg, _ = _cfg_with_provider()
    cfg.env = {}
    monkeypatch.setenv("TEST_APIS", '["shell-key"]')
    (cred,) = cfg.provider_credentials("commandcode")
    assert cred.value == "shell-key"


def test_provider_credentials_fail_for_enabled_provider_with_missing_list():
    cfg, _ = _cfg_with_provider()
    cfg.env = {}
    with pytest.raises(RuntimeError, match="api_keys_env"):
        cfg.provider_credentials("commandcode")


def test_disabled_provider_returns_no_credentials():
    cfg, pcfg = _cfg_with_provider()
    pcfg.enabled = False
    assert cfg.provider_credentials("commandcode") == []


def test_credential_repr_never_contains_the_raw_key():
    cfg, _ = _cfg_with_provider()
    cfg.env = {"TEST_APIS": '["sk-super-secret"]'}
    (cred,) = cfg.provider_credentials("commandcode")
    assert "sk-super-secret" not in repr(cred)
    assert "sk-super-secret" not in str(cred)
