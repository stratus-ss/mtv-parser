# file-budget: 600 — record pipeline, still-running VM list, and the complexity split stayed over the 500-line cap
from datetime import datetime, timedelta
from typing import Any, Dict, Union
import typing as t

try:
    from pipeline_timing import (
        migration_wall_clock_seconds,
        phase_minutes,
        plan_vm_phase_averages,
        positive_phase_minutes,
    )
except ModuleNotFoundError:
    from mtv_parser.pipeline_timing import (
        migration_wall_clock_seconds,
        phase_minutes,
        plan_vm_phase_averages,
        positive_phase_minutes,
    )

try:
    from utils import as_naive_utc
except ModuleNotFoundError:
    from mtv_parser.utils import as_naive_utc

try:
    from migration_windows import MigrationWindowsMixin
    from migration_summary import MigrationSummaryMixin
except ModuleNotFoundError:
    from mtv_parser.migration_windows import MigrationWindowsMixin
    from mtv_parser.migration_summary import MigrationSummaryMixin


class MigrationAnalyzer(MigrationWindowsMixin, MigrationSummaryMixin):
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

    def add_to_dict(
        self: t.Self,
        vm_information: dict,
        dict_to_update: dict,
        succeeded: bool = True,
    ) -> list[dict]:
        """Copy a VM payload onto the OS-keyed record list.

        This function copies start time, end time, and duration from the payload.
        It skips the append when the start time or duration is missing.

        Args:
            vm_information (dict): A dictionary containing VM information.
            dict_to_update (dict): The dictionary to update with the VM details.
            succeeded (bool): Whether the VM migration succeeded. Defaults to True.

        Returns:
            list[dict]: The updated dictionary with the added VM information.
        """
        dict_key = next(iter(vm_information.keys()))
        payload = vm_information[dict_key]
        transfer_start = payload["start_time"]
        transfer_end_time = payload["end_time"]
        duration = payload["duration"]

        if not transfer_start or not duration:
            return dict_to_update

        record = {
            "name": payload["name"],
            "disk_size": payload["disk_size"],
            "start_time": transfer_start,
            "end_time": transfer_end_time,
            "duration": duration,
            "succeeded": succeeded,
        }
        record.update(positive_phase_minutes(payload))
        dict_to_update[dict_key].append(record)

        return dict_to_update

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

    def _accumulate_pipeline_phase(
        self: t.Self,
        phase: dict,
        total_disk_size: int,
        vm_pending: bool,
        transfer_minutes: float | None,
        conversion_minutes: float | None,
        guest_reboot_minutes_value: float | None,
    ) -> tuple[int, bool, float | None, float | None, float | None]:
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
            minutes = phase_minutes(phase.get("started"), phase.get("completed"))
            if minutes is not None:
                transfer_minutes = minutes
        elif phase["name"] == "ImageConversion":
            minutes = phase_minutes(phase.get("started"), phase.get("completed"))
            if minutes is not None:
                conversion_minutes = minutes
        elif phase["name"] == "WaitForGuestReboots":
            minutes = phase_minutes(phase.get("started"), phase.get("completed"))
            if minutes is not None:
                guest_reboot_minutes_value = minutes
        return total_disk_size, vm_pending, transfer_minutes, conversion_minutes, guest_reboot_minutes_value

    def extract_vm_information(
        self: t.Self,
        vm: Dict[str, Any],
        vm_started: str,
        vm_completed: str,
    ) -> Dict[str, Dict[str, Union[int, timedelta]]]:
        """Extract VM information, including disk size and the VM clock.

        Disk progress still sums into disk size. The stored interval is vm_started
        to vm_completed. Phase minutes come from phase_minutes and stay exact.

        Args:
            vm (Dict[str, Any]): A dictionary containing VM information.
            vm_started (str): VM start timestamp, or the migration start when the VM has none.
            vm_completed (str): VM completed timestamp, or the migration completed when the VM has none.

        Returns:
            Dict[str, Dict[str, Union[int, timedelta]]]: A dictionary containing the extracted VM information,
            including disk size, start time, end time, duration, migration type, and migration window.
        """
        total_disk_size = 0
        vm_information = {}

        os_name = vm.get("operatingSystem", "unknown")
        vm_name = vm.get("name")
        vm_pending = False
        transfer_minutes = None
        conversion_minutes = None
        guest_reboot_minutes_value = None

        for phase in vm["pipeline"]:
            try:
                (
                    total_disk_size,
                    vm_pending,
                    transfer_minutes,
                    conversion_minutes,
                    guest_reboot_minutes_value,
                ) = self._accumulate_pipeline_phase(
                    phase,
                    total_disk_size,
                    vm_pending,
                    transfer_minutes,
                    conversion_minutes,
                    guest_reboot_minutes_value,
                )
            except KeyError:
                pass

        start_time = as_naive_utc(vm_started)
        end_time = as_naive_utc(vm_completed)
        duration = 0.0
        if start_time is not None and end_time is not None:
            span_minutes = (end_time - start_time).total_seconds() / 60
            if span_minutes > 0:
                duration = span_minutes

        if vm_pending:
            migration_window = None
        elif duration > 0 and start_time is not None:
            migration_window = self.get_migration_time_range(start_time, duration)
        else:
            migration_window = None

        os_payload: dict[str, Any] = {
            "name": vm_name,
            "disk_size": total_disk_size,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "migration_type": vm["migration_type"],
            "migration_window": migration_window,
        }
        os_payload.update(
            positive_phase_minutes(
                {
                    "transfer_minutes": transfer_minutes,
                    "conversion_minutes": conversion_minutes,
                    "guest_reboot_wait_minutes": guest_reboot_minutes_value,
                }
            )
        )

        vm_information.update({os_name: os_payload})
        return vm_information

    def _create_migration_dict(
        self: t.Self,
        entry: dict,
        vm_information: dict,
        total_disk_size: int,
        vm_names: list[str],
        failed_vm_count: int = 0,
        failed_vm_names: list[str] = None,
        processed_vm_count: int = 0,
        plan_timing: dict[str, Any] | None = None,
    ) -> dict:
        """Create a dictionary summarizing migration details for a migration entry.

        The plan interval is status.migration started to completed, for cold and warm.

        Args:
            entry (dict): The migration entry containing metadata and status.
            vm_information (dict): Information about the VMs involved in the migration.
            total_disk_size (int): The total disk size migrated.
            vm_names (list[str]): The names of the VMs involved in the migration.
            failed_vm_count (int): The number of VMs that failed in this plan.
            failed_vm_names (list[str]): The names of VMs that failed. Defaults to None.
            processed_vm_count (int): The number of VMs that actually migrated data.

        Returns:
            dict: A dictionary summarizing the migration details.
        """
        if failed_vm_names is None:
            failed_vm_names = []

        vm_data = next(iter(vm_information.values()))
        migration = entry["status"]["migration"]
        start_time = as_naive_utc(migration["started"])
        end_time = as_naive_utc(migration["completed"])
        duration_mins = 0.0
        if start_time is not None and end_time is not None:
            span_minutes = (end_time - start_time).total_seconds() / 60
            if span_minutes > 0:
                duration_mins = span_minutes
        migration_summary = {
            "name": entry["metadata"]["name"],
            "total_duration_mins": duration_mins,
            "vms": len(entry["spec"]["vms"]),
            "vms_migrated": processed_vm_count,  # VMs that actually migrated data
            "vms_failed": str(
                any(
                    condition["type"] != "Succeeded"
                    for condition in entry["status"]["migration"]["vms"][0]["conditions"]
                )
            ),
            "failed_vm_count": failed_vm_count,
            "failed_vm_names": failed_vm_names,
            "total_disk_size": total_disk_size,
            "duration": duration_mins,
            "start_time": start_time,
            "end_time": end_time,
            "migration_type": vm_data["migration_type"],
            "vm_names": vm_names,
            "migration_window": vm_data.get("migration_window"),
        }
        if plan_timing:
            migration_summary.update(plan_timing)
        return migration_summary

    def _note_phase_minutes(
        self: t.Self,
        vm_data: dict,
        plan_transfer: list,
        plan_conversion: list,
        plan_reboot: list,
    ) -> None:
        minutes = positive_phase_minutes(vm_data)
        destinations = {
            "transfer_minutes": plan_transfer,
            "conversion_minutes": plan_conversion,
            "guest_reboot_wait_minutes": plan_reboot,
        }
        for field, destination in destinations.items():
            if field in minutes:
                destination.append(minutes[field])

    def _vm_has_failed_condition(self: t.Self, vm: dict) -> bool:
        for condition in vm["conditions"]:
            if condition["type"] == "Failed":
                return True
        return False

    def _store_vm_record(
        self: t.Self,
        vm_information: dict,
        vm_data: dict,
        all_vms: dict,
        open_vms: dict | None,
        succeeded: bool,
    ) -> tuple[bool, int]:
        if vm_data["start_time"] and vm_data.get("duration"):
            self.add_to_dict(vm_information, all_vms, succeeded)
            return True, vm_data["disk_size"]
        if (
            open_vms is not None
            and vm_data.get("end_time") is None
            and isinstance(vm_data.get("start_time"), datetime)
        ):
            self._append_open_vm(vm_information, open_vms)
        return False, 0

    def _note_migration_window(self: t.Self, vm_data: dict, migration_window_for_plan: dict) -> None:
        if vm_data.get("migration_window"):
            for window in vm_data["migration_window"]:
                migration_window_for_plan[window] = migration_window_for_plan.get(window, 0) + 1

    def _collect_vm_for_plan(
        self: t.Self,
        entry: dict,
        vm: dict,
        all_vms: dict,
        open_vms: dict | None,
        plan_transfer: list,
        plan_conversion: list,
        plan_reboot: list,
        migration_window_for_plan: dict,
    ) -> tuple:
        new_vm_object = self.add_migration_attribute(vm)
        migration = entry["status"]["migration"]
        vm_started = new_vm_object.get("started")
        vm_completed = new_vm_object.get("completed")
        if not vm_started or not vm_completed:
            vm_started = migration["started"]
            vm_completed = migration["completed"]
        vm_information = self.extract_vm_information(new_vm_object, vm_started, vm_completed)
        os_type = next(iter(vm_information))
        vm_data = vm_information[os_type]
        self._note_phase_minutes(vm_data, plan_transfer, plan_conversion, plan_reboot)
        failed = self._vm_has_failed_condition(new_vm_object)
        counted, disk_size = self._store_vm_record(vm_information, vm_data, all_vms, open_vms, not failed)
        self._note_migration_window(vm_data, migration_window_for_plan)
        return vm_information, vm_data["name"], counted, disk_size, failed

    def _process_vm_entries(
        self: t.Self,
        entry: dict,
        all_vms: dict,
        migration_window_for_plan: dict,
        open_vms: dict | None = None,
    ) -> tuple[
        dict,  # vm_information
        int,  # total_disk_size
        list,  # vm_names
        dict,  # all_vms
        bool,  # vms_failed
        dict,  # migration_window_for_plan
        int,  # processed_vm_count
        int,  # failed_vm_count
        list,  # failed_vm_names
        dict,  # plan_phase_summary
    ]:
        total_disk_size = 0
        vm_names = []
        vms_failed = False
        vm_information = None  # To store the last VM's information
        processed_vm_count = 0
        failed_vm_count = 0
        failed_vm_names = []
        plan_transfer_minutes: list[float] = []
        plan_conversion_minutes: list[float] = []
        plan_guest_reboot_minutes: list[float] = []
        # Process all VMs for this migration entry
        for vm in entry["status"]["migration"]["vms"]:
            vm_information, vm_name, counted, disk_size, failed = self._collect_vm_for_plan(
                entry,
                vm,
                all_vms,
                open_vms,
                plan_transfer_minutes,
                plan_conversion_minutes,
                plan_guest_reboot_minutes,
                migration_window_for_plan,
            )
            vm_names.append(vm_name)
            if counted:
                processed_vm_count += 1
                total_disk_size += disk_size
            if failed:
                vms_failed = True
                failed_vm_count += 1
                failed_vm_names.append(vm_name)
        plan_phase_summary = plan_vm_phase_averages(
            plan_transfer_minutes,
            plan_conversion_minutes,
            plan_guest_reboot_minutes,
        )
        total_plan_wall_clock_seconds = migration_wall_clock_seconds(entry["status"]["migration"])
        if total_plan_wall_clock_seconds is not None and total_plan_wall_clock_seconds > 0:
            plan_phase_summary["plan_wall_clock_minutes"] = total_plan_wall_clock_seconds / 60
        return (
            vm_information,
            total_disk_size,
            vm_names,
            all_vms,
            vms_failed,
            migration_window_for_plan,
            processed_vm_count,
            failed_vm_count,
            failed_vm_names,
            plan_phase_summary,
        )

    def _append_open_vm(self: t.Self, vm_information: dict, open_vms: dict) -> None:
        """Copy one still-running VM onto open_vms.

        all_vms feeds the summaries, the OS report, concurrency, and the Gantt chart.
        add_to_dict returns before appending when the duration is missing, and a VM
        with a start and no end has no duration. This writes name, disk size, start,
        and end onto open_vms so the advisory list can name that VM without putting
        its disk into those totals.
        """
        os_name = next(iter(vm_information.keys()))
        payload = vm_information[os_name]
        if os_name not in open_vms:
            open_vms[os_name] = []
        record = {
            "name": payload["name"],
            "disk_size": payload["disk_size"],
            "start_time": payload["start_time"],
            "end_time": payload.get("end_time"),
        }
        open_vms[os_name].append(record)

    def _collect_open_vms(self: t.Self, entry: dict, open_vms: dict) -> None:
        """Record still-running VMs from a plan that has no completion.

        A plan with no status.migration.completed is skipped before its VMs are read,
        so those VMs never reach add_to_dict. This walk keeps a VM that has a start
        and no end. It does not borrow a plan completion time, because this plan has none.
        """
        migration = entry.get("status", {}).get("migration", {})
        for vm in migration.get("vms", []):
            new_vm_object = self.add_migration_attribute(vm)
            if "pipeline" not in new_vm_object:
                continue
            vm_started = new_vm_object.get("started") or ""
            vm_completed = new_vm_object.get("completed") or ""
            vm_information = self.extract_vm_information(new_vm_object, vm_started, vm_completed)
            os_name = next(iter(vm_information))
            vm_data = vm_information[os_name]
            if vm_data.get("end_time") is not None:
                continue
            if not isinstance(vm_data.get("start_time"), datetime):
                continue
            self._append_open_vm(vm_information, open_vms)

    def get_migration_success_info(
        self: t.Self,
        mtv_plan_data: dict,
        all_vms: dict,
        open_vms: dict | None = None,
    ) -> tuple[list, list, dict]:
        """Process migration data and extract success/failure information.

        This function iterates through migration plan data, extracts information about each
        VM's migration, including disk size, duration, and success/failure status. It
        categorizes migrations into successful and failed lists and also tracks migration
        windows.

        Pass open_vms to collect VMs that have a start and no end. Those VMs stay out of
        all_vms, so their disks stay out of the totals. Leave open_vms as None to skip
        that list.

        Args:
            mtv_plan_data (dict): A dictionary containing migration plan data.
            all_vms (dict): A dictionary to store individual VM migration details.
            open_vms (dict | None): OS-keyed records for VMs that have a start and no end.

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
                if open_vms is not None:
                    self._collect_open_vms(entry, open_vms)
                continue

            (
                vm_information,
                total_disk_size,
                vm_names,
                all_vms,
                vms_failed,
                migration_window_for_plan,
                processed_vm_count,
                failed_vm_count,
                failed_vm_names,
                plan_phase_summary,
            ) = self._process_vm_entries(entry, all_vms, migration_window_for_plan, open_vms)

            # Skip if no VMs were processed
            if not vm_information or processed_vm_count == 0:
                continue

            migration_dict = self._create_migration_dict(
                entry,
                vm_information,
                total_disk_size,
                vm_names,
                failed_vm_count,
                failed_vm_names,
                processed_vm_count,
                plan_timing=plan_phase_summary,
            )

            # Categorize migration based on success/failure
            if vms_failed:
                failed_migrations.append(migration_dict)
            else:
                successful_migrations.append(migration_dict)

        return successful_migrations, failed_migrations, migration_window_for_plan
