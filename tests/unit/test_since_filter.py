from datetime import datetime, timedelta, timezone

from mtv_parser.migration_information import MigrationAnalyzer
from mtv_parser.since_filter import (
    chart_cutoff,
    completed_in_window,
    filter_plan_records,
    filter_vm_groups,
    rebuild_hour_window,
    vms_continuing_past_until,
)


def test_since_only_keeps_vm_completed_after_cutoff():
    vm = {
        "start_time": datetime(2026, 9, 25, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 10, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), None) is True


def test_since_only_drops_vm_that_ended_before_cutoff():
    vm = {
        "start_time": datetime(2026, 9, 25, 10, 0, 0),
        "end_time": datetime(2026, 9, 26, 23, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), None) is False


def test_since_only_keeps_vm_that_starts_on_or_after_cutoff():
    vm = {
        "start_time": datetime(2026, 9, 28, 1, 0, 0),
        "end_time": datetime(2026, 9, 28, 12, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), None) is True


def test_missing_end_is_excluded():
    vm = {"start_time": datetime(2026, 9, 25, 10, 0, 0)}
    assert completed_in_window(vm.get("end_time"), datetime(2026, 9, 27), None) is False


def test_missing_start_ignores_start():
    vm = {"end_time": datetime(2026, 9, 28)}
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), None) is True


def test_since_only_aware_end_uses_utc_completion():
    aware_end = datetime(2026, 9, 27, 3, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    vm = {"start_time": datetime(2026, 9, 26, 12, 0, 0), "end_time": aware_end}
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), None) is True


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


def test_completion_at_since_midnight_is_kept():
    vm = {
        "start_time": datetime(2026, 9, 26, 18, 0, 0),
        "end_time": datetime(2026, 9, 27, 0, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), None) is True


def test_window_keeps_vm_fully_inside_since_and_until():
    vm = {
        "start_time": datetime(2026, 9, 28, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 18, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), datetime(2026, 9, 28)) is True


def test_window_drops_vm_that_starts_after_until_day():
    vm = {
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 29, 4, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), datetime(2026, 9, 28)) is False


def test_window_drops_vm_that_extends_past_until_day():
    vm = {
        "start_time": datetime(2026, 9, 27, 10, 0, 0),
        "end_time": datetime(2026, 9, 30, 10, 0, 0),
    }
    assert completed_in_window(vm["end_time"], datetime(2026, 9, 27), datetime(2026, 9, 28)) is False


def test_window_only_until_open_ended_vm_raises():
    vm = {"start_time": datetime(2026, 9, 28, 10, 0, 0)}
    assert completed_in_window(vm.get("end_time"), None, datetime(2026, 9, 28)) is False


def test_window_only_until_drops_vm_starting_after_until_day():
    vm = {
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 29, 4, 0, 0),
    }
    assert completed_in_window(vm["end_time"], None, datetime(2026, 9, 28)) is False


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
    assert result == []


def test_filter_plan_records_excludes_completion_after_until():
    plan = {
        "name": "later",
        "start_time": datetime(2026, 9, 29, 0, 0, 0),
        "end_time": datetime(2026, 9, 30, 0, 0, 0),
        "total_duration_mins": 60,
    }
    assert filter_plan_records([plan], datetime(2026, 9, 27), datetime(2026, 9, 28)) == []


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


def test_filter_vm_groups_until_only_excludes_later_completion():
    inside = {
        "name": "inside",
        "start_time": datetime(2026, 9, 28, 10, 0, 0),
        "end_time": datetime(2026, 9, 28, 18, 0, 0),
    }
    later = {
        "name": "later",
        "start_time": datetime(2026, 9, 28, 10, 0, 0),
        "end_time": datetime(2026, 9, 29, 1, 0, 0),
    }
    grouped = {"linux": [inside, later]}
    assert filter_vm_groups(grouped, None, datetime(2026, 9, 28)) == {"linux": [inside]}


def test_filter_plan_records_until_only():
    inside = {"name": "inside", "end_time": datetime(2026, 9, 28, 18, 0, 0)}
    later = {"name": "later", "end_time": datetime(2026, 9, 29, 1, 0, 0)}
    assert filter_plan_records([inside, later], None, datetime(2026, 9, 28)) == [inside]


def test_vms_continuing_past_until_lists_overflow_and_still_running():
    since = datetime(2026, 9, 25)
    until = datetime(2026, 9, 27)
    grouped = {
        "linux": [
            {
                "name": "overflow",
                "start_time": datetime(2026, 9, 26, 10, 0, 0),
                "end_time": datetime(2026, 9, 28, 10, 0, 0),
            },
            {
                "name": "finished",
                "start_time": datetime(2026, 9, 26, 10, 0, 0),
                "end_time": datetime(2026, 9, 26, 18, 0, 0),
            },
            {
                "name": "started-early",
                "start_time": datetime(2026, 9, 20, 10, 0, 0),
                "end_time": datetime(2026, 9, 28, 10, 0, 0),
            },
        ]
    }
    open_vms = {
        "linux": [
            {
                "name": "still-running",
                "start_time": datetime(2026, 9, 26, 12, 0, 0),
                "end_time": None,
            }
        ]
    }
    rows = vms_continuing_past_until(grouped, open_vms, since, until)
    names = []
    for vm in rows:
        names.append(vm["name"])
    assert names == ["overflow", "still-running"]
