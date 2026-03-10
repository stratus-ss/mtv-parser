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

### Using Container (Recommended)

**Prebuilt container from Quay:**

```bash
# Analyze multiple migration plans
podman run -v /path/to/yaml/files:/mtv-parser/plans/multiple \
           -v ./output:/mtv-parser/charts \
           quay.io/sovens/rhtools/mtv-parser:ubi9-stable
```

Use `-v` to mount your YAML files and output directory. The container processes all `.yaml`/`.yml` files in the mounted directory.

**Build locally:**
```bash
podman build . -t mtv-parser
```

> [!NOTE]
> Charts export to the mounted volume - interactive display requires additional container configuration.

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
```

All `.yaml` and `.yml` files are processed and merged for cross-wave analysis. See `examples/` for sample files.

> [!IMPORTANT]
> CLI arguments not supported. Edit paths in `mtv_plan_parser.py` if needed.


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
4. **Gantt Chart** - Visual timeline saved as `migration_gantt_chart.png`

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
