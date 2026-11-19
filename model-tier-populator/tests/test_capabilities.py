"""Tests for provider-only capability resolution and reasoning policy."""

from model_pipeline.capabilities import (
    FLAG_MODALITIES_MISSING,
    FLAG_NON_CHAT_OUTPUT,
    FLAG_REASONING_LEVELS_MISSING,
    FLAG_UNRESOLVED,
    REASONING_FLAGS,
    apply_capabilities,
    resolve_entry,
)
from model_pipeline.limits import LimitResolver
from model_pipeline.models import RawModel


def _entry(**overrides):
    entry = {
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
        "tool_call": True,
        "structured_output": True,
        "reasoning": True,
        "reasoning_options": [
            {"type": "effort", "values": ["low", "high", "max"]}
        ],
    }
    entry.update(overrides)
    return entry


def test_full_capability_mapping():
    resolved = resolve_entry(_entry(), "models.dev:ours")
    fields = resolved.fields

    assert fields["modalities"] == {
        "input": ["text", "image", "pdf"],
        "output": ["text"],
    }
    assert fields["supports_vision"] is True
    assert fields["supports_pdf_input"] is True
    assert fields["supports_audio_input"] is False
    assert fields["supports_video_input"] is False
    assert fields["supports_function_calling"] is True
    assert fields["supports_response_schema"] is True
    assert fields["supports_audio_output"] is False
    assert fields["supports_reasoning"] is True
    assert fields["reasoning_effort_levels"] == ["low", "high", "max"]
    assert fields[REASONING_FLAGS["low"]] is True
    assert fields[REASONING_FLAGS["high"]] is True
    assert fields[REASONING_FLAGS["max"]] is True
    assert fields[REASONING_FLAGS["medium"]] is False
    assert fields[REASONING_FLAGS["none"]] is False
    assert resolved.flags == []
    assert resolved.source == "models.dev:ours"


def test_text_only_declares_false_media_flags():
    resolved = resolve_entry(
        {"modalities": {"input": ["text"], "output": ["text"]}}, "models.dev:ours"
    )
    assert resolved.fields["supports_vision"] is False
    assert resolved.fields["supports_pdf_input"] is False
    assert resolved.fields["supports_audio_input"] is False
    assert resolved.fields["supports_video_input"] is False


def test_missing_modalities_is_flagged_and_not_invented():
    resolved = resolve_entry({"attachment": True}, "models.dev:ours")
    assert "modalities" not in resolved.fields
    assert "supports_vision" not in resolved.fields
    assert FLAG_MODALITIES_MISSING in resolved.flags


def test_audio_output_is_true_when_declared_and_false_when_omitted():
    declared = resolve_entry(
        {"modalities": {"input": ["text"], "output": ["text", "audio"]}},
        "models.dev:ours",
    )
    assert declared.fields["supports_audio_output"] is True

    omitted = resolve_entry(
        {"modalities": {"input": ["text"], "output": ["text"]}},
        "models.dev:ours",
    )
    assert omitted.fields["supports_audio_output"] is False

    unknown = resolve_entry(
        {"modalities": {"input": ["text"]}}, "models.dev:ours"
    )
    assert "supports_audio_output" not in unknown.fields


def test_non_text_output_is_flagged():
    resolved = resolve_entry(
        {"modalities": {"input": ["text"], "output": ["image"]}}, "models.dev:ours"
    )
    assert FLAG_NON_CHAT_OUTPUT in resolved.flags


def test_reasoning_false_emits_empty_levels_and_all_flags_false():
    resolved = resolve_entry({"reasoning": False}, "models.dev:ours")
    assert resolved.fields["supports_reasoning"] is False
    assert resolved.fields["reasoning_effort_levels"] == []
    for flag in REASONING_FLAGS.values():
        assert resolved.fields[flag] is False


def test_reasoning_without_effort_levels_omits_flags_and_keeps_client_default():
    resolved = resolve_entry({"reasoning": True, "reasoning_options": [{"type": "toggle"}]}, "models.dev:ours")
    assert resolved.fields["supports_reasoning"] is True
    assert resolved.fields["reasoning_effort_levels"] == []
    for flag in REASONING_FLAGS.values():
        assert flag not in resolved.fields
    assert FLAG_REASONING_LEVELS_MISSING in resolved.flags


def test_missing_provider_entry_is_unresolved_without_cross_provider_fallback():
    catalog = {
        "other": {"models": {"gpt-x": _entry()}},
    }
    resolver = LimitResolver(catalog)
    model = RawModel(provider="ours", model_id="gpt-x", display_name="GPT X")
    flagged = apply_capabilities([model], resolver, {"ours": ["ours"]})

    assert model.capabilities == {}
    assert model.capabilities_source == "unresolved"
    assert model.capabilities_flags == [FLAG_UNRESOLVED]
    assert flagged == {"ours:gpt-x": [FLAG_UNRESOLVED]}


def test_provider_entry_exact_then_normalized():
    catalog = {
        "ours": {
            "models": {
                "gpt-x": _entry(),
                "gpt-y-latest": {"modalities": {"input": ["text"], "output": ["text"]}},
            }
        }
    }
    resolver = LimitResolver(catalog, strip_suffixes=["-latest"])

    entry, source = resolver.provider_entry(["ours"], "gpt-x")
    assert entry is not None and source == "models.dev:ours"

    # Normalization strips the -latest suffix and matches within our provider.
    entry, source = resolver.provider_entry(["ours"], "gpt-y")
    assert entry is not None and source == "models.dev:ours"


def test_apply_capabilities_sets_fields_on_raw_models():
    catalog = {"ours": {"models": {"gpt-x": _entry()}}}
    resolver = LimitResolver(catalog)
    model = RawModel(provider="ours", model_id="gpt-x", display_name="GPT X")

    apply_capabilities([model], resolver, {"ours": ["ours"]})
    assert model.capabilities["supports_vision"] is True
    assert model.capabilities_source == "models.dev:ours"
    assert model.capabilities_flags == []
