"""Tests for tier-scoped exclusion and tier-pin configuration."""

import pytest
import yaml

from model_pipeline.config import (
    PROJECT_ROOT,
    _pin_map,
    _tier_pattern_map,
    _validate_tier_names,
    load_config,
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
