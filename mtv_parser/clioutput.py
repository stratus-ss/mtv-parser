import io
import sys
import typing as t
import weakref

import pandas as pd
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

    def migration_output(self, migrations: list, type_of_migration: str) -> None:
        rows = []
        number_of_migrations = len(migrations)
        average_time = sum(item["total_duration_mins"] for item in migrations) / number_of_migrations
        total_number_of_vms = sum(item["vms"] for item in migrations)
        total_disk_size_for_migration = sum(item["total_disk_size"] for item in migrations) / 1024
        average_disk_size_gb =  total_disk_size_for_migration / number_of_migrations 
        average_transfer_speed = average_disk_size_gb / average_time
        # Find max duration and corresponding plan name
        max_minutes = max(item["total_duration_mins"] for item in migrations)
        longest_plan = next(item for item in migrations if item["total_duration_mins"] == max_minutes)
        longest_disk_size_gb = longest_plan["total_disk_size"] / 1024
        longest_transfer_speed =  longest_disk_size_gb/ max_minutes
        min_minutes = min(item["total_duration_mins"] for item in migrations)

        header = f"The number of {type_of_migration} migrations:"
        sep = "-" * len(header)
        rows.append([header, number_of_migrations])
        rows.append([sep])
        rows.append(["The number of vms:", total_number_of_vms])
        rows.append(["Plan with longest runtime: ", longest_plan["name"]])
        rows.append(["Longest runtime in minutes: ", f"{max_minutes:.1f}"])
        rows.append(["Total disk size in longest plan (GB): ", longest_disk_size_gb])
        rows.append(["Transferred data per hour in longest plan (GB): ", f"{longest_transfer_speed:.1f}"])
        rows.append(["Shortest runtime in minutes: ", f"{min_minutes:.1f}"])
        rows.append(["Average runtime in minutes: ", f"{average_time:.1f}"])
        rows.append(["Average disk size (GB): ", f"{average_disk_size_gb:.1f}"])
        rows.append(["Average transfer per hour (GB): ", f"{average_transfer_speed:.1f}"])
        rows.append(["Total Disk Size Migrated (GB): ", f"{total_disk_size_for_migration}"])

        return (tabulate(rows, tablefmt="plain"))

    def operating_system_report(self, all_vms: dict):
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
                total_disk_size += vm['disk_size'] / 1024
            rows.append([header])
            rows.append([sep])
            rows.append(["Number of VMs: ", f"{len(all_vms[os])}"])
            rows.append(["Total Disk Size (GB):", f"{total_disk_size}"])
            rows.append([])
            
        return(tabulate(rows, tablefmt="plain"))

    def generate_concurrency_report(self, concurrency_data):
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
        
        rows.append(["Peak concurrent VMs:", concurrency_data.get('max_concurrent_total', 0)])
        rows.append(["Peak time:", concurrency_data.get('peak_time', 'Unknown')])
        rows.append(["Average concurrent VMs:", concurrency_data.get('average_concurrent_vms', 0)])
        
        rows.append([""])
        rows.append(["Maximum concurrent VMs by OS type:"])
        for os_type, count in sorted(concurrency_data.get('max_concurrent', {}).items()):
            rows.append([f" {os_type}:", count])
        
        if concurrency_data.get('significant_drops'):
            rows.append([""])
            rows.append(["Significant drops in concurrency:"])
            for i, drop in enumerate(concurrency_data['significant_drops'], 1):
                rows.append([f" Drop {i}:"])
                rows.append([f"   Time:", drop['time']])
                rows.append([f"   From {drop['from']} to {drop['to']} VMs"])
                rows.append([f"   Minutes after peak:", f"{drop['duration_mins']:.1f}"])
        
        if concurrency_data.get('hourly_concurrent_vms'):
            rows.append([""])
            rows.append(["Hourly concurrent VMs:"])
            for data in concurrency_data['hourly_concurrent_vms']:
                hour_str = data['hour'].strftime('%Y-%m-%d %H:%M')
                rows.append([f" {hour_str}:", f"{data['vms']} VMs"])
        
        return tabulate(rows, tablefmt="plain")
