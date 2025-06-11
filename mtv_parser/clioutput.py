import io
import sys
import typing as t
import weakref

from tabulate import tabulate


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

    def migration_output(self: t.Self, migration_info: dict, type_of_migration: str) -> str:
        report_header = "MIGRATION REPORT"
        sep = "=" * len(report_header)
        rows = []
        rows.append([""])
        rows.append([report_header])
        rows.append([sep])
        rows.append([""])

        header = f"The number of {type_of_migration} migration plans:"
        sep = "-" * len(header)

        rows.append([header, migration_info["number_of_migrations"]])
        rows.append([sep])

        rows.append(["The number of vms:", migration_info["total_number_of_vms"]])
        rows.append(["Number of Warm Migration Plans: ", migration_info["warm_migrations"]])
        rows.append(["Number of Cold Migration Plans: ", migration_info["cold_migrations"]])
        rows.append(["Number of Cold Migrated VMs: ", migration_info["cold_migrated_vms"]])
        rows.append(["Number of Warm Migrated VMs: ", migration_info["warm_migrated_vms"]])
        rows.append(["Plan with longest runtime: ", migration_info["longest_plan"]["name"]])
        rows.append(["Longest runtime in minutes: ", f"{migration_info['max_minutes']:.1f}"])
        rows.append(["Total disk size in longest plan (GB): ", migration_info["longest_disk_size_gb"]])
        rows.append(
            ["Transferred data per hour in longest plan (GB): ", f"{migration_info['longest_transfer_speed']:.1f}"]
        )
        rows.append(["Shortest runtime in minutes: ", f"{migration_info['min_minutes']:.1f}"])
        rows.append(["Average runtime in minutes: ", f"{migration_info['average_time']:.1f}"])
        rows.append(["Average disk size (GB): ", f"{migration_info['average_disk_size_gb']:.1f}"])
        rows.append(["Average transfer per hour (GB): ", f"{migration_info['average_transfer_speed']:.1f}"])
        rows.append(["Total Disk Size Migrated (GB): ", migration_info["total_disk_size_for_migration"]])
        rows.append(["Total Migration Hours (approx): ", migration_info["total_migration_hrs"]])

        return tabulate(rows, tablefmt="plain")

    def operating_system_report(self: t.Self, all_vms: dict) -> str:
        rows = []
        os_header = "OS REPORT"
        sep = "=" * len(os_header)
        rows.append([""])
        rows.append([os_header])
        rows.append([sep])
        rows.append([""])
        for os in all_vms.keys():
            header = f"Report for {os}:"
            sep = "-" * len(header)
            total_disk_size = 0
            for vm in all_vms[os]:
                total_disk_size += vm["disk_size"] / 1024
            rows.append([header])
            rows.append([sep])
            rows.append(["Number of VMs: ", f"{len(all_vms[os])}"])
            rows.append(["Total Disk Size (GB):", f"{total_disk_size}"])
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
