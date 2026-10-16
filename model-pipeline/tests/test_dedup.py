"""Tests for dedup normalization, variant matching, and mappings CSV."""

import csv
from pathlib import Path

from model_pipeline.dedup.mappings_csv import FIELDS, read_mappings, write_mappings
from model_pipeline.dedup.normalize import CanonicalIndex, normalize_key
from model_pipeline.dedup.prefilter import shortlist
from model_pipeline.dedup.variant import parse_variant
from model_pipeline.models import CanonicalModel, Mapping

EFFORT = ["high", "highspeed", "max", "xhigh", "medium", "low", "thinking", "reasoning"]


# -- normalization --------------------------------------------------------
def test_normalize_strips_prefix_paren_date_suffix():
    assert normalize_key("openai/xiaomi/mimo-v2.6-pro") == "mimov26pro"
    assert normalize_key("Claude Sonnet 5.5 (latest)") == "claudesonnet55"
    assert normalize_key("claude-haiku-4-5-20251001") == "claudehaiku45"
    assert normalize_key("deepseek/deepseek-v4.1-flash:free", [":free"]) == "deepseekv41flash"


def test_exact_prefers_slug_over_ambiguous_name():
    # Two AA variants share a display name once the parenthetical is dropped.
    models = [
        CanonicalModel(slug="claude-sonnet-5-5", name="Claude Sonnet 5.5 (Max, Default Fallback)"),
        CanonicalModel(slug="claude-sonnet-5-5-medium", name="Claude Sonnet 5.5 (Medium, Default Fallback)"),
    ]
    idx = CanonicalIndex(models, [])
    assert idx.exact("claude-sonnet-5-5").slug == "claude-sonnet-5-5"


def test_exact_none_when_ambiguous_name_only():
    models = [
        CanonicalModel(slug="x-a", name="Model X (High)"),
        CanonicalModel(slug="x-b", name="Model X (Low)"),
    ]
    idx = CanonicalIndex(models, [])
    # "model-x" doesn't match either slug and the name is ambiguous -> None
    assert idx.exact("model-x") is None


# -- variant parsing (decorates option text; Jev disambiguates) -----------
def test_parse_variant_extracts_signals():
    assert parse_variant("Qwen3-4B", EFFORT).params == "4b"
    assert parse_variant("Qwen3-26B", EFFORT).params == "26b"
    assert parse_variant("MiMo-2.6-high", EFFORT).effort == "high"
    assert parse_variant("MiMo-2.6", EFFORT).effort is None
    assert parse_variant("gpt-oss-20b (high)", EFFORT).label() == "20b+high"


# -- shortlist (name-only, no variant filter) -----------------------------
def test_shortlist_keeps_candidate_with_effort_parenthetical():
    # Regression: the old strict variant filter dropped this candidate, so Jev
    # never saw it and returned "unmapped".
    models = [
        CanonicalModel(slug="claude-haiku-4-5", name="Claude Haiku 4.5 (Max, Default Fallback)"),
        CanonicalModel(slug="claude-3-haiku", name="Claude 3 Haiku"),
        CanonicalModel(slug="claude-3-5-haiku", name="Claude 3.5 Haiku"),
    ]
    result = shortlist("claude-haiku-4-5", models, size=80, strip_suffixes=[])
    assert "claude-haiku-4-5" in [m.slug for m in result]


# -- relaxed exact match (serving / version suffixes) ---------------------
SPEED = ["-fast", "-highspeed", "-ultraspeed", "-turbo"]


def test_exact_maps_serving_token_to_base():
    models = [CanonicalModel(slug="mimo-v2-6-pro", name="MiMo V2.6 Pro")]
    idx = CanonicalIndex(models, [], speed_suffixes=SPEED)
    assert idx.exact("xiaomi/mimo-v2.6-pro-ultraspeed").slug == "mimo-v2-6-pro"


def test_exact_speed_suffix_is_case_insensitive():
    models = [CanonicalModel(slug="qwen3-8-max", name="Qwen3.8 Max")]
    idx = CanonicalIndex(models, [], speed_suffixes=["-Prime"])
    assert idx.exact("Qwen/Qwen3.8-Max-Prime").slug == "qwen3-8-max"


def test_exact_distinct_fast_entry_wins_full_name():
    # grok-4-fast is its own model; it must not collapse into grok-4.
    models = [
        CanonicalModel(slug="grok-4", name="Grok 4"),
        CanonicalModel(slug="grok-4-fast", name="Grok 4 Fast"),
    ]
    idx = CanonicalIndex(models, [], speed_suffixes=SPEED)
    assert idx.exact("grok-4-fast").slug == "grok-4-fast"
    assert idx.exact("grok-4").slug == "grok-4"


def test_exact_strips_next_version_suffix():
    models = [CanonicalModel(slug="qwen3-8-flash-next", name="Qwen3.8 Flash")]
    idx = CanonicalIndex(models, ["-latest", "-next"])
    assert idx.exact("Qwen/Qwen3.8-Flash").slug == "qwen3-8-flash-next"


# -- mappings CSV ---------------------------------------------------------
def test_mappings_csv_roundtrip_and_override(tmp_path: Path):
    maps = [
        Mapping("commandcode", "claude-sonnet-5-5", "claude-sonnet-5-5", "Claude Sonnet 5.5", "", "exact", 1.0),
        Mapping("opencode", "glm-5.3-flash", "glm-5-3-flash", "GLM-5.3 Flash", "", "jev", 0.55, low_confidence=True),
    ]
    path = tmp_path / "mappings.csv"
    write_mappings(path, maps)

    # Header is present and human-readable.
    with path.open(encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == FIELDS

    # A reviewer fixes the low-confidence row via the override column.
    rows = read_mappings(path)
    assert rows[1].low_confidence and rows[1].effective_slug == "glm-5-3-flash"
    rows[1].override = "glm-5-3-flash"
    write_mappings(path, rows)

    reloaded = read_mappings(path)
    assert reloaded[1].override == "glm-5-3-flash"
    assert reloaded[1].effective_slug == "glm-5-3-flash"
