# vms-by-date

## Purpose

Optional completion-date listing. Dates use the VM record `end_time` after the completion window.

## Requirements

### Requirement: flag off

`--vms-by-date` off SHALL omit the section.

#### Scenario: default

- GIVEN `--vms-by-date` is off
- WHEN the text report is written
- THEN the completion-date section is omitted

### Requirement: grouping

`group_successful_vms_by_completion_date` SHALL group successful VM names by the UTC calendar date of `end_time`. Names SHALL be unique and sorted. Dates SHALL be sorted ascending. Failed VMs SHALL be excluded.

#### Scenario: two dates

- GIVEN two successful VMs complete on different UTC dates and one VM failed
- WHEN the groups are built
- THEN names under each date are unique and sorted
- THEN dates are sorted ascending
- THEN the failed VM is excluded
