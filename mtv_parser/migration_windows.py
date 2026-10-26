from datetime import datetime, timedelta
from typing import Any, Dict, List
import typing as t
import math


class MigrationWindowsMixin:
    def analyze_concurrent_migrations(
        self: t.Self,
        migration_plan_by_hour: datetime,
        max_concurrent_total: int,
        peak_time: datetime,
    ) -> Dict[str, Any]:
        """Analyze concurrent VM migrations based on transfer start times and durations.

        This function analyzes the concurrency of VM migrations by examining hourly data.
        It calculates the average concurrent VMs for each plan and overall, and also
        provides hourly concurrent VM counts.

        Args:
            migration_plan_by_hour (datetime): Hourly migration plan data.
            max_concurrent_total (int): Maximum concurrent VMs observed.
            peak_time (datetime): Time of peak concurrency.

        Returns:
            Dict[str, Any]: A dictionary containing analysis results, including maximum concurrent VMs,
            peak time, average concurrent VMs per plan, overall average, and hourly counts.
        """
        migration_plan_hourly_concurrent_vms = []
        avg_concurrent_vms_per_plan = []
        
        # Track totals for weighted average calculation
        total_vm_hours = 0
        total_hours = 0

        # Format hourly data for report
        for migration_plan in migration_plan_by_hour:
            migration_plan_hourly_concurrent_vms.append(
                [{"hour": hour, "vms": count} for hour, count in sorted(migration_plan.items())]
            )
            plan_avg = self.get_avg_concurrent_count(migration_plan)
            avg_concurrent_vms_per_plan.append([plan_avg])
            
            total_vm_hours += sum(migration_plan.values())
            total_hours += len(migration_plan)

        overall_average_concurrent_vms = total_vm_hours / total_hours if total_hours > 0 else 0

        return {
            "max_concurrent_total": max_concurrent_total,
            "peak_time": peak_time,
            "average_concurrent_vms": avg_concurrent_vms_per_plan,
            "overall_average_concurrent_vms": math.ceil(overall_average_concurrent_vms),
            "hourly_concurrent_vms": migration_plan_hourly_concurrent_vms,
        }

    def get_avg_concurrent_count(self: t.Self, hourly_counts: dict) -> int:
        """Calculate the average concurrent count from hourly counts.

        This function takes a dictionary of hourly counts and calculates the average
        concurrent count, excluding hours with zero VMs (only counting active migration hours).
        The result is rounded up to the nearest integer.

        Args:
            hourly_counts (dict): A dictionary with datetime keys and VM counts as values.

        Returns:
            int: The average concurrent count for active hours, rounded up to the nearest integer.
        """
        # Only count hours with active migrations
        active_hours = {}
        for hour, vm_count in hourly_counts.items():
            if vm_count > 0:
                active_hours[hour] = vm_count
        
        if not active_hours:
            return 0
        
        number_of_hours = len(active_hours)
        total_count = sum(active_hours.values())
        average_per_hour = round((total_count / number_of_hours), 1)
        return math.ceil(average_per_hour)

    def union_interval_hours(self: t.Self, intervals: List[tuple[datetime, datetime]]) -> float:
        """Return hours covered by the union of [start, end] intervals.

        Overlapping and touching intervals are merged so concurrent work is counted
        once. Gaps with no activity are excluded. The same formula is used for one
        VM or many plans.
        """
        valid = [(start, end) for start, end in intervals if start and end and end > start]
        if not valid:
            return 0.0

        valid.sort(key=lambda interval: interval[0])
        merged = [valid[0]]
        for start, end in valid[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        total_seconds = sum((end - start).total_seconds() for start, end in merged)
        return total_seconds / 3600.0

    def _intervals_from_records(self: t.Self, records: List[Dict[str, Any]]) -> List[tuple[datetime, datetime]]:
        """Build datetime intervals from records with start_time and duration or end_time."""
        intervals: List[tuple[datetime, datetime]] = []
        for record in records:
            start = record.get("start_time")
            if not isinstance(start, datetime):
                continue
            end = record.get("end_time")
            if not isinstance(end, datetime):
                duration = record.get("duration") or record.get("total_duration_mins")
                if not duration:
                    continue
                end = start + timedelta(minutes=duration)
            intervals.append((start, end))
        return intervals

    def calculate_active_migration_hours(self: t.Self, mtv_plan_data: dict) -> float:
        """Hours covered by the union of plan started/completed timestamps.

        Overlapping plans count once. Prefer union of effective VM/plan intervals
        for aggregate GiB/hour; this YAML clock is a fallback.
        """
        intervals: List[tuple[datetime, datetime]] = []
        for entry in mtv_plan_data.get("items", []):
            migration_status = entry.get("status", {}).get("migration", {})
            if "started" in migration_status and "completed" in migration_status:
                start = datetime.fromisoformat(migration_status["started"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(migration_status["completed"].replace("Z", "+00:00"))
                intervals.append((start, end))
        return self.union_interval_hours(intervals)

    def find_deployment_windows(self: t.Self, data: Dict, threshold_hours: int = 28) -> List[dict]:
        """Identify deployment windows based on a threshold of zero VMs.

        This function analyzes a dictionary of VM counts over time and identifies
        periods where the VM count is zero for a specified duration (threshold).
        These periods are considered deployment windows.

        Args:
            data (Dict[datetime, int]): A dictionary with datetime keys and VM counts as values.
            threshold_hours (int): The number of consecutive hours of zero VMs required to define a
                                   deployment window. Defaults to 28.

        Returns:
            List[Dict[datetime, int]]: A list of dictionaries, each representing a deployment window with datetime keys and
            corresponding VM counts.
        """
        sorted_data = dict(sorted(data.items()))
        deployment_windows = []
        current_window = {}
        zero_count = 0

        for time, vms in sorted_data.items():
            if vms == 0:
                zero_count += 1
            else:
                zero_count = 0

            if zero_count >= threshold_hours:
                if current_window:
                    deployment_windows.append(current_window)
                    current_window = {}

            if vms > 0:
                current_window[time] = vms

        if current_window:
            deployment_windows.append(current_window)

        return deployment_windows

    def get_migration_time_range(self: t.Self, start_time: datetime, duration: float) -> list:
        """Calculate the hourly timestamps for a migration.

        This function calculates the hourly timestamps for a migration based on its start time and duration.
        It returns a list of hourly timestamps from the start of the migration to its end.

        Args:
            start_time (datetime): The start time of the migration.
            duration (float): The duration of the migration in minutes.

        Returns:
            list: A list of hourly timestamps.
        """
        end_time = start_time + timedelta(minutes=duration)
        current_hour = start_time.replace(minute=0, second=0, microsecond=0)
        hourly_timestamps = []
        end_datetime = end_time.replace(minute=0, second=0, microsecond=0)

        while current_hour <= end_datetime:
            hourly_timestamps.append(current_hour)
            current_hour += timedelta(hours=1)

        return hourly_timestamps

    def sort_migration_events(
        self: t.Self,
        all_vms: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Sort migration events by start time.

        This function processes a dictionary of VMs and their migration details,
        extracts start and end times for each migration event, and sorts these
        events chronologically.

        Args:
            all_vms (Dict[str, List[Dict[str, Any]]]): A dictionary of VMs with their migration details.

        Returns:
            List[Dict[str, Any]]: A list of sorted migration events.
        """
        events = []

        # Process the all_vms dictionary
        for os_type, vms in all_vms.items():
            for vm in vms:
                vm_name = vm["name"]

                # Extract start time and calculate end time
                start_time = vm.get("start_time")
                transfer_time_minutes = vm.get("duration")

                # Skip if we don't have the necessary time data
                if not start_time or not transfer_time_minutes:
                    continue

                # Calculate end time by adding transfer time (in minutes) to start time
                end_time = start_time + timedelta(minutes=transfer_time_minutes)

                # Add a single event with both start and end times
                events.append(
                    {
                        "time": start_time,
                        "type": "start",
                        "os": os_type,
                        "name": vm_name,
                        "duration": transfer_time_minutes,
                        "event_end": end_time,
                    }
                )

                events.append(
                    {
                        "time": end_time,
                        "type": "end",
                        "os": os_type,
                        "name": vm_name,
                        "duration": transfer_time_minutes,
                    }
                )

        # Sort events by start time
        events.sort(key=lambda x: x["time"])

        return events
