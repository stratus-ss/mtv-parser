from mtv_parser.clioutput import CLIOutput


def _migration_info() -> dict:
    return {
        "number_of_migrations": 1,
        "total_number_of_vms": 1,
        "warm_migrations": 0,
        "cold_migrations": 1,
        "cold_migrated_vms": 1,
        "warm_migrated_vms": 0,
        "average_disk_size_gb": 1.0,
        "average_time": 10.0,
        "longest_transfer_speed": 2.0,
        "max_minutes": 10.0,
        "longest_plan": {"name": "plan-a"},
        "min_minutes": 10.0,
        "longest_disk_size_gb": 1.0,
        "total_disk_size_for_migration": 1.0,
        "average_transfer_speed": 1.0,
        "total_migration_hrs": 1.0,
    }


def _vm_info() -> dict:
    return {
        "total_vms": 1,
        "average_time_mins": 10.0,
        "max_minutes": 10.0,
        "longest_running_vm_name": "vm-a",
        "longest_vm_transferspeed": 2.0,
        "min_minutes": 10.0,
        "shortest_vm_name": "vm-a",
        "longest_transfer_minutes": 43.4,
        "longest_transfer_gb_per_hour": 3.0,
        "average_disk_size_GiB": 1.0,
        "largest_vm_name": "vm-a",
        "largest_vm_disk_GiB": 1.0,
        "smallest_vm_name": "vm-a",
        "smallest_vm_disk_GiB": 1.0,
        "aggregate_speed_GiB_per_hr": 1.0,
        "total_disk_size_gb": 1.0,
        "total_migration_hours": 1.0,
    }


def test_rate_labels_say_highest():
    output = CLIOutput()
    plan_text = output.migration_output(_migration_info(), "successful")
    vm_text = output.vm_migration_output(_vm_info())

    assert "Highest plan GiB/hour over plan runtime:" in plan_text
    assert "Highest VM GiB/hour over plan runtime:" in vm_text
    assert "Highest VM GiB/hour over disk-copy time:" in vm_text
    assert "Longest plan GiB/hour over plan runtime:" not in plan_text
    assert "Longest VM GiB/hour over plan runtime:" not in vm_text
    assert "Longest VM GiB/hour over disk-copy time:" not in vm_text
