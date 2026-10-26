import pytest

from mtv_parser.pipeline_timing import (
    highest_gib_per_hour,
    migration_wall_clock_seconds,
    phase_minutes,
    plan_vm_phase_averages,
    summarize_plan_records,
    summarize_vm_records,
)


def test_migration_wall_clock():
    status = {"started": "2026-09-24T14:43:24Z", "completed": "2026-09-24T16:08:39Z"}
    assert migration_wall_clock_seconds(status) == pytest.approx(5115.0)


def test_summarize_vm_records():
    vms = [
        {
            "name": "a",
            "transfer_minutes": 10.0,
            "conversion_minutes": 5.0,
            "guest_reboot_wait_minutes": 20.0,
        },
        {"name": "b", "transfer_minutes": 20.0, "conversion_minutes": 15.0},
    ]
    stats = summarize_vm_records(vms)
    assert stats["average_transfer_minutes"] == 15.0
    assert stats["longest_transfer_minutes"] == 20.0
    assert stats["average_conversion_minutes"] == 10.0
    assert stats["average_guest_reboot_wait_minutes"] == 20.0
    assert stats["vms_with_guest_reboot_wait"] == 1


def test_summarize_plan_records():
    migrations = [
        {
            "name": "plan-a",
            "plan_wall_clock_minutes": 100.0,
            "avg_transfer_minutes": 10.0,
            "avg_conversion_minutes": 5.0,
            "vms_with_guest_reboot_wait": 1,
            "avg_guest_reboot_wait_minutes": 18.0,
        },
        {
            "name": "plan-b",
            "plan_wall_clock_minutes": 50.0,
            "avg_transfer_minutes": 8.0,
            "avg_conversion_minutes": 4.0,
        },
    ]
    stats = summarize_plan_records(migrations)
    assert stats["average_plan_wall_clock_minutes"] == 75.0
    assert stats["longest_plan_wall_clock_minutes"] == 100.0
    assert stats["longest_plan_wall_clock_name"] == "plan-a"
    assert stats["plans_with_guest_reboot_wait"] == 1


def test_plan_vm_phase_averages():
    out = plan_vm_phase_averages([10.0, 20.0], [5.0], [12.0])
    assert out["avg_transfer_minutes"] == 15.0
    assert out["avg_conversion_minutes"] == 5.0
    assert out["vms_with_guest_reboot_wait"] == 1


def test_phase_minutes_exact():
    minutes = phase_minutes("2026-10-09T17:15:24", "2026-10-09T17:58:45")
    assert minutes == 2601 / 60
    assert phase_minutes("2026-10-09T17:58:45", "2026-10-09T17:15:24") is None


def test_highest_rate_is_not_the_longest_row():
    records = [
        {"disk_mib": 24160256, "minutes": 43.35},
        {"disk_mib": 31960064, "minutes": 2473 / 60},
    ]
    rate = highest_gib_per_hour(records, "disk_mib", "minutes")
    assert rate == 31211 * 3600 / 2473
