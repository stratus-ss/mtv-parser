import io
import sys
import typing as t
import weakref

from tabulate import tabulate


def _sort_metric_rows(rows: list[list]) -> list[list]:
    """Sort label/value rows by the first column (metric name)."""
    return sorted(rows, key=lambda row: str(row[0]).strip().lower() if row else "")


def _append_section(rows: list[list], title: str, metric_rows: list[list]) -> None:
    """Add a titled block with metrics sorted alphabetically by label."""
    if not metric_rows:
        return
    rows.append([title])
    rows.append(["-" * len(title)])
    rows.extend(_sort_metric_rows(metric_rows))


def _tabulate_sections(preamble: list[list], sections: list[tuple[str, list[list]]]) -> str:
    rows = list(preamble)
    wrote_section = False
    for title, metric_rows in sections:
        if not metric_rows:
            continue
        if wrote_section:
            rows.append([""])
        _append_section(rows, title, metric_rows)
        wrote_section = True
    return tabulate(rows, tablefmt="plain")


class CLIOutput:
    def __init__(self: t.Self) -> None:
        # Output buffer to store output.
        self.output = io.StringIO(initial_value="\n\n", newline="\n")

        # Finalizer for flushing buffer to stdout.
        # Will be called when self is deleted or when the interpreter exits
        self._finalize = weakref.finalize(self, self.flush_output, self.output)

        # might need to track the state of this object to ensure it's closed or not
        self._closed = False

    @staticmethod
    def flush_output(output: io.StringIO, file: io.TextIOBase | None = None) -> None:
        """Write StringIO Buffer to file (or stdout).  Closes output buffer.

        Args:
            output (io.StringIO): StringIO obj containing output buffer
            file (io.TextIOBase | None, optional): File to write butter to. Defaults to stdout.
        """
        if output.closed:
            return
        # Delay setting referece to stdout so tests can capture it
        if file is None:
            file = sys.stdout
        file.write(output.getvalue())
        output.close()

    def writeline(self: t.Self, line: t.Any = "") -> None:
        """write string to output buffer.  Adds newline if line does not end with one.

        Args:
            line (str, optional): string to write to output buffer. Defaults to "".
        """
        if self._closed:
            raise ValueError("CLIOutput is already closed")
        if not isinstance(line, str):
            line: str = str(line)
        if not line.endswith("\n"):
            line = line + "\n"
        self.write(line)

    def write(self: t.Self, line: t.Any) -> None:
        """Write string to output buffer.

        Args:
            line (str): string to write to output buffer
        """
        if self._closed:
            raise ValueError("CLIOutput is already closed")
        if not isinstance(line, str):
            line: str = str(line)
        self.output.write(line)

    def close(self: t.Self) -> None:
        """Calls private finalizer for output buffer.  Finalizer will be closed and cannot be called again."""
        if not self._closed:
            self._finalize()
            self._closed = True

    def migration_output(self: t.Self, migration_info: dict, type_of_migration: str, include_main_header: bool = True) -> str:
        preamble: list[list] = []
        if include_main_header:
            report_header = "MIGRATION PLAN REPORT"
            sep = "=" * len(report_header)
            preamble.extend([[""], [report_header], [sep], [""]])

        overview: list[list] = [
            [f"The number of {type_of_migration} migration plans:", migration_info["number_of_migrations"]],
            ["The number of vms:", migration_info["total_number_of_vms"]],
            ["Number of Warm Migration Plans:", migration_info["warm_migrations"]],
            ["Number of Cold Migration Plans:", migration_info["cold_migrations"]],
            ["Number of Cold Migrated VMs:", migration_info["cold_migrated_vms"]],
            ["Number of Warm Migrated VMs:", migration_info["warm_migrated_vms"]],
        ]
        if type_of_migration == "failed" and migration_info.get("total_failed_vms", 0) > 0:
            overview.append(["Number of VMs that failed:", migration_info["total_failed_vms"]])
            failed_vm_names = migration_info.get("failed_vm_names", [])
            if failed_vm_names:
                overview.append(["Failed VM names:", ", ".join(failed_vm_names)])
            total_vms_migrated = migration_info.get("total_vms_migrated", 0)
            if total_vms_migrated > 0:
                overview.append(["Number of VMs that migrated data:", total_vms_migrated])

        effective_runtime: list[list] = [
            ["Average disk size (GiB):", f"{migration_info['average_disk_size_gb']:.1f}"],
            ["Average runtime in minutes:", f"{migration_info['average_time']:.1f}"],
            ["Longest plan GiB/hour over plan runtime:", f"{migration_info['longest_transfer_speed']:.1f}"],
            ["Longest runtime in minutes:", f"{migration_info['max_minutes']:.1f}"],
            ["Plan with longest runtime:", migration_info["longest_plan"]["name"]],
            ["Shortest runtime in minutes:", f"{migration_info['min_minutes']:.1f}"],
            ["Total disk size in longest plan (GiB):", migration_info["longest_disk_size_gb"]],
        ]

        pipeline_timing: list[list] = []
        if migration_info.get("average_plan_wall_clock_minutes") is not None:
            pipeline_timing.extend(
                [
                    [
                        "Average plan duration minutes (migration started to completed):",
                        f"{migration_info['average_plan_wall_clock_minutes']:.1f}",
                    ],
                    ["Longest plan duration minutes:", f"{migration_info['longest_plan_wall_clock_minutes']:.1f}"],
                    ["Plan with longest duration:", migration_info.get("longest_plan_wall_clock_name", "")],
                ]
            )
        if migration_info.get("average_plan_disk_transfer_minutes") is not None:
            pipeline_timing.append(
                [
                    "Average disk transfer minutes per plan:",
                    f"{migration_info['average_plan_disk_transfer_minutes']:.1f}",
                ]
            )
        if migration_info.get("average_plan_conversion_minutes") is not None:
            pipeline_timing.append(
                [
                    "Average disk conversion minutes per plan:",
                    f"{migration_info['average_plan_conversion_minutes']:.1f}",
                ]
            )
        if migration_info.get("average_plan_guest_reboot_wait_minutes") is not None:
            pipeline_timing.extend(
                [
                    [
                        "Average guest reboot wait minutes per plan (Windows):",
                        f"{migration_info['average_plan_guest_reboot_wait_minutes']:.1f}",
                    ],
                    [
                        "Plans with at least one WaitForGuestReboots VM:",
                        migration_info.get("plans_with_guest_reboot_wait", 0),
                    ],
                ]
            )

        totals: list[list] = [
            ["Total Disk Size Migrated (GiB):", migration_info["total_disk_size_for_migration"]],
        ]
        if type_of_migration != "failed":
            totals.append(
                [
                    "Approximate plan size (GiB) completed in an hour:",
                    f"{migration_info['average_transfer_speed']:.1f}",
                ]
            )
            totals.append(["Hours migrations were running:", f"{migration_info['total_migration_hrs']:.2f}"])

        sections = [
            ("Overview", overview),
            ("Effective plan runtime", effective_runtime),
            ("Pipeline timing (plan)", pipeline_timing),
            ("Totals and throughput", totals),
        ]
        return _tabulate_sections(preamble, sections)

    def vm_migration_output(self: t.Self, vm_info: dict) -> str:
        """Generate output for VM-level migration summary.

        Args:
            vm_info (dict): Dictionary containing VM-level statistics.

        Returns:
            str: Formatted string for VM migration summary.
        """
        header = "MIGRATED VMS SUMMARY"
        sep = "=" * len(header)
        preamble = [[""], [header], [sep], [""]]

        overview = [["The number of migrated vms:", vm_info["total_vms"]]]

        effective_runtime = [
            ["Average runtime in minutes:", f'{vm_info["average_time_mins"]:.1f}'],
            ["Longest runtime in minutes:", f'{vm_info["max_minutes"]:.1f}'],
            ["Longest runtime VM:", vm_info["longest_running_vm_name"]],
            ["Longest VM GiB/hour over plan runtime:", f'{vm_info["longest_vm_transferspeed"]:.1f}'],
            ["Shortest runtime in minutes:", f'{vm_info["min_minutes"]:.1f}'],
            ["Shortest runtime VM:", vm_info["shortest_vm_name"]],
        ]
        if "longest_transfer_minutes" in vm_info:
            effective_runtime.append(["Longest VM disk-copy minutes:", f'{vm_info["longest_transfer_minutes"]:.1f}'])
        if "longest_transfer_gb_per_hour" in vm_info:
            effective_runtime.append(
                ["Longest VM GiB/hour over disk-copy time:", f'{vm_info["longest_transfer_gb_per_hour"]:.1f}']
            )

        disk_size = [
            ["Average disk size (GiB):", f'{vm_info["average_disk_size_GiB"]:.1f}'],
            ["Largest VM:", vm_info["largest_vm_name"]],
            ["Largest VM disk size (GiB):", f'{vm_info["largest_vm_disk_GiB"]:.1f}'],
            ["Smallest VM:", vm_info["smallest_vm_name"]],
            ["Smallest VM disk size (GiB):", f'{vm_info["smallest_vm_disk_GiB"]:.1f}'],
        ]

        pipeline_timing: list[list] = []
        if "average_transfer_minutes" in vm_info:
            pipeline_timing.append(["Average disk transfer minutes:", f'{vm_info["average_transfer_minutes"]:.1f}'])
        if "average_conversion_minutes" in vm_info:
            pipeline_timing.append(["Average disk conversion minutes:", f'{vm_info["average_conversion_minutes"]:.1f}'])
        if "longest_conversion_minutes" in vm_info:
            pipeline_timing.extend(
                [
                    ["Longest disk conversion minutes:", f'{vm_info["longest_conversion_minutes"]:.1f}'],
                    ["Longest conversion VM:", vm_info.get("longest_conversion_vm_name", "")],
                ]
            )
        if "average_guest_reboot_wait_minutes" in vm_info:
            pipeline_timing.extend(
                [
                    [
                        "Average guest reboot wait minutes (WaitForGuestReboots):",
                        f'{vm_info["average_guest_reboot_wait_minutes"]:.1f}',
                    ],
                    ["Longest guest reboot wait minutes:", f'{vm_info["longest_guest_reboot_wait_minutes"]:.1f}'],
                    ["Longest guest reboot wait VM:", vm_info.get("longest_guest_reboot_vm_name", "")],
                    ["VMs with guest reboot wait data:", vm_info.get("vms_with_guest_reboot_wait", 0)],
                ]
            )

        totals: list[list] = [
            ["Approximate plan size (GiB) completed in an hour:", f'{vm_info["aggregate_speed_GiB_per_hr"]:.1f}'],
            ["Total Disk Size Migrated (GiB):", f'{vm_info["total_disk_size_gb"]:.1f}'],
            ["Hours migrations were running:", f'{vm_info["total_migration_hours"]:.2f}'],
        ]
        if "transfer_gb_per_hour" in vm_info:
            totals.append(
                ["All VMs GiB/hour over disk-copy time (summed):", f'{vm_info["transfer_gb_per_hour"]:.1f}']
            )

        sections = [
            ("Overview", overview),
            ("Effective VM runtime", effective_runtime),
            ("Disk size", disk_size),
            ("Pipeline timing (VM)", pipeline_timing),
            ("Totals and throughput", totals),
        ]
        return _tabulate_sections(preamble, sections)

    def vms_by_date_output(self: t.Self, vms_by_date: dict) -> str:
        """Format successful VM names grouped by UTC completion date.

        Args:
            vms_by_date: Mapping of date -> sorted unique VM names.

        Returns:
            str: Report section with date headings and indented names.
        """
        header = "VMS BY COMPLETION DATE"
        sep = "=" * len(header)
        lines = ["", header, sep, ""]
        if not vms_by_date:
            lines.append("No VMs with a completion date.")
            return "\n".join(lines) + "\n"
        for day, names in vms_by_date.items():
            lines.append(day.isoformat())
            for name in names:
                lines.append(f"  {name}")
        return "\n".join(lines) + "\n"

    def operating_system_report(self: t.Self, all_vms: dict) -> str:
        rows = []
        os_header = "OS REPORT"
        sep = "=" * len(os_header)
        rows.append([""])
        rows.append([os_header])
        rows.append([sep])
        rows.append([""])
        for os in sorted(all_vms.keys(), key=str.lower):
            header = f"Report for {os}:"
            sep = "-" * len(header)
            total_disk_size = 0
            for vm in all_vms[os]:
                total_disk_size += vm["disk_size"] / 1024
            rows.append([header])
            rows.append([sep])
            rows.append(["Number of VMs: ", f"{len(all_vms[os])}"])
            rows.append(["Total Disk Size (GiB):", f"{total_disk_size}"])
            rows.append([])

        return tabulate(rows, tablefmt="plain")

    def generate_concurrency_report(self: t.Self, concurrency_data: dict) -> str:
        """Generate a textual report of VM concurrency."""
        rows = []
        header = "CONCURRENCY REPORT"
        sep = "=" * len(header)

        rows.append([""])
        rows.append([header])
        rows.append([sep])
        rows.append([""])

        if not concurrency_data:
            rows.append(["No concurrency data available."])
            return tabulate(rows, tablefmt="plain")

        rows.append(["Peak concurrent VMs:", concurrency_data.get("max_concurrent_total", 0)])
        rows.append(["Peak time:", concurrency_data.get("peak_time", "Unknown")])
        rows.append(
            [
                "Average concurrent VMs:",
                concurrency_data.get("overall_average_concurrent_vms", 0),
            ]
        )

        rows.append([""])
        rows.append([""])
        max_concur_header = "Maximum concurrent VMs by OS type:"
        sep = "-" * len(max_concur_header)
        rows.append([max_concur_header])
        rows.append([sep])
        for os_type, count in sorted(concurrency_data.get("max_concurrent", {}).items()):
            rows.append([f" {os_type}:", count])

        if concurrency_data.get("significant_drops"):
            rows.append([""])
            rows.append(["Significant drops in concurrency:"])
            for i, drop in enumerate(concurrency_data["significant_drops"], 1):
                rows.append([f" Drop {i}:"])
                rows.append(["   Time:", drop["time"]])
                rows.append([f"   From {drop['from']} to {drop['to']} VMs"])
                rows.append(["   Minutes after peak:", f"{drop['duration_mins']:.1f}"])

        if concurrency_data.get("hourly_concurrent_vms"):
            rows.append([""])
            rows.append([""])
            plan_number = 1
            for plan in concurrency_data["hourly_concurrent_vms"]:
                hourly_header = f"Hourly concurrent VMs for Migration Window {plan_number}:"
                sep = "-" * len(hourly_header)
                rows.append([hourly_header])
                rows.append([sep])
                for data in plan:
                    hour_str = data["hour"].strftime("%Y-%m-%d %H:%M")
                    rows.append([f" {hour_str}:", f"{data['vms']} VMs"])
                plan_number += 1
                rows.append([""])
                rows.append([""])
        return tabulate(rows, tablefmt="plain")
