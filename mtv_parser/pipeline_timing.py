"""Aggregate migration pipeline timing for plan and VM reports."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any

try:
    from utils import as_naive_utc
except ModuleNotFoundError:
    from mtv_parser.utils import as_naive_utc


def migration_wall_clock_seconds(migration_status: dict[str, Any]) -> float | None:
    """Plan-level wall clock from status.migration started to completed, in seconds."""
    try:
        migration_wall_clock_duration = datetime.fromisoformat(
            migration_status["completed"]
        ) - datetime.fromisoformat(migration_status["started"])
    except (KeyError, TypeError, ValueError):
        return None
    return migration_wall_clock_duration.total_seconds()


def _mean_positive(values: list[float]) -> float | None:
    positive = [v for v in values if v > 0]
    if not positive:
        return None
    return statistics.mean(positive)


def _max_named(
    records: list[dict[str, Any]], field: str, name_field: str = "name"
) -> tuple[float | None, str | None]:
    candidates = [(record[field], record.get(name_field, "")) for record in records if record.get(field, 0) > 0]
    if not candidates:
        return None, None
    value, name = max(candidates, key=lambda item: item[0])
    return value, name


def summarize_vm_records(vms: list[dict[str, Any]]) -> dict[str, Any]:
    """Build VM summary timing keys consumed by clioutput."""
    result: dict[str, Any] = {}

    transfer_values = [vm["transfer_minutes"] for vm in vms if vm.get("transfer_minutes", 0) > 0]
    if transfer_values:
        result["average_transfer_minutes"] = statistics.mean(transfer_values)
        result["longest_transfer_minutes"] = max(transfer_values)

    conversion_values = [vm["conversion_minutes"] for vm in vms if vm.get("conversion_minutes", 0) > 0]
    if conversion_values:
        result["average_conversion_minutes"] = statistics.mean(conversion_values)
        longest_conversion, longest_conversion_vm = _max_named(vms, "conversion_minutes")
        if longest_conversion is not None:
            result["longest_conversion_minutes"] = longest_conversion
            result["longest_conversion_vm_name"] = longest_conversion_vm

    guest_values = [vm["guest_reboot_wait_minutes"] for vm in vms if vm.get("guest_reboot_wait_minutes", 0) > 0]
    if guest_values:
        result["average_guest_reboot_wait_minutes"] = statistics.mean(guest_values)
        result["vms_with_guest_reboot_wait"] = len(guest_values)
        longest_guest, longest_guest_vm = _max_named(vms, "guest_reboot_wait_minutes")
        if longest_guest is not None:
            result["longest_guest_reboot_wait_minutes"] = longest_guest
            result["longest_guest_reboot_vm_name"] = longest_guest_vm

    return result


def summarize_plan_records(migrations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate migration dicts for the plan report pipeline-timing section."""
    result: dict[str, Any] = {}

    wall_clock_values = [
        migration["plan_wall_clock_minutes"]
        for migration in migrations
        if migration.get("plan_wall_clock_minutes", 0) > 0
    ]
    if wall_clock_values:
        result["average_plan_wall_clock_minutes"] = statistics.mean(wall_clock_values)
        longest_wall_clock, longest_wall_clock_name = _max_named(migrations, "plan_wall_clock_minutes")
        if longest_wall_clock is not None:
            result["longest_plan_wall_clock_minutes"] = longest_wall_clock
            result["longest_plan_wall_clock_name"] = longest_wall_clock_name

    transfer_values = [
        migration["avg_transfer_minutes"] for migration in migrations if migration.get("avg_transfer_minutes", 0) > 0
    ]
    if transfer_values:
        result["average_plan_disk_transfer_minutes"] = statistics.mean(transfer_values)

    conversion_values = [
        migration["avg_conversion_minutes"]
        for migration in migrations
        if migration.get("avg_conversion_minutes", 0) > 0
    ]
    if conversion_values:
        result["average_plan_conversion_minutes"] = statistics.mean(conversion_values)

    guest_values = [
        migration["avg_guest_reboot_wait_minutes"]
        for migration in migrations
        if migration.get("avg_guest_reboot_wait_minutes", 0) > 0
    ]
    if guest_values:
        result["average_plan_guest_reboot_wait_minutes"] = statistics.mean(guest_values)

    plans_with_guest = sum(1 for migration in migrations if migration.get("vms_with_guest_reboot_wait", 0) > 0)
    if plans_with_guest > 0:
        result["plans_with_guest_reboot_wait"] = plans_with_guest

    return result


def positive_phase_minutes(payload: dict[str, Any]) -> dict[str, float]:
    """Return transfer, conversion, and guest-reboot minutes that are greater than zero."""
    minutes: dict[str, float] = {}
    for field in ("transfer_minutes", "conversion_minutes", "guest_reboot_wait_minutes"):
        value = payload.get(field) or 0
        if value > 0:
            minutes[field] = value
    return minutes


def plan_vm_phase_averages(
    transfer_minutes_list: list[float],
    conversion_minutes_list: list[float],
    guest_reboot_minutes_list: list[float],
) -> dict[str, Any]:
    """Per-plan means from VM-level phase minute lists."""
    result: dict[str, Any] = {}

    avg_transfer = _mean_positive(transfer_minutes_list)
    if avg_transfer is not None:
        result["avg_transfer_minutes"] = avg_transfer

    avg_conversion = _mean_positive(conversion_minutes_list)
    if avg_conversion is not None:
        result["avg_conversion_minutes"] = avg_conversion

    if guest_reboot_minutes_list:
        result["vms_with_guest_reboot_wait"] = len(guest_reboot_minutes_list)
        avg_guest = _mean_positive(guest_reboot_minutes_list)
        if avg_guest is not None:
            result["avg_guest_reboot_wait_minutes"] = avg_guest

    return result


def phase_minutes(started: str | None, completed: str | None) -> float | None:
    """Exact minutes from started to completed. None unless the span is positive."""
    started_at = as_naive_utc(started)
    completed_at = as_naive_utc(completed)
    if started_at is None or completed_at is None:
        return None
    minutes = (completed_at - started_at).total_seconds() / 60
    if minutes <= 0:
        return None
    return minutes


def highest_gib_per_hour(
    records: list[dict[str, Any]],
    disk_mib_field: str,
    minutes_field: str,
) -> float | None:
    """Max GiB/hour. Skip a row whose disk or minutes are not positive."""
    highest_rate = None
    for record in records:
        disk_mib = record.get(disk_mib_field)
        minutes = record.get(minutes_field)
        disk_ok = isinstance(disk_mib, (int, float)) and not isinstance(disk_mib, bool) and disk_mib > 0
        minutes_ok = isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0
        if not disk_ok or not minutes_ok:
            continue
        gib = disk_mib / 1024
        hours = minutes / 60
        rate = gib / hours
        if highest_rate is None or rate > highest_rate:
            highest_rate = rate
    return highest_rate
