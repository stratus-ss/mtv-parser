# date-window

## Purpose

Who is inside the report window after DR-2. This file states the corrected rule.

## Requirements

### Requirement: plan membership

A plan SHALL be kept when `end_time` (migration `completed`) is on or after `--since` midnight UTC and on or before `--until` at 23:59:59.999999 UTC. `--since` alone uses only the lower bound. `--until` alone uses only the upper bound. Both bounds absent SHALL leave the input list unchanged.

#### Scenario: both bounds

- GIVEN `--since` is 2026-10-01 and `--until` is 2026-10-10
- WHEN a plan's `end_time` is 2026-10-08 19:21:48 UTC
- THEN the plan is kept

#### Scenario: since only

- GIVEN `--since` is 2026-10-01 and `--until` is absent
- WHEN a plan's `end_time` is 2026-10-15 20:03:53 UTC
- THEN the plan is kept

#### Scenario: until only

- GIVEN `--since` is absent and `--until` is 2026-10-10
- WHEN a plan's `end_time` is 2026-10-15 20:03:53 UTC
- THEN the plan is excluded

#### Scenario: no bounds

- GIVEN both bounds are absent
- WHEN the filter runs
- THEN the input list is unchanged

### Requirement: VM membership

A VM SHALL be kept when its `end_time` (that VM's `completed`) meets the same bounds. A VM with no `end_time` SHALL be excluded. The function SHALL NOT raise.

#### Scenario: missing end

- GIVEN a VM record has no `end_time`
- WHEN the window check runs
- THEN the VM is excluded
- THEN the function does not raise

### Requirement: start before the window

A VM that started before `--since` and completed inside the window SHALL be kept.

#### Scenario: early start

- GIVEN `--since` is 2026-10-01
- WHEN a VM started on 2026-09-30 and its `end_time` is inside the window
- THEN the VM is kept

### Requirement: VMs continuing past until

When `--until` is set, the report SHALL list a VM whose start is inside the window and whose end is missing or later than the end of the `--until` day. The list SHALL be omitted when `--until` is absent or the list is empty. Disks on this list SHALL stay outside the totals.

#### Scenario: still going after until

- GIVEN `--since` is 2026-09-25 and `--until` is 2026-09-27
- WHEN a VM starts on 2026-09-26 and ends on 2026-09-28
- THEN the VM is listed
- THEN its disk is not added to a total

#### Scenario: finished inside

- GIVEN the same window
- WHEN a VM ends on 2026-09-26
- THEN the VM is not listed

#### Scenario: started before since

- GIVEN the same window
- WHEN a VM starts on 2026-09-20 and ends on 2026-09-28
- THEN the VM is not listed

#### Scenario: until absent

- GIVEN `--until` is absent
- THEN the list is omitted
