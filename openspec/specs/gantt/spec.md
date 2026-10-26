# gantt

## Purpose

Gantt chart behavior. Bars use the VM record clock. Membership uses the completion window in `openspec/specs/date-window/spec.md`.

## Requirements

### Requirement: flag off

`--gantt` off SHALL write no PNG.

#### Scenario: default

- GIVEN `--gantt` is off
- WHEN the CLI finishes
- THEN no PNG is written

### Requirement: output path

With `--gantt`, `plot_gantt_chart` SHALL write the `--gantt-output` path using the Agg backend.

#### Scenario: write

- GIVEN `--gantt` is on
- WHEN the chart is plotted
- THEN the PNG is the `--gantt-output` path
- THEN the backend is Agg

### Requirement: bar interval

Bar start SHALL be the VM record `start_time` and bar end SHALL be `end_time`. Bars SHALL NOT be clipped to the window.

#### Scenario: unclipped bar

- GIVEN a VM `start_time` is before the window and `end_time` is inside it
- WHEN the bar is drawn
- THEN the bar uses those two timestamps
- THEN the bar is not clipped to the window

### Requirement: chart cutoff precedence

`chart_cutoff` SHALL prefer `--gantt-since` over `--since` and `--gantt-until` over `--until`.

#### Scenario: chart flag wins

- GIVEN both `--since` and `--gantt-since` are set
- WHEN the chart cutoff is chosen
- THEN `--gantt-since` is the chart start

### Requirement: either chart bound

The chart VM list SHALL be filtered when either chart bound is set, using the completion rule in `openspec/specs/date-window/spec.md`.

#### Scenario: one bound

- GIVEN only `--gantt-since` is set
- WHEN the chart VM list is built
- THEN the list is filtered with the completion rule
