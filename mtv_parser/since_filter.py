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
    


def vm_in_time_window(vm: dict, since: datetime | None, until: datetime | None) -> bool:
    """
    Check if a VM overlaps with a given since and/or until datetime.
    Args:
        vm: One VM record. Read start_time and end_time. Do not write either key.
        since: Cutoff instant. May be naive or timezone-aware.
    """
    cli_start_time_utc = None
    cli_end_time_utc = None
    vm_start_time_utc = _as_naive_utc(vm.get("start_time"))
    vm_end_time_utc = _as_naive_utc(vm.get("end_time"))
    if since is not None and isinstance(since, datetime):
        cli_start_time_utc = _as_naive_utc(since)
    if until is not None and isinstance(until, datetime):
        cli_end_time_utc = _as_naive_utc(until)
    
    # Check if the VM is in the time window by looking at the start and end times of the VM[start_time, end_time] 
    # and the start and end times of the CLI[since, until]. I want to include the full day of the until date.

    if cli_end_time_utc is not None:
        cli_end_time_utc = cli_end_time_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        if vm_start_time_utc >= cli_start_time_utc and vm_end_time_utc <= cli_end_time_utc:
            return True
        else:
            return False
    if cli_start_time_utc is not None:
        if vm_start_time_utc >= cli_start_time_utc:
            return True
    return False

def filter_vm_groups(grouped: dict[str, list[dict]], since: datetime | None, until: datetime | None) -> dict[str, list[dict]]:
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
            if vm_in_time_window(vm, since, until):
                if filtered.get(os_key) is None:
                    filtered[os_key] = [vm]
                else:
                    filtered[os_key].append(vm)
    return filtered


def filter_plan_records(plans: list[dict], since: datetime | None, until: datetime | None) -> list[dict]:
    """
    Filter plan records based on a given since datetime.
    Args:
        plans: Plan summary dicts. Read end_time. Leave every other field as it is.
        since: Cutoff instant, or None when no cutoff is set.
    """
    if since is None and until is None:
        return plans
    cutoff_date = _as_naive_utc(since)
    all_plans = []
    for plan in plans:
        plan_end_time = _as_naive_utc(plan["end_time"])
        if plan_end_time >= cutoff_date:
            all_plans.append(plan)
    return all_plans


def chart_cutoff(since: datetime | None, until: datetime | None, gantt_since: datetime | None, 
                 gantt_until: datetime | None) -> datetime | None:
    """
    Prefer the chart-only cutoff. Fall back to the global cutoff.

    Args:
        since: Global cutoff from --since, or None.
        until: Global cutoff from --until, or None.
        gantt_since: Chart-only cutoff from --gantt-since, or None.
        gantt_until: Chart-only cutoff from --gantt-until, or None.
    """
    # I need to return a start and an end time which could be None or a datetime object.
    # The gantt options take precedence over the global options.
    # If I have a gantt_since but no gantt_until, use the global until if available.
    start_time = None
    end_time = None 
    if gantt_since is not None:
        start_time = gantt_since
    elif since is not None:
        start_time = since
    if gantt_until is not None:
        end_time = gantt_until
    elif until is not None:
        end_time = until
    return start_time, end_time


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
