from datetime import datetime, timedelta, timezone

import pytest
from argparse import ArgumentTypeError

from mtv_parser.migration_information import MigrationAnalyzer
from mtv_parser.since_filter import (
    chart_cutoff,
    filter_plan_records,
    filter_vm_groups,
    parse_since_date,
    rebuild_hour_window,
    vm_in_time_window,
)

_INVALID_DATE = r"Invalid date format\. Expected YYYY-MM-DD"


def test_parse_since_midnight():
    assert parse_since_date("2026-09-27") == datetime(2026, 9, 27)


def test_parse_since_rejects_slashes():
    with pytest.raises(ArgumentTypeError, match=_INVALID_DATE):
        parse_since_date("09/27/2026")


def test_parse_since_rejects_compact():
    with pytest.raises(ArgumentTypeError):
        parse_since_date("20260927")


def test_parse_since_rejects_impossible_day():
    with pytest.raises(ArgumentTypeError):
        parse_since_date("2026-02-31")


def test_since_only_drops_vm_that_started_before_cutoff():
    vm = {
        "start_time": datetime(2026, 9, 25, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 10, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), None) is False


def test_since_only_drops_vm_that_ended_before_cutoff():
    vm = {
        "start_time": datetime(2026, 9, 25, 10, 0, 0),
        "end_time": datetime(2026, 9, 26, 23, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), None) is False


def test_since_only_keeps_vm_that_starts_on_or_after_cutoff():
    vm = {
        "start_time": datetime(2026, 9, 28, 1, 0, 0),
        "end_time": datetime(2026, 9, 28, 12, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), None) is True


def test_since_only_open_ended_vm_without_end_raises():
    vm = {"start_time": datetime(2026, 9, 25, 10, 0, 0)}
    with pytest.raises(AttributeError):
        vm_in_time_window(vm, datetime(2026, 9, 27), None)


def test_missing_start_raises():
    with pytest.raises(AttributeError):
        vm_in_time_window({"end_time": datetime(2026, 9, 28)}, datetime(2026, 9, 27), None)


def test_since_only_aware_end_still_requires_start_on_or_after_cutoff():
    aware_end = datetime(2026, 9, 27, 3, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    vm = {"start_time": datetime(2026, 9, 26, 12, 0, 0), "end_time": aware_end}
    assert vm_in_time_window(vm, datetime(2026, 9, 27), None) is False


def test_filter_vm_groups_none_returns_same_object():
    grouped = {"linux": [{"start_time": datetime(2026, 9, 28), "end_time": datetime(2026, 9, 28, 1)}]}
    assert filter_vm_groups(grouped, None, None) is grouped


def test_filter_vm_groups_omits_empty_os_and_does_not_mutate():
    kept = {
        "name": "kept",
        "start_time": datetime(2026, 9, 27, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 10, 0, 0),
    }
    ended = {
        "name": "ended",
        "start_time": datetime(2026, 9, 20, 10, 0, 0),
        "end_time": datetime(2026, 9, 26, 10, 0, 0),
    }
    grouped = {"linux": [kept, ended]}
    result = filter_vm_groups(grouped, datetime(2026, 9, 27), None)
    assert result == {"linux": [kept]}
    assert len(grouped["linux"]) == 2


def test_filter_plan_records_keeps_overlapping_plan():
    early = {
        "name": "early",
        "start_time": datetime(2026, 9, 20, 8, 0, 0),
        "end_time": datetime(2026, 9, 26, 18, 0, 0),
    }
    late = {
        "name": "late",
        "start_time": datetime(2026, 9, 27, 1, 0, 0),
        "end_time": datetime(2026, 9, 28, 18, 0, 0),
    }
    plans = [early, late]
    assert filter_plan_records(plans, None, None) is plans
    assert filter_plan_records(plans, datetime(2026, 9, 27), None) == [late]


def test_chart_cutoff_prefers_gantt_since():
    september_first = datetime(2026, 9, 1)
    september_27 = datetime(2026, 9, 27)
    assert chart_cutoff(september_first, None, september_27, None) == (september_27, None)
    assert chart_cutoff(september_first, None, None, None) == (september_first, None)
    assert chart_cutoff(None, None, None, None) == (None, None)


def test_since_only_boundary_start_before_cutoff_is_dropped():
    vm = {
        "start_time": datetime(2026, 9, 26, 18, 0, 0),
        "end_time": datetime(2026, 9, 27, 0, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), None) is False


def test_window_keeps_vm_fully_inside_since_and_until():
    vm = {
        "start_time": datetime(2026, 9, 28, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 18, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), datetime(2026, 9, 28)) is True


def test_window_drops_vm_that_starts_after_until_day():
    vm = {
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 29, 4, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), datetime(2026, 9, 28)) is False


def test_window_drops_vm_that_extends_past_until_day():
    vm = {
        "start_time": datetime(2026, 9, 27, 10, 0, 0),
        "end_time": datetime(2026, 9, 30, 10, 0, 0),
    }
    assert vm_in_time_window(vm, datetime(2026, 9, 27), datetime(2026, 9, 28)) is False


def test_window_only_until_open_ended_vm_raises():
    vm = {"start_time": datetime(2026, 9, 28, 10, 0, 0)}
    with pytest.raises(AttributeError):
        vm_in_time_window(vm, None, datetime(2026, 9, 28))


def test_window_only_until_drops_vm_starting_after_until_day():
    vm = {
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 29, 4, 0, 0),
    }
    with pytest.raises(TypeError):
        vm_in_time_window(vm, None, datetime(2026, 9, 28))


def test_filter_vm_groups_removes_entire_os_key():
    grouped = {
        "windows": [
            {
                "name": "old-win",
                "start_time": datetime(2026, 9, 20, 10, 0, 0),
                "end_time": datetime(2026, 9, 21, 10, 0, 0),
            }
        ],
        "linux": [
            {
                "name": "recent-lin",
                "start_time": datetime(2026, 9, 27, 1, 0, 0),
                "end_time": datetime(2026, 9, 27, 5, 0, 0),
            }
        ],
    }
    result = filter_vm_groups(grouped, datetime(2026, 9, 27), None)
    assert "windows" not in result
    assert result["linux"][0]["name"] == "recent-lin"


def test_rebuild_hour_window_includes_pre_cutoff_start():
    grouped = {
        "linux": [
            {
                "name": "span",
                "start_time": datetime(2026, 9, 25, 10, 0, 0),
                "end_time": datetime(2026, 9, 28, 10, 0, 0),
                "duration": 4320.0,
            }
        ]
    }
    window = rebuild_hour_window(MigrationAnalyzer(), grouped)
    assert datetime(2026, 9, 25, 10, 0, 0) in window
    assert datetime(2026, 9, 28, 10, 0, 0) in window


def test_filter_vm_groups_applies_until_without_clipping():
    inside = {
        "name": "inside",
        "start_time": datetime(2026, 9, 27, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 18, 0, 0),
    }
    late = {
        "name": "late",
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 29, 4, 0, 0),
    }
    grouped = {"linux": [inside, late]}
    result = filter_vm_groups(grouped, datetime(2026, 9, 27), datetime(2026, 9, 28))
    assert result == {"linux": [inside]}
    assert result["linux"][0] is inside


def test_filter_vm_groups_both_bounds_missing_returns_same_object():
    grouped = {"linux": [{"start_time": datetime(2026, 9, 28), "end_time": datetime(2026, 9, 28, 1)}]}
    assert filter_vm_groups(grouped, None, None) is grouped


def test_filter_plan_records_keeps_plan_still_running_on_last_day():
    plan = {
        "name": "span",
        "start_time": datetime(2026, 9, 26, 8, 0, 0),
        "end_time": datetime(2026, 9, 30, 8, 0, 0),
        "total_duration_mins": 5760,
        "total_disk_size": 100,
    }
    result = filter_plan_records([plan], datetime(2026, 9, 27), datetime(2026, 9, 28))
    assert result == [plan]
    assert result[0]["total_duration_mins"] == 5760
    assert result[0]["total_disk_size"] == 100


def test_filter_plan_records_until_not_applied_to_plans_yet():
    plan = {
        "name": "later",
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 30, 0, 0, 0),
        "total_duration_mins": 60,
    }
    assert filter_plan_records([plan], datetime(2026, 9, 27), datetime(2026, 9, 28)) == [plan]


def test_filter_plan_records_keeps_plan_with_end_on_or_after_since():
    plan = {"name": "no-start", "end_time": datetime(2026, 9, 28, 18, 0, 0)}
    assert filter_plan_records([plan], datetime(2026, 9, 27), None) == [plan]


def test_chart_cutoff_inherits_report_end_when_only_gantt_since_is_set():
    report_end = datetime(2026, 9, 28)
    assert chart_cutoff(datetime(2026, 9, 1), report_end, datetime(2026, 9, 27), None) == (
        datetime(2026, 9, 27),
        report_end,
    )


def test_chart_cutoff_gantt_until_overrides_report_until():
    report_end = datetime(2026, 9, 30)
    chart_end = datetime(2026, 9, 28)
    assert chart_cutoff(datetime(2026, 9, 1), report_end, datetime(2026, 9, 27), chart_end) == (
        datetime(2026, 9, 27),
        chart_end,
    )


def test_chart_cutoff_chart_end_keeps_report_start():
    chart_end = datetime(2026, 9, 28)
    assert chart_cutoff(datetime(2026, 9, 1), None, None, chart_end) == (datetime(2026, 9, 1), chart_end)
