# report-math

## Purpose

Summary figures after DR-1, DR-3, and DR-4.

## Requirements

### Requirement: plan runtime

Plan runtime SHALL be migration `completed` minus migration `started`, for cold and warm.

#### Scenario: warm plan

- GIVEN a warm plan whose migration runs 2026-10-15T19:49:10 to 2026-10-15T20:03:53
- WHEN the plan summary is built
- THEN the runtime is 883 seconds, including when precopy is longer

### Requirement: VM runtime

VM runtime SHALL be that VM's `completed` minus that VM's `started` when both are present, else the plan clock.

#### Scenario: own clock

- GIVEN a VM started 2026-10-03T03:32:58 and completed 2026-10-03T04:11:57
- WHEN the VM record is stored
- THEN the duration is 2339 seconds

### Requirement: phase minutes and display

DiskTransfer, ImageConversion, and WaitForGuestReboots minutes SHALL be exact seconds divided by 60. Display SHALL round with one decimal for minutes, GiB, and GiB/hour, and two decimals for hours.

#### Scenario: disk copy of 2601 seconds

- GIVEN a DiskTransfer of 2601 seconds
- WHEN the minutes are displayed
- THEN the printed value is `43.4`

### Requirement: averages

An average SHALL be the arithmetic mean. Guest-reboot means SHALL include only rows that have that phase.

#### Scenario: reboot mean

- GIVEN some VMs have WaitForGuestReboots and some do not
- WHEN the guest-reboot mean is computed
- THEN only the rows that have that phase are in the mean

### Requirement: hours and GiB/hour

Hours running SHALL be the union of the real intervals. GiB/hour SHALL be total GiB divided by those hours.

#### Scenario: overlap

- GIVEN two migrations overlap
- WHEN hours running are computed
- THEN the overlap is counted once

### Requirement: highest rate labels

The printed labels SHALL be `Highest plan GiB/hour over plan runtime:`, `Highest VM GiB/hour over plan runtime:`, and `Highest VM GiB/hour over disk-copy time:`. Each value SHALL be the maximum rate, not the rate of the longest row.

#### Scenario: faster shorter row

- GIVEN one long slow row and one shorter faster row
- WHEN the rate line is printed
- THEN the value is the faster row's rate
