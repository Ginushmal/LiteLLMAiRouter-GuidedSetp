"""Tests for score wiring, the refresh verb, and LiteLLM independence.

All tests are offline: provider adapters, the Artificial Analysis client,
and the models.dev catalog are faked, and no LiteLLM server is contacted.
"""

from types import SimpleNamespace

from model_pipeline import cli
from model_pipeline.config import load_config
from model_pipeline.dedup.mappings_csv import write_mappings
from model_pipeline.emit.html_report import build_html
from model_pipeline.emit.report import build_report
from model_pipeline.emit.snapshot import write_snapshot
from model_pipeline.models import CanonicalModel, Mapping, RawModel, ResolvedPricing
from model_pipeline.scoring import pipeline as scoring_pipeline


class _StubAdapter:
    """Minimal provider adapter so score() needs no network or LiteLLM."""

    pcfg = SimpleNamespace(api_key_env="TEST_KEY")

    def to_litellm_deployment(self, model, pricing, model_group, order):
        return {
            "model_name": model_group,
            "litellm_params": {"api_base": "http://stub"},
            "model_info": {"id": f"mp::{model_group}::{model.model_id}"},
        }


class _StubAaClient:
    def __init__(self, *args, **kwargs):
        pass

    def canonical_models(self, use_cache=True):
        return [
            CanonicalModel(
                slug="a", name="A", intelligence=50, latency_seconds=10,
                aa_input=1.0, aa_output=2.0,
            ),
            CanonicalModel(
                slug="b", name="B", intelligence=40, latency_seconds=20,
                aa_input=1.0, aa_output=2.0,
            ),
        ]


def _fixtures():
    mappings = [
        Mapping(provider="p1", model_id="a-p1", canonical_slug="a", canonical_name="A"),
        Mapping(
            provider="p1", model_id="b-p1", canonical_slug="b", canonical_name="B",
            confidence=0.2, low_confidence=True,
        ),
    ]
    models = [
        RawModel(
            provider="p1", model_id="a-p1", display_name="A",
            pricing=ResolvedPricing(input=1.0, output=2.0),
        ),
        RawModel(
            provider="p1", model_id="b-p1", display_name="B",
            pricing=ResolvedPricing(input=1.0, output=2.0),
        ),
    ]
    return mappings, models


def _score_cfg(tmp_path, monkeypatch):
    """Real config with artifact dirs redirected and secrets emptied.

    Emptying ``env`` proves fetch/score/refresh never require any secret —
    including the LiteLLM master key — and no LiteLLM server.
    """
    cfg = load_config()
    cfg.output_dir = tmp_path / "output"
    cfg.raw_dir = tmp_path / "raw"
    cfg.logs_dir = tmp_path / "logs"
    cfg.env = {}
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    monkeypatch.setattr(cli, "load_config", lambda *args, **kwargs: cfg)
    monkeypatch.setattr("model_pipeline.scoring.aa.AaClient", _StubAaClient)
    monkeypatch.setattr(
        "model_pipeline.providers.registry.build_adapters",
        lambda cfg, http, recorder: [SimpleNamespace(name="p1")],
    )
    # score() builds its own adapter map from these names; give it the stub.
    real_score = scoring_pipeline.score
    monkeypatch.setattr(
        scoring_pipeline, "score",
        lambda mappings, models_index, canonical, adapters, cfg: real_score(
            mappings, models_index, canonical, {"p1": _StubAdapter()}, cfg
        ),
    )
    monkeypatch.setattr(
        "model_pipeline.limits.fetch_catalog", lambda cfg, http, recorder: None
    )
    return cfg


def _write_inputs(cfg):
    mappings, models = _fixtures()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    write_mappings(cfg.output_dir / "mappings.csv", mappings)
    write_snapshot(cfg.output_dir / "models_snapshot.json", models)
    return mappings


def test_score_writes_tier_report_html(tmp_path, monkeypatch):
    cfg = _score_cfg(tmp_path, monkeypatch)
    _write_inputs(cfg)

    assert cli.cmd_score(SimpleNamespace(config=None, as_of=None)) == 0

    assert (cfg.output_dir / "tier-output.json").exists()
    assert (cfg.output_dir / "tier-report.html").exists()
    page = (cfg.output_dir / "tier-report.html").read_text(encoding="utf-8")
    assert "Model pipeline — tier report" in page
    assert "ultra-tier" in page


def test_score_needs_no_secrets_and_no_litellm(tmp_path, monkeypatch, capsys):
    """The LiteLLM-independence regression test: empty env still scores."""
    cfg = _score_cfg(tmp_path, monkeypatch)
    _write_inputs(cfg)

    assert cli.cmd_score(SimpleNamespace(config=None, as_of=None)) == 0
    out = capsys.readouterr().out
    assert "score complete" in out


def test_low_confidence_banner_parity():
    rows = [
        Mapping(
            provider="p1", model_id="b-p1", canonical_slug="b",
            canonical_name="B", confidence=0.2, low_confidence=True,
        )
    ]
    from model_pipeline.scoring.pipeline import ScoreResult

    result = ScoreResult(
        generated_at="2026-10-23T17:01:53+00:00",
        sota_intelligence=50.0,
        tiers=[],
        excluded={},
        parameters={"top_k_per_tier": 10},
        cost_methods={},
        pareto_kept=0,
        pareto_dropped=0,
    )
    assert "low-confidence mapping" in build_report(result, None, rows)
    assert "low-confidence mapping" in build_html(result, rows)
    assert "low-confidence mapping" not in build_report(result, None)
    assert "low-confidence mapping" not in build_html(result)


def test_refresh_runs_fetch_then_score_and_never_populate(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli, "cmd_fetch", lambda args: calls.append("fetch") or 0
    )
    monkeypatch.setattr(
        cli, "cmd_score", lambda args: calls.append("score") or 0
    )
    monkeypatch.setattr(
        cli, "cmd_populate",
        lambda args: (_ for _ in ()).throw(AssertionError("populate must not run")),
    )
    args = SimpleNamespace(as_of=None)
    assert cli.cmd_refresh(args) == 0
    assert calls == ["fetch", "score"]


def test_refresh_stops_at_the_first_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "cmd_fetch", lambda args: 3)
    monkeypatch.setattr(
        cli, "cmd_score", lambda args: calls.append("score") or 0
    )
    assert cli.cmd_refresh(SimpleNamespace(as_of=None)) == 3
    assert calls == []


def test_refresh_accepts_as_of():
    args = cli.build_parser().parse_args(["refresh", "--as-of", "2026-10-22T18:00Z"])
    assert args.as_of == "2026-10-22T18:00Z"
