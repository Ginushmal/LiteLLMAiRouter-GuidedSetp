"""Tests for score-phase console output and the --as-of override."""

from datetime import datetime, timezone
from types import SimpleNamespace

from model_pipeline.cli import (
    _as_of_for_run,
    _print_pin_warnings,
    _tier_summary,
    build_parser,
)


def test_pin_warnings_go_to_stderr(capsys):
    _print_pin_warnings(["pins.tiers.Ultra: 'x' matches no canonical model; ignored"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "warning: pins.tiers.Ultra: 'x' matches no canonical model; ignored\n"
    )


def test_tier_summary_separates_pinned_and_scored_deployments():
    tier = SimpleNamespace(
        name="Ultra",
        model_group="ultra-tier",
        pool_size=7,
        deployments=[
            SimpleNamespace(is_pinned=True),
            SimpleNamespace(is_pinned=True),
            SimpleNamespace(is_pinned=False),
        ],
    )

    summary = _tier_summary(tier)
    assert "2 pinned" in summary
    assert "1 scored" in summary
    assert "pool 7" in summary


# -- --as-of precedence ---------------------------------------------------
CONFIG_INSTANT = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)


def test_as_of_flag_wins_over_the_configured_instant():
    cfg = SimpleNamespace(pricing=SimpleNamespace(as_of=CONFIG_INSTANT))
    args = SimpleNamespace(as_of="2026-10-22T18:00Z")
    assert _as_of_for_run(cfg, args) == datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc)


def test_absent_as_of_flag_keeps_the_configured_instant():
    cfg = SimpleNamespace(pricing=SimpleNamespace(as_of=CONFIG_INSTANT))
    assert _as_of_for_run(cfg, SimpleNamespace(as_of=None)) == CONFIG_INSTANT
    # `populate` has no flag at all.
    assert _as_of_for_run(cfg, SimpleNamespace()) == CONFIG_INSTANT


def test_fetch_score_and_run_accept_as_of():
    for command in ("fetch", "score", "run"):
        args = build_parser().parse_args([command, "--as-of", "2026-10-22T18:00Z"])
        assert args.as_of == "2026-10-22T18:00Z"
