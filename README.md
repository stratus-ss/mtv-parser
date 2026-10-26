# AI Usage Disclaimer

Previous to Sept 2026, this project was maintained and written by the author. Post Sept 2026, some AI assistance is being utilized to generate tests, do code reviews and documentation updates. The author constrains AI based on complexity, code quality, and other software engineering practices (context7 and so on). This project has a strict, no-vibe coding policy. Tools may be used but the human is responsible for commits and functionality of the code submitted.

# VM Migration Analyzer

> [!WARNING]
> All of the metrics herein are constrained by what the MTV tool collects. That means things such as Windows reboot times are NOT included, as the Migration plans do not track this data!

**VM Migration Analyzer** is a Python toolkit designed to process, analyze, and visualize virtual machine (VM) migration data. It parses OpenShift's [MTV](https://docs.redhat.com/en/documentation/migration_toolkit_for_virtualization/2.8) migration plans YAML files, calculates effective migration times, analyzes concurrent migrations, and produces text reports (and an optional Gantt PNG). This tool is particularly useful for migration teams who need to understand migration performance metrics and optimize future migration waves.

## Features

- **YAML Migration Plan Processing:** Parses VM migration plans to extract critical timing and resource information
- **Smart Migration Time Analysis:** Detects significant drops in precopy duration to accurately calculate effective migration times
- **Comprehensive Reporting:** Generates detailed reports on successful and failed migrations, OS distribution, and performance metrics
- **Concurrency Analysis:** Tracks and analyzes concurrent migrations to identify peaks, patterns, and resource utilization
- **Visualization:** Optional Gantt chart PNG (`--gantt`) of migration timelines and overlapping migrations
- **Performance Metrics:** Calculates key indicators like transfer speeds, average durations, and resource efficiency
- **VMs by completion date:** Optional `--vms-by-date` listing of successful VM names grouped by UTC date
- **Date filtering:** Optional UTC `YYYY-MM-DD` window flags (`--since` / `--until` for reports and chart; `--gantt-since` / `--gantt-until` for chart-only overrides)

## Installation

VM Migration Analyzer can be installed directly from GitHub using pip, or executed from a cloned repository.

### Container

> [!NOTE]
> Charts are written as PNG files (the process uses matplotlib's non-interactive `Agg` backend). Mount a volume onto `/mtv-parser/charts` if you pass `--gantt`, or the image stays inside the container. The default container command does **not** generate a chart; add `--gantt` to the command if you want one.

#### Understanding Podman Volume Mounts

Podman volume mounts allow you to share files and directories between your local machine and the container. This is essential for:
- **Input Files:** Getting your migration YAML files into the container
- **Output Files:** Retrieving generated charts and reports from the container

**Volume Mount Syntax:** `-v local_path:container_path`
- `local_path`: File or directory on your computer
- `container_path`: Where it appears inside the container
- The container can read from and write to these mounted locations

#### Building

There is a `Containerfile` in this repository. The image build clones `https://github.com/rhtools/mtv-parser` and checks out the `dev` branch; it does not copy your local working tree.

```
podman build . -t mtv-parser
```

#### Running with Single File

To analyze a single migration plan file, mount it over the fallback path. `plans/multiple` must be empty (or absent); otherwise the parser merges every YAML file in that directory instead.

```
# Mount your YAML file over the single-file fallback location
podman run -v ./my_migration_plan.yaml:/mtv-parser/plans/single/vm-plan-sample.yaml \
           -v /your/local/chart/dir:/mtv-parser/charts \
           mtv-parser --gantt
```

**Explanation:**
- `-v ./my_migration_plan.yaml:/mtv-parser/plans/single/vm-plan-sample.yaml`: This mounts your local YAML file over the fallback file the parser reads when `plans/multiple` has no YAML
- `-v /your/local/chart/dir:/mtv-parser/charts`: This mounts a local directory to receive generated charts and any output files

#### Running with Multiple Files

To analyze multiple migration plan files:

```
# Mount your directory containing multiple YAML files
podman run -v /path/to/your/yaml/files:/mtv-parser/plans/multiple \
           -v /your/local/chart/dir:/mtv-parser/charts \
           mtv-parser --gantt
```

**Explanation:**
- `-v /path/to/your/yaml/files:/mtv-parser/plans/multiple`: This mounts your local directory containing multiple YAML files to the container's multiple files directory
- All `.yaml` and `.yml` files in your local directory will be processed together
- The analyzer automatically detects multiple files and merges them for comprehensive analysis

#### Using the Prebuilt Container

You can pull from the pre-built container from Quay. There are both `ubi9-stable` and `ubi9-dev` tags. The `dev` is considered unstable.

**Single File Analysis:**
```
podman run -v ./my_migration_plan.yaml:/mtv-parser/plans/single/vm-plan-sample.yaml \
           -v /your/local/chart/dir:/mtv-parser/charts \
           quay.io/sovens/rhtools/mtv-parser:ubi9-stable --gantt
```

**Multiple File Analysis:**
```
podman run -v /path/to/your/yaml/files:/mtv-parser/plans/multiple \
           -v /your/local/chart/dir:/mtv-parser/charts \
           quay.io/sovens/rhtools/mtv-parser:ubi9-stable --gantt
```
#### Volume Mount Troubleshooting

**Common Issues:**
- **File not found:** Ensure your local file path is correct and the file exists
- **Permission denied:** Make sure Podman has permission to read your files
- **Empty output:** Check that your output directory exists and is writable

**Verifying Mounts:**
You can verify your files are mounted correctly by running:
```
podman run -v ./my_file.yaml:/mtv-parser/plans/single/vm-plan-sample.yaml \
           mtv-parser ls -la /mtv-parser/plans/single/
```

### Using pip

```bash
pip install git+https://github.com/rhtools/mtv-parser.git
```

### From GitHub repository

```bash
git clone https://github.com/rhtools/mtv-parser.git
cd mtv-parser
pip install -r requirements.txt
```

Requires **Python 3.11 or newer**. There is no console-script entry point; after install or clone, run `python mtv_parser/mtv_plan_parser.py` from the repository root (that path is what makes the module imports resolve).

The `plans/` directory is gitignored and is not present after a clone. Create it and add YAML as described in [Usage](#usage) before running the parser.

## Required Dependencies

See `requirements.txt`. The analysis path uses:

- PyYAML: For parsing YAML migration plan files
- matplotlib: For generating Gantt chart PNGs (non-interactive `Agg` backend)
- tabulate: For formatting CLI output tables

## Input File Format

The analyzer accepts either a Plan **list** (`items:` as from `oc get plan -A -o yaml`) or a single object with `kind: Plan`. It expects VM migration plan data with the following structure:

- Migration metadata and specifications
- VM details including operating system information
- Migration status with timestamps
- Pipeline phases including disk transfer data
- Warm migration details with precopy information

Example structure (simplified):

```yaml
items:
  - metadata:
      name: migration-plan-1
    spec:
      vms:
        - name: vm1
    status:
      migration:
        started: "2023-04-01T10:00:00"
        completed: "2023-04-01T11:30:00"
        vms:
          - name: vm1
            operatingSystem: "Windows"
            pipeline:
              - name: "DiskTransfer"
                started: "2023-04-01T10:00:00"
                completed: "2023-04-01T10:45:00"
                progress:
                  total: 102400
            warm:
              precopies:
                - start: "2023-04-01T10:00:00"
                  end: "2023-04-01T10:15:00"
            conditions:
              - type: "Succeeded"
```

In the simplest form this can be obtained by running the following on an OpenShift Cluster
```
oc get plan -A -o yaml > migration_plan.yaml
```

## Usage

From the repository root:

```
python mtv_parser/mtv_plan_parser.py
```

That command always uses the same file-discovery order. It does **not** mean "analyze the single sample file."

1. If `plans/multiple/` exists and contains **two or more** `.yaml` / `.yml` files, those files are merged and analyzed together.
2. If `plans/multiple/` contains **exactly one** YAML file, that file is analyzed.
3. If `plans/multiple/` is missing or contains no YAML files, the parser falls back to `plans/single/vm-plan-sample.yaml`.

`plans/` is gitignored (it may contain real customer data). Create the directories you need and place YAML there, or edit the paths in `mtv_plan_parser.py`.

### Optional Gantt chart

Text reports run by default. To also write a Gantt chart PNG:

```
python mtv_parser/mtv_plan_parser.py --gantt
```

Optional output path (default `charts/migration_gantt_chart.png`):

```
python mtv_parser/mtv_plan_parser.py --gantt --gantt-output charts/my_wave.png
```

### Optional VMs-by-date report

To print successful VM names grouped by UTC completion date:

```
python mtv_parser/mtv_plan_parser.py --vms-by-date
```

Flags can be combined (`--gantt --vms-by-date`).

### Optional date filtering

All date flags use UTC calendar dates in `YYYY-MM-DD` form.

**Report window (`--since`, `--until`)**

Text reports, concurrency, the OS breakdown, optional `--vms-by-date`, and the Gantt chart keep a plan when `status.migration.completed` is inside the window, and keep a VM when that VM's `completed` is inside the window. `--since` is 00:00:00 UTC on that date. `--until` is 23:59:59.999999 UTC on that date. Either flag works alone. A VM that started before `--since` and completed inside the window stays in, on its real start and real end.

When `--until` is set, the report lists VMs that started inside the window and were still going after the end of that day. That list appears only for `--until`, and those disks stay outside the totals.

Example (reports):

```
python mtv_parser/mtv_plan_parser.py --since 2025-03-21
python mtv_parser/mtv_plan_parser.py --since 2025-03-21 --until 2025-03-25
```

**Chart window (`--gantt-since`, `--gantt-until`, plus `--gantt`)**

Chart bounds are resolved by `chart_cutoff`: `--gantt-since` / `--gantt-until` override `--since` / `--until` for the PNG only. If you set only a chart start (for example `--gantt-since` without any until), inherited report `--until` is used when present.

The Gantt VM list is filtered when either chart bound is set, using the same completion rule. When both chart bounds are absent, the chart uses the VM set already produced for reports.

Examples:

```
python mtv_parser/mtv_plan_parser.py --gantt --gantt-since 2025-03-21 --until 2025-03-25
python mtv_parser/mtv_plan_parser.py --gantt --since 2025-03-21 --until 2025-03-25
```

### Single File Analysis

To analyze one file, make sure `plans/multiple/` is empty or does not exist, then put your YAML at:

```
plans/single/vm-plan-sample.yaml
```

Alternatively, put **exactly one** YAML file in `plans/multiple/`.

If `plans/multiple/` already has more than one YAML file, the parser will merge those files and ignore `plans/single/`.

### Multiple File Analysis

Place two or more `.yaml` / `.yml` files in `plans/multiple/`. They are merged into one dataset before analysis, which is useful across migration waves or batches.

**Benefits of Multiple File Processing:**
- **Comprehensive Reporting:** Get overall statistics across all migration waves
- **Accurate Concurrency Analysis:** See true concurrent migration patterns across multiple plans
- **Resource Planning:** Better understand total migration capacity and timing
- **Historical Analysis:** Track migration performance across different time periods

> [!IMPORTANT]
> Plan input is selected by what is on disk under `plans/`, not by positional arguments. Optional flags: `--gantt` / `--gantt-output` (PNG chart), `--vms-by-date` (UTC completion dates), `--since` / `--until` (report window), `--gantt-since` / `--gantt-until` (chart-only window overrides). All date flags use `YYYY-MM-DD`.


## Module Structure

| Module | Description |
|--------|-------------|
| `mtv_plan_parser.py` | Main script that orchestrates the analysis process |
| `migration_information.py` | Core class `MigrationAnalyzer` for extracting and analyzing VM migration data |
| `vm_information.py` | Standalone helpers for effective migration time (also implemented on `MigrationAnalyzer`) |
| `clioutput.py` | Handles formatting and display of results to the command line |
| `since_filter.py` | Parses date CLI values; filters VM groups and plan rows; resolves chart vs report windows (`chart_cutoff`) |
| `visualization.py` | Writes Gantt chart PNGs of migration timelines |

## Key Methods of MigrationAnalyzer Class

### MigrationAnalyzer Class

**`calculate_effective_migration_time(vm, entry)`**
- Analyzes precopy phases to determine when migration effectively completed
- Detects significant drops in precopy duration to mark effective completion
- Falls back to regular migration times if no precopies are found

**`extract_vm_information(vm, effective_duration)`**
- Extracts essential VM data including OS, disk size, and transfer times
- Organizes information into a standardized dictionary structure
- Determines the VM's migration window based on the effective duration

**`analyze_concurrent_migrations(migration_plan_by_hour, max_concurrent_total, peak_time)`**
- Formats hourly concurrency windows (from `find_deployment_windows`) for reporting
- Uses the peak count and peak time already computed in `main()`
- Calculates hourly statistics and average concurrent VMs

**`get_migration_success_info(mtv_plan_data, all_vms)`**
- Processes migration data and extracts success/failure information
- Categorizes migrations into successful and failed lists
- Tracks migration windows for planning

**`prepare_migration_information(migrations, active_migration_hours=0)`**
- Calculates and organizes overall migration statistics
- Computes various statistics like average time, total VMs, disk size
- Identifies the longest migration plan and calculates cold/warm migration counts
- Prefers union-of-interval hours from plan records when computing aggregate GiB/hour

**`prepare_vm_inform(all_vms, concurrent_migration_hours=0)`**
- VM-level stats for successfully migrated VMs (longest/shortest, disk size, aggregate speed)

**`group_successful_vms_by_completion_date(all_vms)`**
- Groups unique successful VM names by UTC calendar completion date

**`sort_migration_events(all_vms)`**
- Processes migration events and sorts them chronologically
- Creates a sequence of start and end events for visualization

### MTV Plan Parser Module

**`main()`**
- Primary function that orchestrates the entire analysis workflow
- Initializes the MigrationAnalyzer class
- Processes YAML data and generates reports and visualizations

### CLI Output Module

The `CLIOutput` class provides methods for generating formatted reports:

- `migration_output()`: Generates reports on successful or failed migrations
- `vm_migration_output()`: VM-level summary (written when successful VM records exist)
- `operating_system_report()`: Creates breakdowns by operating system
- `generate_concurrency_report()`: Produces concurrency analysis reports
- `vms_by_date_output()`: Optional UTC-date grouping (`--vms-by-date`)

Reports use `tabulate` with titled sections (for example **Overview**, **Effective plan runtime**, **Pipeline timing**, **Totals and throughput**). Metrics inside each section are sorted alphabetically by label.

### Visualization Module

**`plot_gantt_chart(data, output_path="charts/migration_gantt_chart.png")`**
- Draws VM migrations as a Gantt chart (separate panels when waves are far apart)
- Times are normalized to UTC
- Writes a PNG and returns the path, or `None` if there is no timing data

## Example Output

The analyzer prints several reports in one run. If any plans failed, a **MIGRATION PLAN REPORT** for failed plans is printed first, then a successful-plan block (without repeating the main header). When there are successful VM records, a **MIGRATED VMS SUMMARY** follows, then **OS REPORT** and **CONCURRENCY REPORT**. With `--vms-by-date`, **VMS BY COMPLETION DATE** is appended. With `--gantt`, a line such as `Gantt chart saved to charts/migration_gantt_chart.png` is printed at the end.

Illustrative excerpt (values are fictional; section layout matches current output):

```
MIGRATION PLAN REPORT
=====================

Overview
--------
Number of Cold Migrated VMs:                     2
Number of Cold Migration Plans:                  1
Number of Warm Migrated VMs:                     17
Number of Warm Migration Plans:                  6
The number of successful migration plans:        7
The number of vms:                               19

Effective plan runtime
----------------------
Average disk size (GiB):                         701.6
Average runtime in minutes:                      275.3
Highest plan GiB/hour over plan runtime:         1.2
Longest runtime in minutes:                      430.3
Plan with longest runtime:                       105289-group-3
Shortest runtime in minutes:                     9.5
Total disk size in longest plan (GiB):           532.0

Pipeline timing (plan)
----------------------
Average disk transfer minutes per plan:          42.5
Average plan duration minutes (migration started to completed): 285.0

Totals and throughput
---------------------
Approximate plan size (GiB) completed in an hour: 152.9
Hours migrations were running:                   10.00
Total Disk Size Migrated (GiB):                  4911.0


MIGRATED VMS SUMMARY
====================

Overview
--------
The number of migrated vms:                      19

Effective VM runtime
--------------------
Average runtime in minutes:                      118.2
Longest runtime in minutes:                      430.3
Longest runtime VM:                              example-vm-long
Highest VM GiB/hour over plan runtime:           1.2
Shortest runtime in minutes:                     9.5
Shortest runtime VM:                             example-vm-short

Disk size
---------
Average disk size (GiB):                         258.5
Largest VM:                                      example-vm-large
Largest VM disk size (GiB):                      1024.0
Smallest VM:                                     example-vm-small
Smallest VM disk size (GiB):                     32.0

Totals and throughput
---------------------
Approximate plan size (GiB) completed in an hour: 152.9
Hours migrations were running:                   10.00
Total Disk Size Migrated (GiB):                  4911.0


OS REPORT
=========

Report for otherGuest64:
------------------------
Number of VMs:                                   16
Total Disk Size (GiB):                           3919.0

Report for windows2022srvNext_64Guest:
--------------------------------------
Number of VMs:                                   3
Total Disk Size (GiB):                           992.0


CONCURRENCY REPORT
==================

Peak concurrent VMs:                             16
Peak time:                                       2025-03-21 18:00:00+00:00
Average concurrent VMs:                          10

Maximum concurrent VMs by OS type:
----------------------------------
 windows2022srvNext_64Guest:                      3
 otherGuest64:                                    13

Hourly concurrent VMs for Migration Window 1:
---------------------------------------------
 2025-03-21 15:00:                               5 VMs
 2025-03-21 16:00:                               6 VMs
 2025-03-21 18:00:                               16 VMs
 2025-03-21 22:00:                               6 VMs
```

With `--vms-by-date`:

```
VMS BY COMPLETION DATE
======================

2025-03-21
  vm-alpha-01
  vm-beta-02
2025-03-22
  vm-gamma-03
```

### Gantt Chart Visualization

With `--gantt`, the tool writes a Gantt chart PNG of VM migrations over time (matplotlib `Agg` backend). Default path: `charts/migration_gantt_chart.png` (override with `--gantt-output`). The directory is created if needed. Limit which VMs are drawn with a **start and end** chart date (`--since` / `--until`, or chart-only `--gantt-since` / `--gantt-until`); see [Optional date filtering](#optional-date-filtering).

The chart helps identify migration overlaps, peak periods, and OS-specific timing. Generate it locally from your plan YAML; it is not checked into this repository.

The analyzer uses the following to determine the true effective migration time:

1. Analyzes all precopy phases for each VM
2. Identifies when precopy duration drops significantly (indicating data sync is nearly complete)
3. Calculates migration time from first precopy to the significant drop point
4. Falls back to total migration time if no significant drop is detected

The thought here is that while not 100% accurate due to the final copy of RAM to disk, there are many who start a migration plan then walk away and come back hours after the copies have completed. MTV's plan will officially be the entire time until the migration has been cut over. This is inaccurate and skews the metrics badly. By watching for a sharp drop off in precopy time we can "guess" at how long a cutover would have taken as if the cutover happened as soon as the VM had transferred all of the initial data.

"Plan runtime" is one migration's window (precopy drop for warm, started-to-completed for cold). "Approximate plan size (GiB) completed in an hour" is the disk finished during one hour when at least one plan was open. "Disk-copy time (summed)" uses only the `DiskTransfer` / `DiskTransferV2v` step and adds each VM's copy minutes. Disk-copy lines are omitted when `transfer_minutes` is absent. Plan YAML does not say whether the copy was network or storage copy offload.

### Concurrency Analysis

The tool provides insights into migration concurrency:

- Tracks which VMs are migrating at any given time
- Identifies peak concurrency periods
- Detects significant drops in concurrency
- Calculates hourly migration loads
- Breaks down concurrency by operating system

## File Processing Modes

The analyzer supports two distinct processing modes:

### Single File Mode
- Used when `plans/multiple/` is missing, empty, or contains exactly one YAML file
- Fallback file: `plans/single/vm-plan-sample.yaml`
- Suitable for analyzing an individual migration wave

### Multiple File Mode  
- Automatically activated when **two or more** YAML files are present in `plans/multiple/`
- Merges all migration data before analysis
- Provides comprehensive statistics across all files
- Maintains accurate concurrency analysis across multiple migration plans

**Data Merging Process:**
1. Scans `plans/multiple/` directory for `.yaml` and `.yml` files
2. Loads each file and extracts the `items` array
3. Combines all items into a single dataset
4. Processes the merged data using the same analysis logic
5. Generates reports that reflect the complete migration picture


## Contributing

Contributions to VM Migration Analyzer are welcome! The codebase is organized into modules with clear responsibilities:

- `migration_information.py`: Core MigrationAnalyzer class with analysis methods
- `mtv_plan_parser.py`: Main entry point and workflow orchestration
- `clioutput.py`: Output formatting and report generation
- `since_filter.py`: UTC date parsing, report/chart window helpers, and VM/plan filtering
- `visualization.py`: Data visualization with matplotlib
- `vm_information.py`: Effective-time helpers shared with analysis logic

To contribute:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-analysis`)
3. Commit your changes (`git commit -m 'Add new analysis capability'`)
4. Push to the branch (`git push origin feature/new-analysis`)
5. Open a Pull Request
