# MTV Parser

Analyzes OpenShift [MTV](https://docs.redhat.com/en/documentation/migration_toolkit_for_virtualization/2.8) migration plans and generates performance reports with visualizations.

> [!WARNING]
> Metrics are limited to what MTV collects. Windows reboot times and similar data not tracked by MTV are excluded.

## What It Does

- Parses migration plan YAML files and calculates effective migration times
- Analyzes concurrent migrations to find peak periods and patterns
- Generates reports on migration success/failure, OS distribution, and performance metrics
- Creates Gantt chart visualizations showing migration timelines
- Detects when warm migrations effectively complete by tracking precopy duration drops

## Quick Start

### Using Container

**Prebuilt container from Quay:**

### Container

> [!NOTE]
> Matplotlib cannot currently show you the chart interactively without appropriate configuration of your local container engine. You should mount a volume so that the image can be exported out of the container.

#### Understanding Podman Volume Mounts

Podman volume mounts allow you to share files and directories between your local machine and the container. This is essential for:
- **Input Files:** Getting your migration YAML files into the container
- **Output Files:** Retrieving generated charts and reports from the container

**Volume Mount Syntax:** `-v local_path:container_path`
- `local_path`: File or directory on your computer
- `container_path`: Where it appears inside the container
- The container can read from and write to these mounted locations

#### Building

There is a container file located in this repository. The build is small and has been tested with podman.

```
podman build . -t mtv-parser
```

#### Running with Single File

To analyze a single migration plan file:

```
# Mount your YAML file over the sample file location
podman run -v ./my_migration_plan.yaml:/mtv-parser/examples/vm-plans-sample2.yaml \
           -v /your/local/chart/dir:/mtv-parser/charts \
           mtv-parser
```

**Explanation:**
- `-v ./my_migration_plan.yaml:/mtv-parser/examples/vm-plans-sample2.yaml`: This mounts your local YAML file directly over the sample file inside the container, replacing it
- `-v /your/local/chart/dir:/mtv-parser/charts`: This mounts a local directory to receive the generated charts and any output files
- Add `-e GENERATE_GANTT=true` for Gantt chart generation (see Gantt Chart Options below)

#### Running with Multiple Files

To analyze multiple migration plan files:

```
# Mount your directory containing multiple YAML files
podman run -v /path/to/your/yaml/files:/mtv-parser/plans/multiple \
           -v /your/local/chart/dir:/mtv-parser/charts \
           mtv-parser
```

**Explanation:**
- `-v /path/to/your/yaml/files:/mtv-parser/plans/multiple`: This mounts your local directory containing multiple YAML files to the container's multiple files directory
- All `.yaml` and `.yml` files in your local directory will be processed together
- The analyzer automatically detects multiple files and merges them for comprehensive analysis
- Add `-e GENERATE_GANTT=true` for Gantt chart generation (see Gantt Chart Options below)

#### Using the Prebuilt Container

You can pull from the pre-built container from Quay. There are both `ubi9-stable` and `ubi9-dev` tags. The `dev` is considered unstable.

**Single File Analysis:**
```
podman run -v ./my_migration_plan.yaml:/mtv-parser/plans/multiple/migration_plan.yaml \
           -v /your/local/chart/dir:/mtv-parser/charts \
           quay.io/sovens/rhtools/mtv-parser:latest
```

**Multiple File Analysis:**
```
podman run -v /path/to/your/yaml/files:/mtv-parser/plans/multiple \
           -v /your/local/chart/dir:/mtv-parser/charts \
           quay.io/sovens/rhtools/mtv-parser:latest
```
#### Gantt Chart Options

Gantt chart generation is **optional** and can be enabled with the `GENERATE_GANTT` environment variable:

```bash
podman run -e GENERATE_GANTT=true \
           -v ./my_migration_plan.yaml:/mtv-parser/plans/multiple/migration_plan.yaml \
           -v /your/local/chart/dir:/mtv-parser/charts \
           mtv-parser
```

**What Gets Generated:**
- **Multi-window charts**: Separate PNG files per migration window (e.g., `migration_gantt_window_01.png`, `_02.png`, etc.)
- **Interactive chart**: Single HTML file with zoom/pan capabilities (`migration_gantt_interactive.html`)

**Why Optional:**
- Large datasets (100+ VMs) can generate many window charts
- Adds processing time and storage requirements
- Not needed for basic analysis reports

> [!NOTE]
> Charts export to the mounted volume - interactive display requires additional container configuration.

#### Volume Mount Troubleshooting

**Common Issues:**
- **File not found:** Ensure your local file path is correct and the file exists
- **Permission denied:** Make sure Podman has permission to read your files
- **Empty output:** Check that your output directory exists and is writable

**Verifying Mounts:**
```bash
podman run -v ./my_file.yaml:/mtv-parser/plans/single/vm-plans-sample2.yaml \
           mtv-parser ls -la /mtv-parser/plans/single/
```

### Using Python Directly

**Install from GitHub:**
```bash
pip install git+https://github.com/rhtools/mtv-parser.git
```

**Clone and run:**
```bash
git clone https://github.com/rhtools/mtv-parser.git
cd mtv-parser
pip install -r requirements.txt
python mtv_parser/mtv_plan_parser.py
```

Place your YAML files in `plans/multiple/` directory before running.

## Usage

**1. Get your migration data:**
```bash
oc get plan -A -o yaml > migration_plan.yaml
```

**2. Place YAML files in `plans/multiple/` directory**

**3. Run the analyzer:**
```bash
python mtv_parser/mtv_plan_parser.py

# With Gantt charts (optional)
python mtv_parser/mtv_plan_parser.py --generate-gantt
# or
GENERATE_GANTT=true python mtv_parser/mtv_plan_parser.py
```

All `.yaml` and `.yml` files are processed and merged for cross-wave analysis. See `examples/` for sample files.


## How It Works

**Effective Migration Time Calculation:**
For warm migrations, the tool analyzes precopy phases and detects when duration drops significantly (50%+), indicating data sync completion. This provides more accurate timing than waiting for manual cutover, which may happen hours after actual data transfer completes.

**Concurrency Analysis:**
Tracks active migrations hour-by-hour to identify peak concurrent periods, resource utilization patterns, and optimal migration windows for planning.

## Output

The tool generates:

1. **Migration Report** - Success/failure rates, warm vs cold migrations, timing statistics, transfer speeds
2. **OS Report** - VM and disk size breakdown by operating system
3. **Concurrency Report** - Peak concurrent VMs, hourly migration load, optimal migration windows
4. **Gantt Charts** *(optional)* - Visual timelines when enabled with `GENERATE_GANTT=true`:
   - Multiple PNG charts per migration window for readability
   - Single interactive HTML chart with zoom/pan capabilities

![Example Gantt Chart](examples/migration_gantt_chart.png)


## Project Structure

```
mtv_parser/
├── mtv_plan_parser.py       # Main entry point
├── migration_information.py # Core analysis logic
├── clioutput.py             # Report formatting
├── visualization.py         # Gantt chart generation
└── vm_os_lookup.py          # OS detection from VM YAML
```

## Contributing

Standard fork-and-PR workflow. See module structure above for code organization.
