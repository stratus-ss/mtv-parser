from collections import defaultdict
from datetime import timedelta
import argparse
import os
import yaml
from clioutput import CLIOutput
from migration_information import MigrationAnalyzer  # Import the MigrationAnalyzer class
from visualization import plot_gantt_chart


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze MTV migration plan YAML files.")
    parser.add_argument(
        "--gantt",
        action="store_true",
        help="Generate a Gantt chart PNG under charts/ (off by default).",
    )
    parser.add_argument(
        "--gantt-output",
        default="charts/migration_gantt_chart.png",
        help="Path for the Gantt chart PNG when --gantt is set (default: charts/migration_gantt_chart.png).",
    )
    parser.add_argument(
        "--vms-by-date",
        action="store_true",
        help="Print successful VM names grouped by UTC completion date (off by default).",
    )
    return parser.parse_args()


def _maybe_write_vms_by_date(args: argparse.Namespace, output, analyzer, all_vms) -> None:
    """Write the optional UTC-date VM grouping when --vms-by-date is set."""
    if not args.vms_by_date:
        return
    grouped = analyzer.group_successful_vms_by_completion_date(all_vms)
    output.write("\n\n")
    output.write(output.vms_by_date_output(grouped))


def normalize_plan_data(plan_data: dict | None) -> dict:
    """Normalize loaded YAML into a dict with an items list of Plan objects.

    Handles both:
    - List structures with an "items" key (e.g. `oc get plan -A -o yaml`)
    - Individual Plan objects (single plan per file)
    """
    if not plan_data:
        return {"items": []}
    if "items" in plan_data:
        return {"items": list(plan_data["items"] or [])}
    if plan_data.get("kind") == "Plan":
        return {"items": [plan_data]}
    return {"items": []}


def load_plan_file(file_path: str) -> dict:
    """Load a single YAML file and normalize it to {items: [...]}."""
    with open(file_path, "r") as yaml_file:
        return normalize_plan_data(yaml.safe_load(yaml_file))


def load_multiple_plans(directory: str) -> dict:
    """Load and merge multiple MTV plan files into a single data structure."""
    merged_data = {"items": []}

    yaml_files = [
        f for f in os.listdir(directory) if f.endswith((".yaml", ".yml")) and os.path.isfile(os.path.join(directory, f))
    ]

    for file_name in yaml_files:
        file_path = os.path.join(directory, file_name)
        merged_data["items"].extend(load_plan_file(file_path)["items"])

    return merged_data


def main() -> None:
    args = parse_args()

    # Load YAML data
    multiple_dir = "./plans/multiple"
    single_file = "./plans/single/vm-plan-sample.yaml"

    yaml_files = []
    if os.path.isdir(multiple_dir):
        yaml_files = [
            f
            for f in os.listdir(multiple_dir)
            if f.endswith((".yaml", ".yml")) and os.path.isfile(os.path.join(multiple_dir, f))
        ]

    if len(yaml_files) > 1:
        mtv_plan_data = load_multiple_plans(multiple_dir)
    elif len(yaml_files) == 1:
        mtv_plan_data = load_plan_file(os.path.join(multiple_dir, yaml_files[0]))
    elif os.path.isfile(single_file):
        mtv_plan_data = load_plan_file(single_file)
    else:
        raise FileNotFoundError(
            "No plan YAML found. Put one or more .yaml/.yml files in "
            f"{multiple_dir}/, or provide {single_file}."
        )

    # Initialize CLI output and MigrationAnalyzer
    output = CLIOutput()
    migration_analyzer = MigrationAnalyzer()

    # Initialize dictionary to hold VM migration data
    all_vms = defaultdict(list)

    # Process migration success info
    successful_migrations, failed_migrations, migration_window_for_plan = migration_analyzer.get_migration_success_info(
        mtv_plan_data, all_vms
    )

    
    # Check if migration_window_for_plan has data
    if not migration_window_for_plan:
        output.write("No migration data available. Please ensure your YAML files contain completed migrations.\n")
        output.close()
        return
    
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

    # Prepare migration reports using union-of-intervals hours from the plan records
    success_migration_report = migration_analyzer.prepare_migration_information(successful_migrations)

    if failed_migrations:
        failed_migration_report = migration_analyzer.prepare_migration_information(failed_migrations)
        # Print header with failed report, then successful without header
        output.write(output.migration_output(failed_migration_report, "failed", include_main_header=True))
        output.write(("\n\n"))
        output.write(("\n\n"))
        output.write(output.migration_output(success_migration_report, "successful", include_main_header=False))
        output.write(("\n\n"))
    else:
        output.write(output.migration_output(success_migration_report, "successful", include_main_header=True))
        output.write(("\n\n"))

    vm_summary = migration_analyzer.prepare_vm_inform(all_vms)
    if vm_summary:
        output.write(output.vm_migration_output(vm_summary))
        output.write(("\n\n"))

    output.write(output.operating_system_report(all_vms))
    output.write(("\n\n"))
    output.write(output.generate_concurrency_report(concurrency_data))
    _maybe_write_vms_by_date(args, output, migration_analyzer, all_vms)

    if args.gantt:
        chart_path = plot_gantt_chart(all_vms, output_path=args.gantt_output)
        if chart_path:
            output.write(f"\nGantt chart saved to {chart_path}\n")
        else:
            output.write("\nNo VM timing data available for Gantt chart.\n")

    output.close()


if __name__ == "__main__":
    main()
