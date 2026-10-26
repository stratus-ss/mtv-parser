# os-detection

## Purpose

OS report membership. Name detection stays as the code works today.

## Requirements

### Requirement: name source

`load_vm_os_info` in `mtv_parser/vm_information.py` SHALL stay the OS-name source. This plan SHALL NOT change that function.

#### Scenario: unchanged function

- GIVEN a VM operating system field
- WHEN the OS name is resolved
- THEN `load_vm_os_info` is the source
- THEN this plan does not change that function

### Requirement: window membership

The OS report SHALL group the VMs that remain after the completion window. A VM removed by the window SHALL NOT appear in the OS report.

#### Scenario: removed VM

- GIVEN the completion window excludes a VM
- WHEN the OS report is built
- THEN that VM is not in the OS report
