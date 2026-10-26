from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List
import typing as t

try:
    from pipeline_timing import (
        highest_gib_per_hour,
        summarize_plan_records,
        summarize_vm_records,
    )
except ModuleNotFoundError:
    from mtv_parser.pipeline_timing import (
        highest_gib_per_hour,
        summarize_plan_records,
        summarize_vm_records,
    )


class MigrationSummaryMixin:
    def _tally_plan_types(self: t.Self, migrations: list[dict]) -> tuple[int, int, int, int, int, list]:
        cold_migrations = 0
        cold_migrated_vms = 0
        warm_migrations = 0
        warm_migrated_vms = 0
        total_failed_vms = 0
        all_failed_vm_names = []
        for item in migrations:
            if item["migration_type"] == "cold":
                cold_migrations += 1
                cold_migrated_vms += item["vms"]
            if item["migration_type"] == "warm":
                warm_migrations += 1
                warm_migrated_vms += item["vms"]
            total_failed_vms += item.get("failed_vm_count", 0)
            all_failed_vm_names.extend(item.get("failed_vm_names", []))
        return (
            cold_migrations,
            cold_migrated_vms,
            warm_migrations,
            warm_migrated_vms,
            total_failed_vms,
            all_failed_vm_names,
        )

    def prepare_migration_information(self: t.Self, migrations: list[dict], active_migration_hours: int = 0) -> dict:
        """Calculate and organize overall migration statistics.

        This function computes various statistics about the migrations,
        including average time, total VMs, disk size, and transfer speeds.
        It also identifies the longest migration plan and calculates
        cold/warm migration counts.

        Args:
            migrations (List[Dict[str, Any]]): A list of migration dictionaries.
            active_migration_hours (int, optional): The number of active migration hours.

        Returns:
            Dict[str, Any]: A dictionary containing the calculated statistics.
        """
        temp_dict = defaultdict(dict)
        number_of_migrations = len(migrations)

        average_time_mins = sum(item["total_duration_mins"] for item in migrations) / number_of_migrations
        total_number_of_vms = sum(item["vms"] for item in migrations)
        total_vms_migrated = sum(item.get("vms_migrated", item["vms"]) for item in migrations)
        total_disk_size_for_migration = round(sum(item["total_disk_size"] for item in migrations) / 1024, 1)
        average_disk_size_gb = (
            round(total_disk_size_for_migration / total_vms_migrated, 1) if total_vms_migrated > 0 else 0
        )
        union_hours = self.union_interval_hours(self._intervals_from_records(migrations))
        total_migration_hrs = union_hours if union_hours > 0 else (active_migration_hours or 0)
        # Aggregate: total GiB ÷ union of active intervals (overlaps counted once)
        average_transfer_speed = (
            round(total_disk_size_for_migration / total_migration_hrs, 1) if total_migration_hrs > 0 else 0
        )

        # Find max duration and corresponding plan name
        max_minutes = max(item["total_duration_mins"] for item in migrations)
        longest_plan = next(item for item in migrations if item["total_duration_mins"] == max_minutes)
        longest_disk_size_gb = round(longest_plan["total_disk_size"] / 1024, 1)
        highest_plan_rate = highest_gib_per_hour(migrations, "total_disk_size", "total_duration_mins")
        longest_transfer_speed = 0 if highest_plan_rate is None else highest_plan_rate
        min_minutes = min(item["total_duration_mins"] for item in migrations)

        (
            cold_migrations,
            cold_migrated_vms,
            warm_migrations,
            warm_migrated_vms,
            total_failed_vms,
            all_failed_vm_names,
        ) = self._tally_plan_types(migrations)

        # Populate temp_dict with the calculated values
        temp_dict["average_disk_size_gb"] = average_disk_size_gb
        temp_dict["average_time"] = average_time_mins
        temp_dict["average_transfer_speed"] = average_transfer_speed
        temp_dict["cold_migrated_vms"] = cold_migrated_vms
        temp_dict["cold_migrations"] = cold_migrations
        temp_dict["longest_disk_size_gb"] = longest_disk_size_gb
        temp_dict["longest_plan"] = longest_plan
        temp_dict["longest_transfer_speed"] = longest_transfer_speed
        temp_dict["max_minutes"] = max_minutes
        temp_dict["min_minutes"] = min_minutes
        temp_dict["number_of_migrations"] = number_of_migrations
        temp_dict["total_disk_size_for_migration"] = total_disk_size_for_migration
        temp_dict["total_migration_hrs"] = total_migration_hrs
        temp_dict["total_number_of_vms"] = total_number_of_vms
        temp_dict["total_vms_migrated"] = total_vms_migrated  # VMs that actually transferred data
        temp_dict["total_failed_vms"] = total_failed_vms
        temp_dict["failed_vm_names"] = all_failed_vm_names
        temp_dict["warm_migrated_vms"] = warm_migrated_vms
        temp_dict["warm_migrations"] = warm_migrations
        temp_dict.update(summarize_plan_records(migrations))

        # Convert defaultdict back to regular dict before returning
        return dict(temp_dict)

    def _filter_successful_vms(
        self: t.Self,
        all_vms: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Filter and return only successfully migrated VMs with valid data.

        Args:
            all_vms (Dict[str, List[Dict[str, Any]]]): Dictionary of VMs by OS type.

        Returns:
            List[Dict[str, Any]]: List of successfully migrated VMs with valid data.
        """
        successful_vms = []
        for _, vm_list in all_vms.items():
            for vm in vm_list:
                if not vm.get("succeeded", True):
                    continue
                if not vm.get("start_time") or not vm.get("duration"):
                    continue
                successful_vms.append(vm)
        return successful_vms

    def _completion_datetime(self: t.Self, vm: Dict[str, Any]) -> datetime | None:
        """Return the VM completion instant, or None when it cannot be derived.

        add_to_dict guarantees end_time on every VM record produced by the
        normal pipeline, so the direct lookup is the expected path.
        """
        end_time = vm.get("end_time")
        if isinstance(end_time, datetime):
            return end_time
        return None

    def _utc_calendar_date(self: t.Self, value: datetime) -> date:
        """Calendar date in UTC. Naive datetimes are treated as UTC."""
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.date()

    def group_successful_vms_by_completion_date(
        self: t.Self,
        all_vms: Dict[str, List[Dict[str, Any]]],
    ) -> dict[date, list[str]]:
        """Group successful VM names under UTC completion dates.

        Names are unique per date and sorted alphabetically. Dates are sorted
        ascending. Empty input returns an empty dict.
        """
        grouped: dict[date, set[str]] = defaultdict(set)
        for vm in self._filter_successful_vms(all_vms):
            completion = self._completion_datetime(vm)
            if completion is None:
                continue
            grouped[self._utc_calendar_date(completion)].add(vm["name"])
        return {day: sorted(names) for day, names in sorted(grouped.items())}

    def _calculate_vm_transfer_speed(self: t.Self, vm: Dict[str, Any]) -> float:
        """Calculate transfer speed for a single VM in GiB/hour.

        Args:
            vm (Dict[str, Any]): VM dictionary with disk_size and duration.

        Returns:
            float: Transfer speed in GiB/hour.
        """
        hours = vm["duration"] / 60.0
        if hours == 0:
            return 0.0
        return (vm["disk_size"] / 1024) / hours

    def _calculate_vm_totals(
        self: t.Self,
        vms: List[Dict[str, Any]],
    ) -> tuple[int, float, float]:
        """Calculate total metrics for a list of VMs.

        Args:
            vms (List[Dict[str, Any]]): List of VM dictionaries.

        Returns:
            tuple: (total_vms, total_disk_gb, total_mins, total_hours)
        """
        total_vms = len(vms)
        total_disk_gb = sum(vm["disk_size"] / 1024 for vm in vms)
        total_mins = sum(vm["duration"] for vm in vms)
        return total_vms, total_disk_gb, total_mins

    def prepare_vm_inform(
        self: t.Self,
        all_vms: Dict[str, List[Dict[str, Any]]],
        concurrent_migration_hours: float = 0,
    ) -> Dict[str, Any]:
        """Calculate VM-level stats for successfully migrated VMs.

        This method computes aggregate stats at the VM level using only 
        VMs that completed successfully.

        Args:
            all_vms (Dict[str, List[Dict[str, Any]]]): Dictionary of all VMs by OS type.
            concurrent_migration_hours (float): Fallback hours if VM records have no timestamps.
                Aggregate prefers the union of effective VM intervals.

        Returns:
            Dict[str, Any]: Dictionary containing VM-level statistics or empty dict if no data.
        """
        vms = self._filter_successful_vms(all_vms)

        if not vms:
            return {}

        total_vms, total_disk_GiB, total_mins = self._calculate_vm_totals(vms)

        # Find longest and shortest VMs
        longest_running_vm = max(vms, key=lambda v: v["duration"])
        shortest_running_vm = min(vms, key=lambda v: v["duration"])
        largest_vm = max(vms, key=lambda v: v["disk_size"])
        smallest_vm = min(vms, key=lambda v: v["disk_size"])
        valid_vms_transferred_list = [vm for vm in vms if vm.get("transfer_minutes", 0) > 0]
        highest_vm_rate = highest_gib_per_hour(vms, "disk_size", "duration")
        longest_vm_speed = 0 if highest_vm_rate is None else highest_vm_rate
        avg_runtime_mins = round(total_mins / total_vms, 1)
        avg_disk_GiB = round(total_disk_GiB / total_vms, 1)

        union_hours = self.union_interval_hours(self._intervals_from_records(vms))
        total_migration_hours = union_hours if union_hours > 0 else (concurrent_migration_hours or 0)
        aggregate_speed_GiB_per_hr = (
            round(total_disk_GiB / total_migration_hours, 1) if total_migration_hours > 0 else 0.0
        )

        result = {
            "total_vms": total_vms,
            "max_minutes": round(longest_running_vm["duration"], 1),
            "longest_running_vm_name": longest_running_vm["name"],
            "largest_vm_name": largest_vm["name"],
            "largest_vm_disk_GiB": round(largest_vm["disk_size"] / 1024, 1),
            "smallest_vm_name": smallest_vm["name"],
            "smallest_vm_disk_GiB": round(smallest_vm["disk_size"] / 1024, 1),
            "longest_vm_transferspeed": longest_vm_speed,
            "min_minutes": round(shortest_running_vm["duration"], 1),
            "shortest_vm_name": shortest_running_vm["name"],
            "average_time_mins": avg_runtime_mins,
            "average_disk_size_GiB": avg_disk_GiB,
            "aggregate_speed_GiB_per_hr": aggregate_speed_GiB_per_hr,
            "total_disk_size_gb": round(total_disk_GiB, 1),
            "total_migration_hours": total_migration_hours,
        }
        if valid_vms_transferred_list:
            longest_transfer_vm = max(valid_vms_transferred_list, key=lambda vm: vm["transfer_minutes"])
            total_transfer_minutes = sum(vm["transfer_minutes"] for vm in valid_vms_transferred_list)
            total_transfer_GiB = sum(vm["disk_size"] / 1024 for vm in valid_vms_transferred_list)
            transfer_hours = total_transfer_minutes / 60
            result["longest_transfer_vm_name"] = longest_transfer_vm["name"]
            result["longest_transfer_minutes"] = longest_transfer_vm["transfer_minutes"]
            result["average_transfer_minutes"] = total_transfer_minutes / len(valid_vms_transferred_list)
            transfer_rate = round(total_transfer_GiB / transfer_hours, 1)
            highest_copy_rate = highest_gib_per_hour(
                valid_vms_transferred_list, "disk_size", "transfer_minutes"
            )
            longest_rate = 0 if highest_copy_rate is None else highest_copy_rate
            result["transfer_GiB_per_hour"] = transfer_rate
            result["transfer_gb_per_hour"] = transfer_rate
            result["longest_transfer_GiB_per_hour"] = longest_rate
            result["longest_transfer_gb_per_hour"] = longest_rate
        result.update(summarize_vm_records(vms))
        return result
