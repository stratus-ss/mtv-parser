from datetime import date, datetime, timezone
from typing import Protocol
import argparse


def _as_naive_utc(value: datetime) -> datetime:
    """
    Convert a timezone-aware datetime to a naive UTC datetime.
    Args:
        value: A naive or timezone-aware datetime.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_since_date(value: str) -> datetime:
    """
    Parse a date string into a datetime object.

    Args:
        value: The raw --since or --gantt-since string from argparse.
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format. Expected YYYY-MM-DD, got {value}")
    


def vm_overlaps_since(vm: dict, since: datetime) -> bool:
    """
    Check if a VM overlaps with a given since datetime.
    Args:
        vm: One VM record. Read start_time and end_time. Do not write either key.
        since: Cutoff instant. May be naive or timezone-aware.
    """
    if vm.get("start_time") is None or not isinstance(vm.get("start_time"), datetime):
        return True
    if vm.get("end_time") is None or not isinstance(vm.get("end_time"), datetime):
        return True
    
    start_time_utc = _as_naive_utc(since)
    end_time_utc = _as_naive_utc(vm["end_time"])
    return end_time_utc >= start_time_utc


def filter_vm_groups(grouped: dict[str, list[dict]], since: datetime | None) -> dict[str, list[dict]]:
    """
    Filter VM groups based on a given since datetime.
    Args:
        grouped: OS name to the list of VM dicts under that OS. Same VM shape as vm_overlaps_since.
        since: Cutoff instant, or None when no cutoff is set.
    """
    if since is None:
        return grouped
    filtered: dict[str, list[dict]] = {}
    for os_key, vm_list in grouped.items():
        for vm in vm_list:
            if vm_overlaps_since(vm, since):
                if filtered.get(os_key) is None:
                    filtered[os_key] = [vm]
                else:
                    filtered[os_key].append(vm)
    return filtered


def filter_plan_records(plans: list[dict], since: datetime | None) -> list[dict]:
    """
    Filter plan records based on a given since datetime.
    Args:
        plans: Plan summary dicts. Read end_time. Leave every other field as it is.
        since: Cutoff instant, or None when no cutoff is set.
    """
    if since is None:
        return plans
    cutoff_date = _as_naive_utc(since)
    all_plans = []
    for plan in plans:
        plan_end_time = _as_naive_utc(plan["end_time"])
        if plan_end_time >= cutoff_date:
            all_plans.append(plan)
    return all_plans


def chart_cutoff(since: datetime | None, gantt_since: datetime | None) -> datetime | None:
    """
    Prefer the chart-only cutoff. Fall back to the global cutoff.

    Args:
        since: Global cutoff from --since, or None.
        gantt_since: Chart-only cutoff from --gantt-since, or None.
    """
    if gantt_since is not None:
        return gantt_since
    return since


def rebuild_hour_window(analyzer, grouped: dict[str, list[dict]]) -> dict[datetime, int]:
    """
    Hour counts for kept VMs, including hours before the cutoff.
    
    Args:
        analyzer: Object with get_migration_time_range(start_time, duration). Pass MigrationAnalyzer.
        grouped: OS name to VM dicts. Each VM may have start_time (datetime) and duration (minutes).
    """
    window: dict[datetime, int] = {}
    for vm_list in grouped.values():
        for single_vm in vm_list:
            start_time = single_vm.get("start_time")
            duration = single_vm.get("duration")
            if not isinstance(start_time, datetime) or not isinstance(duration, (int, float)) or duration <= 0:
                continue
            for hour in analyzer.get_migration_time_range(start_time, duration):
                window[hour] = window.get(hour, 0) + 1
    return window
