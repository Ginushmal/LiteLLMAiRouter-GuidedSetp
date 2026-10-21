"""Tests for tier-scoped exclusion and tier-pin configuration."""

from datetime import datetime, timezone

import pytest
import yaml

from model_pipeline.config import (
    PROJECT_ROOT,
    _pin_map,
    _tier_pattern_map,
    _validate_tier_names,
    load_config,
    parse_as_of,
)


def test_tier_pattern_map_accepts_lists_and_nulls():
    assert _tier_pattern_map(None) == {}
    assert _tier_pattern_map({"Pro": ["x"], "Flash": None}) == {
        "Pro": ["x"],
        "Flash": [],
    }
    assert _tier_pattern_map({"Pro": []}) == {"Pro": []}


def test_tier_pattern_map_rejects_a_bare_string():
    # A scalar would be iterated character by character, matching everything.
    with pytest.raises(TypeError, match="must be a list"):
        _tier_pattern_map({"Pro": "gpt-5"})
    with pytest.raises(TypeError, match="must be a mapping"):
        _tier_pattern_map(["Pro"])


def test_unknown_tier_name_names_the_bad_key_and_the_valid_ones():
    with pytest.raises(ValueError) as exc:
        _validate_tier_names({"Ultraa": []}, {"Ultra": 0.8, "Pro": 0.6})
    message = str(exc.value)
    assert "Ultraa" in message
    assert "Ultra" in message and "Pro" in message

    # Missing map and empty list on a real tier are valid.
    _validate_tier_names({}, {"Ultra": 0.8})
    _validate_tier_names({"Ultra": []}, {"Ultra": 0.8})


def test_repo_config_exposes_a_valid_tier_pattern_map():
    cfg = load_config()
    assert isinstance(cfg.exclude_tier_patterns, dict)
    for tier, patterns in cfg.exclude_tier_patterns.items():
        assert tier in cfg.nmb.tier_floors
        assert isinstance(patterns, list)


# -- tier pins -------------------------------------------------------------
def test_pin_map_accepts_ordered_lists_and_nulls():
    assert _pin_map(None) == {}
    assert _pin_map({"Pro": ["a", " b ", ""], "Flash": None}) == {
        "Pro": ["a", "b"],
        "Flash": [],
    }
    assert _pin_map({"Pro": []}) == {"Pro": []}


def test_pin_map_rejects_wrong_shapes():
    # A bare string would be iterated character by character.
    with pytest.raises(TypeError, match="must be a list"):
        _pin_map({"Pro": "gpt-5"})
    with pytest.raises(TypeError, match="must be a mapping"):
        _pin_map(["Pro"])
    with pytest.raises(TypeError, match="slug strings"):
        _pin_map({"Pro": [1]})


def _config_with_pins(tmp_path, pins):
    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    data["pins"] = {"tiers": pins}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_config(path)


def test_load_config_parses_a_populated_pin_map(tmp_path):
    cfg = _config_with_pins(tmp_path, {"Pro": ["a", " b "], "Flash": None})
    assert cfg.pin_slugs == {"Pro": ["a", "b"], "Flash": []}


def test_load_config_rejects_an_unknown_pin_tier(tmp_path):
    with pytest.raises(ValueError) as exc:
        _config_with_pins(tmp_path, {"Ultraa": ["a"]})
    message = str(exc.value)
    assert "pins.tiers" in message
    assert "Ultraa" in message
    assert "Ultra" in message


# -- time-of-day pricing policy ------------------------------------------
def _config_with_pricing(tmp_path, **updates):
    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    for key, value in updates.items():
        data["pricing"][key] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_config(path)


def test_time_price_mode_defaults_to_today(tmp_path):
    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    data["pricing"].pop("time_price_mode", None)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    cfg = load_config(path)
    assert cfg.pricing.time_price_mode == "today"
    assert cfg.pricing.as_of is None

    for mode in ("today", "average", "instant"):
        assert _config_with_pricing(tmp_path, time_price_mode=mode).pricing.time_price_mode == mode


def test_invalid_time_price_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="time_price_mode"):
        _config_with_pricing(tmp_path, time_price_mode="weekly")


def test_as_of_is_parsed_to_aware_utc(tmp_path):
    cfg = _config_with_pricing(tmp_path, as_of="2026-10-22T18:00Z")
    assert cfg.pricing.as_of == datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc)

    cfg = _config_with_pricing(tmp_path, as_of="2026-10-23T00:30+05:30")
    assert cfg.pricing.as_of == datetime(2026, 10, 22, 19, 0, tzinfo=timezone.utc)


def test_as_of_requires_a_timezone(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        _config_with_pricing(tmp_path, as_of="2026-10-22T18:00")


def test_malformed_as_of_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="ISO 8601"):
        _config_with_pricing(tmp_path, as_of="next tuesday")
    with pytest.raises(ValueError, match="ISO 8601"):
        parse_as_of("2026-13-40T99:99Z")


# -- missing config file ---------------------------------------------------
def test_missing_config_names_the_example_template(tmp_path):
    # A fresh checkout has only config.example.yaml; the failure must say how
    # to bootstrap instead of raising a raw file-not-found.
    with pytest.raises(FileNotFoundError) as exc:
        load_config(tmp_path / "config.yaml")
    message = str(exc.value)
    assert "config.example.yaml" in message
    assert "copy config.example.yaml config.yaml" in message
    assert str(tmp_path / "config.yaml") in message


def test_example_template_stays_loadable():
    # The tracked template must always parse through the real loader, so a new
    # person's first `copy config.example.yaml config.yaml` cannot fail.
    cfg = load_config(PROJECT_ROOT / "config.example.yaml")
    assert cfg.nmb.tier_names
    assert cfg.providers
