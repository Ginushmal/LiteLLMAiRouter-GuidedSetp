"""Tests for score-phase console output."""

from types import SimpleNamespace

from model_pipeline.cli import _print_pin_warnings, _tier_summary


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
