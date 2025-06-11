from collections import defaultdict
from datetime import timedelta
import os
import yaml
from clioutput import CLIOutput
from migration_information import MigrationAnalyzer  # Import the MigrationAnalyzer class


def load_multiple_plans(directory: str) -> dict:
    """Load and merge multiple MTV plan files into a single data structure."""
    merged_data = {"items": []}

    yaml_files = [
        f for f in os.listdir(directory) if f.endswith((".yaml", ".yml")) and os.path.isfile(os.path.join(directory, f))
    ]

    for file_name in yaml_files:
        file_path = os.path.join(directory, file_name)
        with open(file_path, "r") as yaml_file:
            plan_data = yaml.safe_load(yaml_file)
            if plan_data and "items" in plan_data:
                merged_data["items"].extend(plan_data["items"])

    return merged_data


def main() -> None:
    # Load YAML data

    multiple_dir = "./plans/multiple"
    single_file = "./plans/single/vm-plan-sample.yaml"

    yaml_files = [
        f
        for f in os.listdir(multiple_dir)
        if f.endswith((".yaml", ".yml")) and os.path.isfile(os.path.join(multiple_dir, f))
    ]

    if len(yaml_files) > 1:
        # Process multiple files as merged dataset
        mtv_plan_data = load_multiple_plans(multiple_dir)
    elif len(yaml_files) == 1:
        # Single file in multiple directory
        with open(os.path.join(multiple_dir, yaml_files[0]), "r") as yaml_file:
            mtv_plan_data = yaml.safe_load(yaml_file)
    else:
        # Fallback to sample file
        with open(single_file, "r") as yaml_file:
            mtv_plan_data = yaml.safe_load(yaml_file)

    # Initialize CLI output and MigrationAnalyzer
    output = CLIOutput()
    migration_analyzer = MigrationAnalyzer()

    # Initialize dictionary to hold VM migration data
    all_vms = defaultdict(list)

    # Process migration success info
    successful_migrations, failed_migrations, migration_window_for_plan = migration_analyzer.get_migration_success_info(
        mtv_plan_data, all_vms
    )

    # Ensure migration window has all hours filled
    current_hour = min(migration_window_for_plan.keys()).replace(minute=0, second=0, microsecond=0)
    end_time = max(migration_window_for_plan.keys()).replace(minute=0, second=0, microsecond=0)

    while current_hour <= end_time:
        if current_hour not in migration_window_for_plan.keys():
            migration_window_for_plan[current_hour] = 0
        current_hour += timedelta(hours=1)

    # Sort migration window by time
    sorted_migration_window_for_plan = dict(sorted(migration_window_for_plan.items()))

    # Find peak time and max concurrent migrations
    peak_time = ""
    max_concurrent = 0
    for entry in migration_window_for_plan.keys():
        if migration_window_for_plan[entry] > max_concurrent:
            max_concurrent = migration_window_for_plan[entry]
            peak_time = entry

    # Analyze concurrency
    migration_window_list = migration_analyzer.find_deployment_windows(sorted_migration_window_for_plan)
    concurrency_data = migration_analyzer.analyze_concurrent_migrations(
        migration_window_list, max_concurrent, peak_time
    )

    # Calculate active migration hours
    active_migration_hours = migration_analyzer.calculate_active_migration_hours(concurrency_data)

    # Prepare migration reports
    success_migration_report = migration_analyzer.prepare_migration_information(
        successful_migrations, active_migration_hours
    )

    if failed_migrations:
        failed_migration_report = migration_analyzer.prepare_migration_information(failed_migrations)
        output.write(output.migration_output(failed_migration_report, "failed"))
        output.write(("\n\n"))

    output.write(output.migration_output(success_migration_report, "successful"))
    output.write(("\n\n"))
    output.write(output.operating_system_report(all_vms))
    output.write(("\n\n"))
    output.write(output.generate_concurrency_report(concurrency_data))

    output.close()


if __name__ == "__main__":
    main()
