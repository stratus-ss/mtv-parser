from collections import defaultdict
from datetime import timedelta
import argparse
import os
import yaml
from clioutput import CLIOutput
from migration_information import MigrationAnalyzer  # Import the MigrationAnalyzer class
from since_filter import (
    chart_cutoff,
    filter_plan_records,
    filter_vm_groups,
    parse_since_date,
    rebuild_hour_window,
)
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
    parser.add_argument(
        "--since",
        type=parse_since_date,
        default=None,
        help=(
            "Limit reports and the Gantt chart to migrations that overlap this UTC date "
            "through the latest data (YYYY-MM-DD)."
        ),
    )
    parser.add_argument(
        "--gantt-since",
        type=parse_since_date,
        default=None,
        help=(
            "Limit only the Gantt chart to migrations that overlap this UTC date (YYYY-MM-DD). "
            "Text reports stay on the full set when this flag is used alone."
        ),
    )

    parser.add_argument(
        "--until",
        type=parse_since_date,
        default=None,
        help=(
            "Limit reports and the Gantt chart to migrations that end on or before this UTC date "
            "until the date specified."
        ),
    )
    parser.add_argument(
        "--gantt-until",
        type=parse_since_date,
        default=None,
        help=(
            "Limit only the Gantt chart to migrations that end on or before this UTC date (YYYY-MM-DD). "
            "Text reports stay on the full set when this flag is used alone."
        ),
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


def _load_mtv_plan_data() -> dict:
    """Load plan YAML from plans/multiple, or the single-file fallback."""
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
        return load_multiple_plans(multiple_dir)
    if len(yaml_files) == 1:
        return load_plan_file(os.path.join(multiple_dir, yaml_files[0]))
    if os.path.isfile(single_file):
        return load_plan_file(single_file)
    raise FileNotFoundError(
        "No plan YAML found. Put one or more .yaml/.yml files in "
        f"{multiple_dir}/, or provide {single_file}."
    )


def _apply_since(
    args: argparse.Namespace,
    analyzer: MigrationAnalyzer,
    all_vms: dict,
    successful_migrations: list,
    failed_migrations: list,
    migration_window: dict,
) -> tuple[dict, list, list, dict]:
    """Filter reports when --since is set. A missing cutoff leaves inputs unchanged."""
    # TODO(range): Filter when either report bound is set, not only when --since is set.
    # Pass the report window into filter_vm_groups and filter_plan_records.
    if args.since is not None:
        all_vms = filter_vm_groups(all_vms, args.since, args.until)
        successful_migrations = filter_plan_records(successful_migrations, args.since, args.until)
        failed_migrations = filter_plan_records(failed_migrations, args.since, args.until)
        rebuilt = rebuild_hour_window(analyzer, all_vms)
        if rebuilt:
            migration_window = rebuilt
    return all_vms, successful_migrations, failed_migrations, migration_window


def _fill_missing_hours(migration_window: dict) -> None:
    """Insert zero counts for hours between the first and last window key."""
    current_hour = min(migration_window.keys()).replace(minute=0, second=0, microsecond=0)
    end_time = max(migration_window.keys()).replace(minute=0, second=0, microsecond=0)
    while current_hour <= end_time:
        if current_hour not in migration_window:
            migration_window[current_hour] = 0
        current_hour += timedelta(hours=1)


def _peak_concurrency(migration_window: dict) -> tuple:
    """Return (peak_time, max_concurrent). peak_time is a datetime or empty string."""
    peak_time: object = ""
    max_concurrent = 0
    for entry, count in migration_window.items():
        if count > max_concurrent:
            max_concurrent = count
            peak_time = entry
    return peak_time, max_concurrent


def _write_migration_reports(output, analyzer, successful_migrations, failed_migrations, all_vms, concurrency_data) -> None:
    success_migration_report = analyzer.prepare_migration_information(successful_migrations)
    if failed_migrations:
        failed_migration_report = analyzer.prepare_migration_information(failed_migrations)
        output.write(output.migration_output(failed_migration_report, "failed", include_main_header=True))
        output.write(("\n\n"))
        output.write(("\n\n"))
        output.write(output.migration_output(success_migration_report, "successful", include_main_header=False))
        output.write(("\n\n"))
    else:
        output.write(output.migration_output(success_migration_report, "successful", include_main_header=True))
        output.write(("\n\n"))

    vm_summary = analyzer.prepare_vm_inform(all_vms)
    if vm_summary:
        output.write(output.vm_migration_output(vm_summary))
        output.write(("\n\n"))

    output.write(output.operating_system_report(all_vms))
    output.write(("\n\n"))
    output.write(output.generate_concurrency_report(concurrency_data))


def _write_gantt(args, output, all_vms) -> None:
    if not args.gantt:
        return
    cutoff_start, cutoff_end = chart_cutoff(args.since, args.until, args.gantt_since, args.gantt_until)
    if cutoff_start is not None and cutoff_end is not None:
        chart_vms = filter_vm_groups(all_vms, cutoff_start, cutoff_end)
    else:
        chart_vms = all_vms
    chart_path = plot_gantt_chart(chart_vms, output_path=args.gantt_output)
    if chart_path:
        output.write(f"\nGantt chart saved to {chart_path}\n")
    else:
        output.write("\nNo VM timing data available for Gantt chart.\n")


def main() -> None:
    args = parse_args()
    # TODO(range): Validate the report window and the chart window before loading plans.
    mtv_plan_data = _load_mtv_plan_data()
    output = CLIOutput()
    migration_analyzer = MigrationAnalyzer()
    all_vms = defaultdict(list)

    successful_migrations, failed_migrations, migration_window_for_plan = migration_analyzer.get_migration_success_info(
        mtv_plan_data, all_vms
    )
    all_vms, successful_migrations, failed_migrations, migration_window_for_plan = _apply_since(
        args,
        migration_analyzer,
        all_vms,
        successful_migrations,
        failed_migrations,
        migration_window_for_plan,
    )

    if not migration_window_for_plan:
        # TODO(range): Keep this early return when the report window removes every migration.
        output.write("No migration data available. Please ensure your YAML files contain completed migrations.\n")
        output.close()
        return

    _fill_missing_hours(migration_window_for_plan)
    sorted_migration_window_for_plan = dict(sorted(migration_window_for_plan.items()))
    peak_time, max_concurrent = _peak_concurrency(migration_window_for_plan)
    migration_window_list = migration_analyzer.find_deployment_windows(sorted_migration_window_for_plan)
    concurrency_data = migration_analyzer.analyze_concurrent_migrations(
        migration_window_list, max_concurrent, peak_time
    )
    _write_migration_reports(
        output,
        migration_analyzer,
        successful_migrations,
        failed_migrations,
        all_vms,
        concurrency_data,
    )
    _maybe_write_vms_by_date(args, output, migration_analyzer, all_vms)
    _write_gantt(args, output, all_vms)
    output.close()


if __name__ == "__main__":
    main()
