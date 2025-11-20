from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Union
import typing as t
import math


class MigrationAnalyzer:
    def __init__(self: t.Self) -> None:
        """Initialize the MigrationAnalyzer class."""
        pass

    def add_migration_attribute(self: t.Self, vm: Dict[str, Any]) -> Dict[str, Any]:
        """Add a 'migration_type' attribute to the VM dictionary.

        Args:
            vm (Dict[str, Any]): A dictionary containing VM information.

        Returns:
            Dict[str, Any]: The updated VM dictionary with the 'migration_type' attribute.
        """
        warm_migration_present = vm.get("warm")
        if warm_migration_present:
            vm["migration_type"] = "warm"
        else:
            vm["migration_type"] = "cold"
        return vm

    def add_to_dict(self: t.Self, vm_information: dict, dict_to_update: dict, effective_duration: float) -> list[dict]:
        """Add VM information to a dictionary.

        This function takes VM information, calculates the transfer end time, and appends
        the VM details to a specified dictionary. It handles cases where start time or
        duration are missing.

        Args:
            vm_information (dict): A dictionary containing VM information.
            dict_to_update (dict): The dictionary to update with the VM details.
            effective_duration (float): The effective duration of the migration.

        Returns:
            list[dict]: The updated dictionary with the added VM information.
        """
        dict_key = next(iter(vm_information.keys()))
        transfer_start = vm_information[dict_key]["start_time"]
        transfer_end_time = transfer_start + timedelta(minutes=effective_duration)

        if not transfer_start or not effective_duration:
            dict_to_update

        dict_to_update[dict_key].append(
            {
                "name": vm_information[dict_key]["name"],
                "disk_size": vm_information[dict_key]["disk_size"],
                "start_time": transfer_start,
                "end_time": transfer_end_time,
                "duration": effective_duration,
            }
        )

        return dict_to_update

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

    def calculate_active_migration_hours(self: t.Self, mtv_plan_data: dict) -> float:
        """Calculate total active migration time by summing all plan durations.

        This method sums the actual time each migration plan was actively transferring data.
        It does this by extracting start and completion timestamps from each migration plan's
        status.migration section.

        Args:
            mtv_plan_data (dict): The full migration plan data dict.

        Returns:
            float: Total hours of active data transfer across all migration plans.
        """
        total_seconds = 0

        for entry in mtv_plan_data["items"]:
            migration_status = entry.get("status", {}).get("migration", {})

            if "started" in migration_status and "completed" in migration_status:
                start = datetime.fromisoformat(migration_status["started"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(migration_status["completed"].replace("Z", "+00:00"))
                duration = (end - start).total_seconds()
                total_seconds += duration

        total_hours = total_seconds / 3600
        return round(total_hours, 2)

    def calculate_effective_migration_time(self: t.Self, vm: Dict[str, Any], entry: Dict[str, Any]) -> float:
        """Calculate the effective migration time based on precopy duration drops.

        This function calculates the effective migration time for a VM, considering
        precopy durations for warm migrations. It identifies significant drops in
        precopy duration and uses that to determine the effective time. For cold
        migrations or those without precopy data, it uses the standard migration
        start and end times.

        Args:
            vm (Dict[str, Any]): A dictionary containing VM information, including migration type and precopy details.
            entry (Dict[str, Any]): A dictionary containing migration status, including start and end times.

        Returns:
            float: The effective migration time in minutes.
        """
        significant_drop_threshold = 0.5  # 50% drop

        # Find all precopies for this VM
        all_precopies = []
        warm_migration_present = vm.get("migration_type")

        if warm_migration_present == "warm" and "precopies" in vm["warm"]:
            for precopy in vm["warm"]["precopies"]:
                if "start" in precopy and "end" in precopy:
                    start_time = datetime.fromisoformat(precopy["start"])
                    end_time = datetime.fromisoformat(precopy["end"])
                    duration = (end_time - start_time).total_seconds() / 60  # Minutes
                    all_precopies.append({"start": start_time, "end": end_time, "duration": duration})

            # Sort precopies by start time
            all_precopies.sort(key=lambda x: x["start"])

            if not all_precopies:
                # Fallback to regular migration times if no precopies
                start = datetime.fromisoformat(entry["status"]["migration"]["started"])
                end = datetime.fromisoformat(entry["status"]["migration"]["completed"])
                return (end - start).total_seconds() / 60

            # Get the start time from the first precopy
            migration_start = all_precopies[0]["start"]

            # Get the initial duration
            initial_duration = all_precopies[0]["duration"]

            # Find when the precopy duration drops significantly
            migration_end = all_precopies[-1]["end"]  # Default to the last precopy

            for i in range(1, len(all_precopies)):
                current_duration = all_precopies[i]["duration"]
                # If we find a significant drop from the initial duration
                if current_duration < initial_duration * significant_drop_threshold:
                    migration_end = all_precopies[i]["end"]
                    break

            # Calculate effective migration time in minutes
            effective_minutes = (migration_end - migration_start).total_seconds() / 60
            return effective_minutes
        else:
            # Handle cold migration
            start = datetime.fromisoformat(entry["status"]["migration"]["started"])
            end = datetime.fromisoformat(entry["status"]["migration"]["completed"])
            return (end - start).total_seconds() / 60

    def extract_vm_information(
        self: t.Self,
        vm: Dict[str, Any],
        effective_duration: float,
    ) -> Dict[str, Dict[str, Union[int, timedelta]]]:
        """Extract VM information, including disk size and transfer details.

        This function processes a single VM's information, calculates its total disk size,
        transfer start and end times, and duration. It also determines the VM's migration
        window based on the effective duration.

        Args:
            vm (Dict[str, Any]): A dictionary containing VM information.
            effective_duration (float): The effective duration of the migration in minutes.

        Returns:
            Dict[str, Dict[str, Union[int, timedelta]]]: A dictionary containing the extracted VM information,
            including disk size, start time, duration, migration type, and migration window.
        """
        total_disk_size = 0
        total_disk_transfer_time = timedelta(seconds=0)
        disk_transfer_start_time = timedelta(seconds=0)
        vm_information = {}

        os_name = vm.get("operatingSystem", "unknown")
        vm_name = vm.get("name")
        vm_pending = False

        for phase in vm["pipeline"]:
            try:
                if (phase["name"] == "DiskTransfer" and phase["phase"] == "Pending") or (
                    phase["name"] == "DiskTransferV2v" and phase["phase"] == "Pending"
                ):
                    vm_pending = True
                elif phase["phase"] == "Pending":
                    pass
                elif (phase["name"] == "DiskTransfer" and "progress" in phase and "total" in phase["progress"]) or (
                    phase["name"] == "DiskTransferV2v" and "progress" in phase and "total" in phase["progress"]
                ):
                    total_disk_size += phase["progress"]["total"]
                    disk_transfer_start_time = datetime.fromisoformat(phase["started"])
                    disk_transfer_end_time = datetime.fromisoformat(phase["completed"])
                    total_disk_transfer_time = disk_transfer_end_time - disk_transfer_start_time
            except KeyError:
                pass

        duration = total_disk_transfer_time.total_seconds() / 60

        # If a vm is pending, it will not have a migration window so skip
        if vm_pending:
            migration_window = None
        else:
            migration_window = self.get_migration_time_range(disk_transfer_start_time, effective_duration)

        vm_information.update(
            {
                os_name: {
                    "name": vm_name,
                    "disk_size": total_disk_size,
                    "start_time": disk_transfer_start_time,
                    "duration": duration,
                    "migration_type": vm["migration_type"],
                    "migration_window": migration_window,
                }
            }
        )
        return vm_information

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

    def _create_migration_dict(
        self: t.Self,
        entry: dict,
        vm_information: dict,
        effective_duration: float,
        total_disk_size: int,
        vm_names: list[str],
    ) -> dict:
        """Create a dictionary summarizing migration details for a migration entry.

        This function compiles relevant migration information such as duration, VM count,
        disk size, migration type, and migration window into a single dictionary for reporting.

        Args:
            entry (dict): The migration entry containing metadata and status.
            vm_information (dict): Information about the VMs involved in the migration.
            effective_duration (float): The effective duration of the migration in minutes.
            total_disk_size (int): The total disk size migrated.
            vm_names (list[str]): The names of the VMs involved in the migration.

        Returns:
            dict: A dictionary summarizing the migration details.
        """
        vm_data = next(iter(vm_information.values()))
        return {
            "name": entry["metadata"]["name"],
            "total_duration_mins": effective_duration,
            "vms": len(entry["spec"]["vms"]),
            "vms_failed": str(
                any(
                    condition["type"] != "Succeeded"
                    for condition in entry["status"]["migration"]["vms"][0]["conditions"]
                )
            ),
            "total_disk_size": total_disk_size,
            "duration": effective_duration,
            "start_time": vm_data["start_time"],
            "migration_type": vm_data["migration_type"],
            "vm_names": vm_names,
            "migration_window": vm_data.get("migration_window"),
        }

    def _process_vm_entries(
        self: t.Self,
        entry: dict,
        all_vms: dict,
        migration_window_for_plan: dict,
    ) -> tuple[
        dict,  # vm_information
        float,  # effective_duration
        int,  # total_disk_size
        list,  # vm_names
        dict,  # all_vms
        bool,  # vms_failed
        dict,  # migration_window_for_plan
        int,  # processed_vm_count
    ]:
        total_disk_size = 0
        vm_names = []
        vms_failed = False
        vm_information = None  # To store the last VM's information
        effective_duration = 0  # To store the last VM's duration
        processed_vm_count = 0

        # Process all VMs for this migration entry
        for vm in entry["status"]["migration"]["vms"]:
            # Process VM and extract information
            new_vm_object = self.add_migration_attribute(vm)
            effective_duration = self.calculate_effective_migration_time(new_vm_object, entry)
            vm_names.append(new_vm_object["name"])
            vm_information = self.extract_vm_information(new_vm_object, effective_duration)
            os_type = next(iter(vm_information))
            vm_data = vm_information[os_type]
            # Only count VMs that have valid data
            if vm_data["start_time"] and effective_duration:
                processed_vm_count += 1
                total_disk_size += vm_data["disk_size"]
                # Update all_vms with VM information
                self.add_to_dict(vm_information, all_vms, effective_duration)

            # Check for VM failure
            for condition in new_vm_object["conditions"]:
                if condition["type"] != "Succeeded":
                    vms_failed = True
                    break

            # Update migration window information
            if vm_data.get("migration_window"):
                for window in vm_data["migration_window"]:
                    migration_window_for_plan[window] = migration_window_for_plan.get(window, 0) + 1
        return (
            vm_information,
            effective_duration,
            total_disk_size,
            vm_names,
            all_vms,
            vms_failed,
            migration_window_for_plan,
            processed_vm_count,
        )

    def get_migration_success_info(self: t.Self, mtv_plan_data: dict, all_vms: dict) -> tuple[list, list, dict]:
        """Process migration data and extract success/failure information.

        This function iterates through migration plan data, extracts information about each
        VM's migration, including disk size, duration, and success/failure status. It
        categorizes migrations into successful and failed lists and also tracks migration
        windows.

        Args:
            mtv_plan_data (dict): A dictionary containing migration plan data.
            all_vms (dict): A dictionary to store individual VM migration details.

        Returns:
            Tuple[list, list, dict]: A tuple containing a list of successful migrations,
            a list of failed migrations, and a dictionary of migration windows.
        """
        migration_window_for_plan = {}
        successful_migrations = []
        failed_migrations = []

        for entry in mtv_plan_data["items"]:
            # Skip entries without completion data
            if "completed" not in entry["status"]["migration"]:
                continue

            (
                vm_information,
                effective_duration,
                total_disk_size,
                vm_names,
                all_vms,
                vms_failed,
                migration_window_for_plan,
                processed_vm_count,
            ) = self._process_vm_entries(entry, all_vms, migration_window_for_plan)

            # Skip if no VMs were processed
            if not vm_information or processed_vm_count == 0:
                continue

            # Create migration dictionary using processed VM count
            migration_dict = self._create_migration_dict(
                entry, vm_information, effective_duration, total_disk_size, vm_names
            )

            # Categorize migration based on success/failure
            if vms_failed:
                failed_migrations.append(migration_dict)
            else:
                successful_migrations.append(migration_dict)

        return successful_migrations, failed_migrations, migration_window_for_plan

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
        total_disk_size_for_migration = sum(item["total_disk_size"] for item in migrations) / 1024
        total_migration_hrs = active_migration_hours if active_migration_hours is not None else 0

        average_disk_size_gb = total_disk_size_for_migration / number_of_migrations
        # Calculate aggregate transfer speed: total GB ÷ total active hours
        average_transfer_speed = (
            round(total_disk_size_for_migration / total_migration_hrs, 2) if total_migration_hrs > 0 else 0
        )

        # Find max duration and corresponding plan name
        max_minutes = max(item["total_duration_mins"] for item in migrations)
        longest_plan = next(item for item in migrations if item["total_duration_mins"] == max_minutes)
        longest_disk_size_gb = longest_plan["total_disk_size"] / 1024
        longest_transfer_speed = longest_disk_size_gb / max_minutes if max_minutes > 0 else 0
        min_minutes = min(item["total_duration_mins"] for item in migrations)

        cold_migrations = 0
        cold_migrated_vms = 0
        warm_migrations = 0
        warm_migrated_vms = 0

        for item in migrations:
            if item["migration_type"] == "cold":
                cold_migrations += 1
                cold_migrated_vms += item["vms"]
            if item["migration_type"] == "warm":
                warm_migrations += 1
                warm_migrated_vms += item["vms"]

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
        temp_dict["warm_migrated_vms"] = warm_migrated_vms
        temp_dict["warm_migrations"] = warm_migrations

        # Convert defaultdict back to regular dict before returning
        return dict(temp_dict)

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
