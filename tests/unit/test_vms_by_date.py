import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

from mtv_parser.clioutput import CLIOutput
from mtv_parser.migration_information import MigrationAnalyzer


REPO_ROOT = "/home/stratus/git_projects/mtv-parser"


@pytest.fixture
def migration_analyzer():
    return MigrationAnalyzer()


def _run_parser(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "mtv_parser/mtv_plan_parser.py", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_group_excludes_failed_vms(migration_analyzer):
    all_vms = {
        "linux": [
            {
                "name": "ok-vm",
                "disk_size": 1024,
                "start_time": datetime(2024, 7, 25, 10, 0, 0),
                "end_time": datetime(2024, 7, 25, 11, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            },
            {
                "name": "fail-vm",
                "disk_size": 2048,
                "start_time": datetime(2024, 7, 25, 11, 0, 0),
                "end_time": datetime(2024, 7, 25, 11, 30, 0),
                "duration": 30.0,
                "succeeded": False,
            },
        ]
    }
    grouped = migration_analyzer.group_successful_vms_by_completion_date(all_vms)
    assert grouped == {date(2024, 7, 25): ["ok-vm"]}


def test_group_two_dates_sorted(migration_analyzer):
    all_vms = {
        "linux": [
            {
                "name": "zeta",
                "disk_size": 1024,
                "start_time": datetime(2024, 7, 26, 9, 0, 0),
                "end_time": datetime(2024, 7, 26, 10, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            },
            {
                "name": "alpha",
                "disk_size": 1024,
                "start_time": datetime(2024, 7, 26, 8, 0, 0),
                "end_time": datetime(2024, 7, 26, 9, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            },
        ],
        "windows": [
            {
                "name": "win-a",
                "disk_size": 4096,
                "start_time": datetime(2024, 7, 25, 12, 0, 0),
                "end_time": datetime(2024, 7, 25, 13, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            }
        ],
    }
    grouped = migration_analyzer.group_successful_vms_by_completion_date(all_vms)
    assert list(grouped.keys()) == [date(2024, 7, 25), date(2024, 7, 26)]
    assert grouped[date(2024, 7, 25)] == ["win-a"]
    assert grouped[date(2024, 7, 26)] == ["alpha", "zeta"]


def test_group_uses_end_time_when_present(migration_analyzer):
    all_vms = {
        "linux": [
            {
                "name": "cross-day",
                "disk_size": 1024,
                "start_time": datetime(2024, 7, 25, 10, 0, 0),
                "end_time": datetime(2024, 7, 26, 1, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            }
        ]
    }
    grouped = migration_analyzer.group_successful_vms_by_completion_date(all_vms)
    assert grouped == {date(2024, 7, 26): ["cross-day"]}


def test_group_timezone_aware_to_utc_date(migration_analyzer):
    aware = datetime(2024, 7, 25, 23, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    all_vms = {
        "linux": [
            {
                "name": "tz-vm",
                "disk_size": 1024,
                "start_time": aware,
                "end_time": aware,
                "duration": 1.0,
                "succeeded": True,
            }
        ]
    }
    grouped = migration_analyzer.group_successful_vms_by_completion_date(all_vms)
    assert grouped == {date(2024, 7, 26): ["tz-vm"]}


def test_group_empty(migration_analyzer):
    assert migration_analyzer.group_successful_vms_by_completion_date({}) == {}


def test_vms_by_date_output_lists_names():
    output = CLIOutput()
    text = output.vms_by_date_output({date(2024, 7, 25): ["alpha", "beta"]})
    assert "VMS BY COMPLETION DATE" in text
    assert "2024-07-25" in text
    assert "  alpha" in text
    assert "  beta" in text


def test_vms_by_date_output_empty():
    output = CLIOutput()
    text = output.vms_by_date_output({})
    assert "No VMs with a completion date." in text


def test_help_lists_vms_by_date():
    result = _run_parser("--help")
    assert result.returncode == 0
    assert "--vms-by-date" in result.stdout


def test_flag_rejects_a_value():
    result = _run_parser("--vms-by-date", "1")
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


def test_parse_args_default_off():
    """Default argv must not print the by-date section.

    mtv_plan_parser.py uses script-relative imports, so parse_args cannot be
    imported via mtv_parser.mtv_plan_parser. Subprocess exercises the real CLI.
    """
    result = _run_parser()
    assert "VMS BY COMPLETION DATE" not in result.stdout


def test_group_deduplicates_same_name_across_os(migration_analyzer):
    """Same VM name under two OS types on the same date appears once."""
    all_vms = {
        "linux": [
            {
                "name": "shared-vm",
                "disk_size": 1024,
                "start_time": datetime(2024, 7, 25, 10, 0, 0),
                "end_time": datetime(2024, 7, 25, 11, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            }
        ],
        "windows": [
            {
                "name": "shared-vm",
                "disk_size": 2048,
                "start_time": datetime(2024, 7, 25, 12, 0, 0),
                "end_time": datetime(2024, 7, 25, 13, 0, 0),
                "duration": 60.0,
                "succeeded": True,
            }
        ],
    }
    grouped = migration_analyzer.group_successful_vms_by_completion_date(all_vms)
    assert grouped == {date(2024, 7, 25): ["shared-vm"]}
