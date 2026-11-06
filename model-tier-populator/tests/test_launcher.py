"""The launcher must refresh first, then open the report, then offer populate."""

from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "refresh-and-open.bat"
REPORT = 'start "" "output\\tier-report.html"'


def _text() -> str:
    return BAT.read_text(encoding="utf-8")


def test_launcher_orders_refresh_report_then_interactive_populate():
    text = _text()
    refresh = text.index("uv run model-pipeline refresh")
    report = text.index(REPORT)
    populate = text.index("uv run model-pipeline populate --interactive")

    assert refresh < report < populate


def test_refresh_failure_exits_before_report_or_populate():
    text = _text()
    failure = text.index("refresh FAILED")
    exit_branch = text.index("exit /b 1", failure)
    report = text.index(REPORT)
    populate = text.index("uv run model-pipeline populate --interactive")

    assert failure < exit_branch < report < populate
