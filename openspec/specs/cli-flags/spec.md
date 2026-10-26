# cli-flags

## Purpose

Flags accepted by `parse_args` in `mtv_parser/mtv_plan_parser.py`.

## Requirements

### Requirement: date flags

The system SHALL accept `--since`, `--until`, `--gantt-since`, and `--gantt-until` as `YYYY-MM-DD`. A value that is not that form SHALL fail in argparse before plans load, with stderr containing `Invalid date format. Expected YYYY-MM-DD`.

#### Scenario: bad date

- GIVEN the operator passes `--since 2026-13-40`
- WHEN argparse parses the flags
- THEN the process exits non-zero before plans load
- THEN stderr contains `Invalid date format. Expected YYYY-MM-DD`

### Requirement: mode flags

`--gantt` and `--vms-by-date` SHALL default off. `--gantt-output` SHALL default to `charts/migration_gantt_chart.png`.

#### Scenario: defaults

- GIVEN the operator passes no mode flags
- WHEN `parse_args` returns
- THEN `--gantt` is off and `--vms-by-date` is off
- THEN `--gantt-output` is `charts/migration_gantt_chart.png`

### Requirement: plan path

The system SHALL load `./plans/multiple` when that directory has YAML files, else `./plans/single/vm-plan-sample.yaml`. There is no positional plan path.

#### Scenario: multiple directory

- GIVEN `./plans/multiple` contains one or more YAML files
- WHEN the CLI loads plans
- THEN those files are the plan set
- THEN no positional plan path is accepted
