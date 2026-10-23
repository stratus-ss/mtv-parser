import subprocess
import sys

import pytest

REPO_ROOT = "/home/stratus/git_projects/mtv-parser"

_INVALID_DATE = "Invalid date format. Expected YYYY-MM-DD"


def _run_parser(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "mtv_parser/mtv_plan_parser.py", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_lists_since_flags():
    result = _run_parser("--help")
    assert result.returncode == 0
    assert "--since" in result.stdout
    assert "--gantt-since" in result.stdout
    assert "--until" in result.stdout
    assert "--gantt-until" in result.stdout


def test_since_rejects_bad_date_before_plans():
    result = _run_parser("--since", "2026-09-27th")
    assert result.returncode != 0
    assert _INVALID_DATE in result.stderr
    assert "No migration data available" not in result.stdout


def test_gantt_since_rejects_bad_date():
    result = _run_parser("--gantt-since", "September")
    assert result.returncode != 0
    assert _INVALID_DATE in result.stderr


def test_until_rejects_bad_date_before_plans():
    result = _run_parser("--until", "2026-09-27th")
    assert result.returncode != 0
    assert _INVALID_DATE in result.stderr
    assert "No migration data available" not in result.stdout
    assert "No plan YAML found" not in result.stderr


def test_gantt_until_rejects_bad_date():
    result = _run_parser("--gantt-until", "September")
    assert result.returncode != 0
    assert _INVALID_DATE in result.stderr


@pytest.mark.skip(reason="Report/chart window validation not implemented yet (mtv_plan_parser TODO)")
def test_until_before_since_rejects_before_plans():
    result = _run_parser("--since", "2026-09-28", "--until", "2026-09-27")
    assert result.returncode != 0
    assert "end date is before start date" in result.stderr


@pytest.mark.skip(reason="Report/chart window validation not implemented yet (mtv_plan_parser TODO)")
def test_gantt_until_before_gantt_since_rejects_before_plans():
    result = _run_parser("--gantt-since", "2026-09-28", "--gantt-until", "2026-09-27")
    assert result.returncode != 0
    assert "end date is before start date" in result.stderr


@pytest.mark.skip(reason="Report/chart window validation not implemented yet (mtv_plan_parser TODO)")
def test_chart_inherits_until_that_is_before_gantt_since():
    result = _run_parser("--gantt-since", "2026-09-28", "--until", "2026-09-27")
    assert result.returncode != 0
    assert "end date is before start date" in result.stderr


@pytest.mark.skip(reason="Report/chart window validation not implemented yet (mtv_plan_parser TODO)")
def test_chart_inherits_since_that_is_after_gantt_until():
    result = _run_parser("--since", "2026-09-28", "--gantt-until", "2026-09-27")
    assert result.returncode != 0
    assert "end date is before start date" in result.stderr


def test_same_calendar_day_is_not_reversed():
    result = _run_parser("--since", "2026-09-27", "--until", "2026-09-27")
    assert "end date is before start date" not in result.stderr
    assert "unrecognized arguments" not in result.stderr
    assert _INVALID_DATE not in result.stderr
