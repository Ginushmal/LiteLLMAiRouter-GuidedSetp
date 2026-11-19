"""Provider-only capability metadata from the models.dev catalog.

Capabilities describe what a *serving provider* accepts, so resolution never
falls back to another provider's entry (unlike token limits, which are model
properties). Unknown fields stay absent; an explicit ``false`` is written only
when the provider's entry declares the modality/capability false.

The per-level reasoning flags are intentionally broader than LiteLLM's own
type: ``supports_medium_reasoning_effort`` and
``supports_high_reasoning_effort`` pass through ``model_info`` and are read by
client integrations such as OpenCode's model-discovery plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from model_pipeline.limits import LimitResolver
from model_pipeline.models import RawModel

FLAG_UNRESOLVED = "unresolved"
FLAG_MODALITIES_MISSING = "modalities_missing"
FLAG_REASONING_LEVELS_MISSING = "reasoning_levels_missing"
FLAG_NON_CHAT_OUTPUT = "non_chat_output"

INPUT_MODALITIES = ("text", "image", "pdf", "audio", "video")
OUTPUT_MODALITIES = ("text", "image", "pdf", "audio", "video")
REASONING_LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
REASONING_FLAGS = {
    level: f"supports_{level}_reasoning_effort" for level in REASONING_LEVELS
}


@dataclass
class ResolvedCapabilities:
    """LiteLLM ``model_info`` fields plus where they came from."""

    fields: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    flags: list[str] = field(default_factory=list)


def _string_list(value: Any, allowed: tuple[str, ...]) -> list[str] | None:
    """Normalize a modality declaration; None when it is not a list."""
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip().lower()
        if normalized == "speech":
            normalized = "audio"
        if normalized in allowed and normalized not in result:
            result.append(normalized)
    return result


def _effort_levels(entry: dict[str, Any]) -> list[str]:
    """Published effort values in canonical order (empty when none)."""
    published: set[str] = set()
    options = entry.get("reasoning_options")
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict) or option.get("type") != "effort":
                continue
            values = option.get("values")
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and value in REASONING_LEVELS:
                    published.add(value)
    return [level for level in REASONING_LEVELS if level in published]


def resolve_entry(
    entry: dict[str, Any] | None, source: str
) -> ResolvedCapabilities:
    """Map one provider catalog entry to LiteLLM capability fields."""
    if entry is None:
        return ResolvedCapabilities(source="unresolved", flags=[FLAG_UNRESOLVED])

    capabilities: dict[str, Any] = {}
    flags: list[str] = []

    modalities = entry.get("modalities")
    input_modalities = _string_list(
        modalities.get("input") if isinstance(modalities, dict) else None,
        INPUT_MODALITIES,
    )
    output_modalities = _string_list(
        modalities.get("output") if isinstance(modalities, dict) else None,
        OUTPUT_MODALITIES,
    )

    if input_modalities is None and output_modalities is None:
        flags.append(FLAG_MODALITIES_MISSING)
    else:
        declared: dict[str, list[str]] = {}
        if input_modalities is not None:
            declared["input"] = input_modalities
        if output_modalities is not None:
            declared["output"] = output_modalities
        capabilities["modalities"] = declared

        if input_modalities is not None:
            capabilities["supports_vision"] = "image" in input_modalities
            capabilities["supports_pdf_input"] = "pdf" in input_modalities
            capabilities["supports_audio_input"] = "audio" in input_modalities
            capabilities["supports_video_input"] = "video" in input_modalities

        if output_modalities is not None:
            # The output list is closed: omitting audio is a declared false.
            capabilities["supports_audio_output"] = "audio" in output_modalities
            if "text" not in output_modalities:
                flags.append(FLAG_NON_CHAT_OUTPUT)

    if isinstance(entry.get("tool_call"), bool):
        capabilities["supports_function_calling"] = entry["tool_call"]
    if isinstance(entry.get("structured_output"), bool):
        capabilities["supports_response_schema"] = entry["structured_output"]

    reasoning = entry.get("reasoning")
    if reasoning is False:
        capabilities["supports_reasoning"] = False
        capabilities["reasoning_effort_levels"] = []
        for flag in REASONING_FLAGS.values():
            capabilities[flag] = False
    elif reasoning is True:
        capabilities["supports_reasoning"] = True
        levels = _effort_levels(entry)
        capabilities["reasoning_effort_levels"] = levels
        if levels:
            for flag in REASONING_FLAGS.values():
                capabilities[flag] = False
            for level in levels:
                capabilities[REASONING_FLAGS[level]] = True
        else:
            # No published levels: omit the seven flags so a client may apply
            # its own default; the reason is visible in the artifact.
            flags.append(FLAG_REASONING_LEVELS_MISSING)

    return ResolvedCapabilities(fields=capabilities, source=source, flags=flags)


def apply_capabilities(
    models: list[RawModel],
    resolver: LimitResolver | None,
    provider_ids: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Annotate each model with provider-only capabilities.

    Returns ``provider:model -> flags`` for the report. A model whose output
    modalities exclude text is flagged ``non_chat_output`` and is later skipped
    by the chat pipeline.
    """
    flagged: dict[str, list[str]] = {}
    for model in models:
        ids = provider_ids.get(model.provider) or [model.provider]
        entry, source = (
            resolver.provider_entry(ids, model.model_id)
            if resolver is not None
            else (None, "")
        )
        resolved = resolve_entry(entry, source)
        model.capabilities = resolved.fields
        model.capabilities_source = resolved.source
        model.capabilities_flags = list(resolved.flags)
        if resolved.flags:
            flagged[f"{model.provider}:{model.model_id}"] = list(resolved.flags)
    return flagged
