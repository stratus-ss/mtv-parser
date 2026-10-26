from datetime import datetime

try:
    from utils import as_naive_utc
except ModuleNotFoundError:
    from mtv_parser.utils import as_naive_utc


def completed_in_window(completed: datetime | None, since: datetime | None, until: datetime | None) -> bool:
    """Return whether a completion instant falls inside the report window.

    A missing completion is out. --since is midnight. --until covers that whole day.
    
    Args:
        completed: The completion time of the VM or plan.
        since: The start time of the report window.
        until: The end time of the report window.
    """
    if not isinstance(completed, datetime):
        return False
    completed_utc = as_naive_utc(completed)
    if since is not None:
        since_utc = as_naive_utc(since)
        if completed_utc < since_utc:
            return False
    if until is not None:
        until_utc = as_naive_utc(until)
        until_end = until_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        if completed_utc > until_end:
            return False
    return True


def vms_continuing_past_until(grouped: dict[str, list[dict]], open_vms: dict, since: datetime | None, until: datetime | None) -> list[dict]:
    """Return VMs that started in the window and were still going after --until.

    grouped is the unfiltered all_vms dict, so a VM that finished after the window
    is still here. open_vms holds VMs that have a start and no end; those never
    enter all_vms. A VM is listed when its start is on or before the end of the
    until day, on or after --since midnight when that flag is set, and its end is
    missing or later than the end of the until day. A VM that finished inside the
    window is left out. Nothing in this list is added to a disk total.

    until is that date at midnight. The end of the day is 23:59:59.999999 UTC,
    the same instant completed_in_window uses.

    Args:
        grouped: OS name to VM dicts that have a positive duration.
        open_vms: OS name to VM dicts that have a start and no end.
        since: --since midnight, or None when that flag is absent.
        until: --until midnight, or None. None returns an empty list.
    """
    rows = []
    if until is None:
        return rows
    for source in (grouped, open_vms):
        for vm_list in source.values():
            for vm in vm_list:
                if completed_in_window(vm.get("start_time"), since, until):
                    if not completed_in_window(vm.get("end_time"), None, until):
                        rows.append(vm)
    return rows



def filter_vm_groups(grouped: dict[str, list[dict]], since: datetime | None, until: datetime | None) -> dict[str, list[dict]]:
    """Keep VM groups whose completion falls inside the report window.
    
    Args:
        grouped: OS name to VM dicts. Each VM may have end_time (datetime).
        since: The start time of the report window.
        until: The end time of the report window.
    """
    if since is None and until is None:
        return grouped
    filtered: dict[str, list[dict]] = {}
    for os_key, vm_list in grouped.items():
        for vm in vm_list:
            if completed_in_window(vm.get("end_time"), since, until):
                if filtered.get(os_key) is None:
                    filtered[os_key] = [vm]
                else:
                    filtered[os_key].append(vm)
    return filtered


def filter_plan_records(plans: list[dict], since: datetime | None, until: datetime | None) -> list[dict]:
    """Keep plans whose end_time falls inside the report window.
    
    Args:
        plans: List of plan dictionaries. Each plan may have end_time (datetime).
        since: The start time of the report window.
        until: The end time of the report window.
    """
    if since is None and until is None:
        return plans
    all_plans = []
    for plan in plans:
        if completed_in_window(plan["end_time"], since, until):
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
