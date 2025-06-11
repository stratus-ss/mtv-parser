from datetime import datetime
from typing import Any, Dict


def calculate_effective_migration_time(vm: Dict[str, Any], entry: Dict[str, Any]) -> float:
    """
    Calculate the effective migration time based on when the precopy duration drops significantly.

    Args:
        vm (Dict[str, Any]): A dictionary containing VM information.
        entry (Dict[str, Any]): A dictionary containing migration status.

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
