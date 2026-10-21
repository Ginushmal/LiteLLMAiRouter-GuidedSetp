"""Tests for models.dev token-limit resolution, derivation, and flags."""

from types import SimpleNamespace

from model_pipeline.limits import (
    FLAG_OUTPUT_EQUALS_CONTEXT,
    FLAG_OUTPUT_NOT_BELOW_CONTEXT,
    FLAG_UNRESOLVED,
    LimitResolver,
    apply_limits,
    normalize_model_id,
)
from model_pipeline.models import RawModel, ResolvedPricing
from model_pipeline.providers.base import ProviderAdapter

STRIP = ["-latest", ":free", "-free", " (latest)"]
SPEED = ["-fast", "-ultraspeed"]

CATALOG = {
    # The pipeline's own provider.
    "ours": {
        "models": {
            "gpt-6-luna": {"limit": {"context": 1050000, "input": 922000, "output": 128000}},
            # Entry exists but publishes no limit -> must fall through.
            "no-limits-model": {"limit": None},
            # Same id under our provider and another one: ours must win.
            "shared-model": {"limit": {"context": 100, "output": 10}},
            # Copied-looking entry (output == context).
            "copied-model": {"limit": {"context": 4096, "output": 4096}},
        }
    },
    "other-reseller": {
        "models": {
            "shared-model": {"limit": {"context": 200, "output": 20}},
            "vendor/model-x": {"limit": {"context": 1000, "output": 100}},
            "no-limits-model": {"limit": {"context": 800, "output": 50}},
        }
    },
    # The model vendor's own entries (unprefixed ids, like xiaomi's).
    "vendor": {
        "models": {
            "model-x": {"limit": {"context": 1000, "output": 200}},
        }
    },
}


def _resolver() -> LimitResolver:
    return LimitResolver(CATALOG, STRIP, SPEED)


# -- resolution order -----------------------------------------------------
def test_provider_entry_wins_over_other_providers():
    limits = _resolver().resolve(["ours"], "shared-model")
    assert limits.output == 10
    assert limits.source == "models.dev:ours"


def test_provider_entry_without_a_limit_falls_through():
    resolver = _resolver()
    # our entry publishes nothing -> another provider's same-id entry is used
    limits = resolver.resolve(["ours"], "no-limits-model")
    assert limits.output == 50
    assert limits.source == "models.dev-fallback:other-reseller"


def test_normalized_match_prefers_the_model_vendors_entry():
    # `vendor/model-x` is exact-matching under the reseller, normalized under
    # both; the vendor's own value (200) must win over the reseller's (100).
    limits = _resolver().resolve(["ours"], "vendor/model-x")
    assert limits.output == 200
    assert limits.source == "models.dev-fallback:vendor"


def test_unrelated_provider_entry_is_used_when_no_vendor_entry_exists():
    limits = _resolver().resolve(["ours"], "gpt-6-luna")
    assert limits.source == "models.dev:ours"
    # A model known only under a third party resolves from there (stable order).
    limits = _resolver().resolve(["nobody"], "shared-model")
    assert limits.output == 20
    assert limits.source == "models.dev-fallback:other-reseller"


def test_unresolved_when_nothing_publishes_an_output_limit():
    limits = _resolver().resolve(["ours"], "not-in-the-catalog")
    assert limits.output is None
    assert limits.source == ""
    assert limits.flags == [FLAG_UNRESOLVED]


def test_output_equals_context_is_flagged():
    limits = _resolver().resolve(["ours"], "copied-model")
    assert limits.output == 4096
    assert FLAG_OUTPUT_EQUALS_CONTEXT in limits.flags


# -- normalization --------------------------------------------------------
def test_normalization_ignores_case_punctuation_prefix_and_suffixes():
    assert normalize_model_id("Google/Gemini-4-Argon", STRIP, SPEED) == "gemini4argon"
    assert normalize_model_id("gemini 4 argon", STRIP, SPEED) == "gemini4argon"
    assert normalize_model_id("gemini-4-argon:free", STRIP, SPEED) == "gemini4argon"
    # "v" is just part of the version string, not punctuation.
    assert normalize_model_id("mimo-v2.6-pro-ultraspeed", STRIP, SPEED) == "mimov26pro"
    assert normalize_model_id("GPT-6.1-Sol", STRIP, SPEED) == "gpt61sol"


# -- derivation + application --------------------------------------------
def _model(model_id: str = "gpt-6-luna", **kwargs) -> RawModel:
    return RawModel(provider="ours", model_id=model_id, display_name="GPT 6", **kwargs)


def test_apply_limits_derives_input_from_context_minus_output():
    model = _model(context_tokens=1050000)
    flagged = apply_limits([model], _resolver(), {"ours": ["ours"]})
    assert (model.output_tokens, model.input_tokens) == (128000, 922000)
    assert model.limits_source == "models.dev:ours"
    assert flagged == {}


def test_apply_limits_leaves_input_unknown_without_provider_context():
    # OpenCode publishes no context window: the output cap is still truthful,
    # but the input limit must stay unset rather than be guessed.
    model = _model()
    apply_limits([model], _resolver(), {"ours": ["ours"]})
    assert model.output_tokens == 128000
    assert model.input_tokens is None
    assert model.limits_flags == []


def test_apply_limits_flags_output_not_below_context():
    model = _model(context_tokens=150)
    model.model_id = "vendor/model-x"
    apply_limits([model], _resolver(), {"ours": ["ours"]})
    assert model.output_tokens == 200
    assert model.input_tokens is None
    assert FLAG_OUTPUT_NOT_BELOW_CONTEXT in model.limits_flags


def test_apply_limits_never_invents_a_value():
    model = _model(model_id="not-in-the-catalog", context_tokens=1000)
    flagged = apply_limits([model], _resolver(), {"ours": ["ours"]})
    assert model.output_tokens is None
    assert model.input_tokens is None
    assert model.limits_source == ""
    assert flagged == {"ours:not-in-the-catalog": [FLAG_UNRESOLVED]}


def test_apply_limits_without_catalog_flags_everything_unresolved():
    model = _model(context_tokens=1000)
    flagged = apply_limits([model], None, {"ours": ["ours"]})
    assert model.output_tokens is None
    assert flagged["ours:gpt-6-luna"] == [FLAG_UNRESOLVED]


def test_free_plan_suffix_resolves_to_base_model_limits():
    # OpenRouter publishes `:free` variants of the same model under a suffixed
    # id; models.dev has the base id, so the normalized fallback must find it.
    catalog = {
        "openrouter": {
            "models": {
                "acme/alpha-1": {"limit": {"context": 200000, "output": 64000}},
            }
        }
    }
    resolver = LimitResolver(catalog, STRIP, SPEED)
    limits = resolver.resolve(["openrouter"], "acme/alpha-1:free")
    assert limits.output == 64000
    assert limits.source == "models.dev:openrouter"

    model = RawModel(
        provider="openrouter",
        model_id="acme/alpha-1:free",
        display_name="Acme: Alpha 1 (free)",
        context_tokens=200000,
    )
    apply_limits([model], resolver, {"openrouter": ["openrouter"]})
    assert model.output_tokens == 64000
    assert model.input_tokens == 136000


# -- artifacts ------------------------------------------------------------
def test_limits_round_trip_through_the_snapshot():
    from model_pipeline.emit.snapshot import models_from_json, models_to_json

    model = _model(context_tokens=1050000)
    apply_limits([model], _resolver(), {"ours": ["ours"]})

    restored = models_from_json(models_to_json([model]))[0]
    assert (restored.output_tokens, restored.input_tokens) == (128000, 922000)
    assert restored.limits_source == "models.dev:ours"
    assert restored.limits_flags == []


class _Adapter(ProviderAdapter):
    """Minimal adapter for exercising the shared payload assembly."""

    name = "ours"
    pcfg = SimpleNamespace(api_key_env="K", extra_headers={}, litellm={})

    def __init__(self) -> None:  # skip the real adapter setup
        pass

    def fetch_models(self) -> list[RawModel]:
        return []

    def fetch_pricing(self):
        return {}

    def to_litellm_deployment(self, model, pricing, model_group, order):  # pragma: no cover
        raise NotImplementedError


def _model_info(model: RawModel) -> dict:
    payload = _Adapter()._assemble(
        model, ResolvedPricing(input=1.0, output=2.0), "pro-tier", 1,
        f"openai/{model.model_id}", "https://api.example/v1",
    )
    return payload["model_info"]


def test_payload_emits_the_three_limit_fields():
    model = _model(context_tokens=1050000)
    apply_limits([model], _resolver(), {"ours": ["ours"]})

    info = _model_info(model)
    assert info["max_input_tokens"] == 922000
    assert info["max_output_tokens"] == 128000
    assert info["max_tokens"] == 128000
    assert info["id"] == "mp::pro-tier::ours::gpt-6-luna"


def test_payload_omits_limits_when_unresolved():
    model = _model(model_id="not-in-the-catalog", context_tokens=1050000)
    apply_limits([model], _resolver(), {"ours": ["ours"]})

    info = _model_info(model)
    assert "max_input_tokens" not in info
    assert "max_output_tokens" not in info
    assert "max_tokens" not in info


def test_report_lists_token_limit_flags():
    from model_pipeline.emit.report import build_report
    from model_pipeline.scoring.pipeline import ScoreResult

    result = ScoreResult(
        generated_at="now",
        sota_intelligence=1.0,
        tiers=[],
        excluded={},
        parameters={"top_k_per_tier": 5, "latency_penalty_mu": 0.0},
        cost_methods={},
        pareto_kept=0,
        pareto_dropped=0,
        limit_flags={"opencode:omen-alpha": [FLAG_UNRESOLVED]},
    )
    report = build_report(result, cfg=None)
    assert "## Token limits" in report
    assert "opencode:omen-alpha" in report
    assert FLAG_UNRESOLVED in report
