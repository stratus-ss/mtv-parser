import pytest
import datetime
from datetime import timedelta
from collections import defaultdict
import math

# Update import to use the MigrationAnalyzer class
from mtv_parser.migration_information import MigrationAnalyzer

@pytest.fixture
def migration_analyzer():
    return MigrationAnalyzer()

# Tests for calculate_effective_migration_time
@pytest.mark.parametrize(
    "test_id, vm, entry, expected_time",
    [
        (
            "single_precopy",
            {
                "warm": {
                    "precopies": [
                        {"start": "2024-07-24T10:00:00", "end": "2024-07-24T11:00:00"}
                    ]
                },
                "migration_type": "warm"
            },
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T09:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                }
            },
            60.0,
        ),
        (
            "multiple_precopies_drop",
            {
                "warm": {
                    "precopies": [
                        {"start": "2024-07-24T10:00:00", "end": "2024-07-24T11:00:00"},
                        {"start": "2024-07-24T11:00:00", "end": "2024-07-24T11:30:00"},
                    ]
                },
                "migration_type": "warm"
            },
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T09:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                }
            },
            90.0,
        ),
        (
            "multiple_precopies_no_drop",
            {
                "warm": {
                    "precopies": [
                        {"start": "2024-07-24T10:00:00", "end": "2024-07-24T10:45:00"},
                        {"start": "2024-07-24T10:45:00", "end": "2024-07-24T11:30:00"},
                    ]
                },
                "migration_type": "warm"
            },
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T09:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                }
            },
            90.0,
        ),
        (
            "edge_no_precopies",
            {},
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T10:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                }
            },
            120.0,
        ),
        (
            "edge_empty_precopies",
            {"warm": {"precopies": []}, "migration_type": "warm"},
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T10:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                }
            },
            120.0,
        ),
        (
            "edge_missing_time",
            {"warm": {"precopies": [{"start": "2024-07-24T10:00:00"}]}, "migration_type": "warm"},
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T10:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                }
            },
            120.0,
        ),
    ],
)
def test_calculate_effective_migration_time(migration_analyzer, test_id, vm, entry, expected_time):
    actual_time = migration_analyzer.calculate_effective_migration_time(vm, entry)
    assert actual_time == expected_time

# Tests for add_migration_attribute
@pytest.mark.parametrize(
    "test_id, vm, expected_result",
    [
        (
            "warm_migration",
            {"warm": True},
            {"warm": True, "migration_type": "warm"},
        ),
        (
            "cold_migration",
            {"warm": False},
            {"warm": False, "migration_type": "cold"},
        ),
        (
            "no_warm_attribute",
            {},
            {"migration_type": "cold"},
        ),
    ],
)
def test_add_migration_attribute(migration_analyzer, test_id, vm, expected_result):
    actual_result = migration_analyzer.add_migration_attribute(vm)
    assert actual_result == expected_result

# Tests for add_to_dict
@pytest.mark.parametrize(
    "test_id, vm_information, dict_to_update, effective_duration, expected_result",
    [
        (
            "valid_data",
            {
                "linux": {
                    "name": "test_vm",
                    "disk_size": 1024,
                    "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                }
            },
            defaultdict(list),
            60.0,
            defaultdict(list, {
                "linux": [{
                    "name": "test_vm",
                    "disk_size": 1024,
                    "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                    "end_time": datetime.datetime(2024, 7, 25, 11, 0, 0),
                    "duration": 60.0,
                    "succeeded": True,
                }]
            }),
        ),
    ],
)
def test_add_to_dict(migration_analyzer, test_id, vm_information, dict_to_update, effective_duration, expected_result):
    actual_result = migration_analyzer.add_to_dict(vm_information, dict_to_update, effective_duration)
    assert actual_result == expected_result

# Tests for get_avg_concurrent_count
@pytest.mark.parametrize(
    "test_id, hourly_counts, expected_result",
    [
        (
            "equal_counts",
            {
                datetime.datetime(2024, 7, 30, 10, 0, 0): 5,
                datetime.datetime(2024, 7, 30, 11, 0, 0): 5,
            },
            5,
        ),
        (
            "varying_counts",
            {
                datetime.datetime(2024, 7, 30, 10, 0, 0): 5,
                datetime.datetime(2024, 7, 30, 11, 0, 0): 3,
            },
            4,
        ),
        (
            "zero_counts",
            {
                datetime.datetime(2024, 7, 30, 10, 0, 0): 0,
                datetime.datetime(2024, 7, 30, 11, 0, 0): 0,
            },
            0,
        ),
    ],
)
def test_get_avg_concurrent_count(migration_analyzer, test_id, hourly_counts, expected_result):
    actual_result = migration_analyzer.get_avg_concurrent_count(hourly_counts)
    assert actual_result == expected_result

# Tests for extract_vm_information
@pytest.mark.parametrize(
    "test_id, vm, effective_duration, expected_information",
    [
        (
            "disktransfer_present",
            {
                "pipeline": [
                    {
                        "name": "DiskTransfer",
                        "started": "2024-07-25T10:00:00",
                        "completed": "2024-07-25T11:00:00",
                        "progress": {"total": 1024},
                        "phase": "Completed"
                    }
                ],
                "operatingSystem": "linux",
                "name": "test_vm",
                "migration_type": "cold",
                "conditions": []
            },
            60.0,
            {
                "linux": {
                    "name": "test_vm",
                    "disk_size": 1024,
                    "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                    "duration": 60.0,
                    "migration_type": "cold",
                    "migration_window": [datetime.datetime(2024, 7, 25, 10, 0, 0), datetime.datetime(2024, 7, 25, 11, 0, 0)]
                }
            },
        ),
    ],
)
def test_extract_vm_information(migration_analyzer, test_id, vm, effective_duration, expected_information):
    actual_information = migration_analyzer.extract_vm_information(vm, effective_duration)
    assert actual_information == expected_information

# Tests for find_deployment_windows
@pytest.mark.parametrize(
    "test_id, data, threshold_hours, expected_windows",
    [
        (
            "single_window",
            {
                datetime.datetime(2024, 7, 28, 10, 0, 0): 5,
                datetime.datetime(2024, 7, 28, 11, 0, 0): 3,
                datetime.datetime(2024, 7, 28, 12, 0, 0): 0,
                datetime.datetime(2024, 7, 28, 13, 0, 0): 0,
                datetime.datetime(2024, 7, 28, 14, 0, 0): 0,
                datetime.datetime(2024, 7, 28, 15, 0, 0): 4,
            },
            3,
            [
                {
                    datetime.datetime(2024, 7, 28, 10, 0, 0): 5,
                    datetime.datetime(2024, 7, 28, 11, 0, 0): 3,
                },
                {
                    datetime.datetime(2024, 7, 28, 15, 0, 0): 4,
                }
            ],
        ),
        (
            "empty_data",
            {},
            28,
            [],
        ),
        (
            "no_windows",
            {
                datetime.datetime(2024, 7, 28, 10, 0, 0): 0,
                datetime.datetime(2024, 7, 28, 11, 0, 0): 0,
            },
            1,
            [],
        ),
    ],
)
def test_find_deployment_windows(migration_analyzer, test_id, data, threshold_hours, expected_windows):
    actual_windows = migration_analyzer.find_deployment_windows(data, threshold_hours)
    assert actual_windows == expected_windows

# Tests for sort_migration_events
@pytest.mark.parametrize(
    "test_id, all_vms, expected_events",
    [
        (
            "start_end",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "start_time": datetime.datetime(2024, 7, 26, 10, 0, 0),
                        "duration": 60.0,
                    }
                ]
            },
            [
                {
                    "time": datetime.datetime(2024, 7, 26, 10, 0, 0),
                    "type": "start",
                    "os": "linux",
                    "name": "vm1",
                    "duration": 60.0,
                    "event_end": datetime.datetime(2024, 7, 26, 11, 0, 0)
                },
                {
                    "time": datetime.datetime(2024, 7, 26, 11, 0, 0),
                    "type": "end",
                    "os": "linux",
                    "name": "vm1",
                    "duration": 60.0,
                },
            ],
        ),
        (
            "edge_no_start",
            {"linux": [{"name": "vm1", "duration": 60.0}]},
            []
        ),
        (
            "edge_no_duration",
            {"linux": [{"name": "vm1", "start_time": datetime.datetime(2024, 7, 26, 10, 0, 0)}]},
            [],
        ),
        (
            "edge_empty_all_vms",
            {},
            []
        ),
    ],
)
def test_sort_migration_events(migration_analyzer, test_id, all_vms, expected_events):
    actual_events = migration_analyzer.sort_migration_events(all_vms)
    assert actual_events == expected_events

# Tests for get_migration_time_range
@pytest.mark.parametrize(
    "test_id, start_time, duration, expected_result",
    [
        (
            "multi_hour_duration",
            datetime.datetime(2024, 7, 31, 10, 30, 0),
            90.0,
            [
                datetime.datetime(2024, 7, 31, 10, 0, 0),
                datetime.datetime(2024, 7, 31, 11, 0, 0),
                datetime.datetime(2024, 7, 31, 12, 0, 0),
            ],
        ),
        (
            "single_hour_duration",
            datetime.datetime(2024, 7, 31, 10, 30, 0),
            25.0,
            [
                datetime.datetime(2024, 7, 31, 10, 0, 0),
            ],
        ),
        (
            "zero_duration",
            datetime.datetime(2024, 7, 31, 10, 30, 0),
            0.0,
            [
                datetime.datetime(2024, 7, 31, 10, 0, 0),
            ],
        ),
    ],
)
def test_get_migration_time_range(migration_analyzer, test_id, start_time, duration, expected_result):
    actual_result = migration_analyzer.get_migration_time_range(start_time, duration)
    assert actual_result == expected_result

# Tests for analyze_concurrent_migrations
@pytest.mark.parametrize(
    "test_id, migration_plan_by_hour, max_concurrent_total, peak_time, expected_result",
    [
        (
            "single_plan",
            [
                {
                    datetime.datetime(2024, 7, 29, 10, 0, 0): 5,
                    datetime.datetime(2024, 7, 29, 11, 0, 0): 3,
                }
            ],
            5,
            datetime.datetime(2024, 7, 29, 10, 0, 0),
            {
                "max_concurrent_total": 5,
                "peak_time": datetime.datetime(2024, 7, 29, 10, 0, 0),
                "average_concurrent_vms": [[4]],
                "overall_average_concurrent_vms": 4,
                "hourly_concurrent_vms": [
                    [
                        {"hour": datetime.datetime(2024, 7, 29, 10, 0, 0), "vms": 5},
                        {"hour": datetime.datetime(2024, 7, 29, 11, 0, 0), "vms": 3},
                    ]
                ],
            },
        ),
    ],
)
def test_analyze_concurrent_migrations(migration_analyzer, test_id, migration_plan_by_hour, max_concurrent_total, peak_time, expected_result):
    actual_result = migration_analyzer.analyze_concurrent_migrations(migration_plan_by_hour, max_concurrent_total, peak_time)
    assert actual_result == expected_result

# Tests for prepare_migration_information
@pytest.mark.parametrize(
    "test_id, migrations, active_migration_hours, expected_result",
    [
        (
            "mixed_migrations",
            [
                {
                    "name": "plan1",
                    "total_duration_mins": 60.0,
                    "vms": 2,
                    "vms_failed": "False",
                    "total_disk_size": 2048,
                    "duration": 60.0,
                    "start_time": datetime.datetime(2024, 8, 1, 10, 0, 0),
                    "migration_type": "warm",
                    "vm_names": ["vm1", "vm2"],
                    "migration_window": [datetime.datetime(2024, 8, 1, 10, 0, 0), datetime.datetime(2024, 8, 1, 11, 0, 0)],
                },
                {
                    "name": "migration2",
                    "total_duration_mins": 30.0,
                    "vms": 1,
                    "vms_failed": "False",
                    "total_disk_size": 1024,
                    "duration": 30.0,
                    "start_time": datetime.datetime(2024, 8, 1, 12, 0, 0),
                    "migration_type": "cold",
                    "vm_names": ["vm3"],
                    "migration_window": [datetime.datetime(2024, 8, 1, 12, 0, 0), datetime.datetime(2024, 8, 1, 13, 0, 0)],
                },
            ],
            2,
            {
                "number_of_migrations": 2,
                "average_time": 45.0,
                "total_number_of_vms": 3,
                "total_disk_size_for_migration": 3.0,
                "total_migration_hrs": 2,
                "average_disk_size_gb": 1.1,
                "average_transfer_speed": 1.5,
                "max_minutes": 60.0,
                "min_minutes": 30.0,
                "cold_migrations": 1,
                "cold_migrated_vms": 1,
                "warm_migrations": 1,
                "warm_migrated_vms": 2,
            },
        ),
    ],
)
def test_prepare_migration_information(migration_analyzer, test_id, migrations, active_migration_hours, expected_result):
    actual_result = migration_analyzer.prepare_migration_information(migrations, active_migration_hours)
    
    # Basic assertion for key counts
    assert actual_result["number_of_migrations"] == expected_result["number_of_migrations"]
    assert actual_result["total_migration_hrs"] == expected_result["total_migration_hrs"]
    assert actual_result["cold_migrations"] == expected_result["cold_migrations"]
    assert actual_result["warm_migrations"] == expected_result["warm_migrations"]
    assert actual_result["average_transfer_speed"] == expected_result["average_transfer_speed"]

# Test for calculate_active_migration_hours
def test_calculate_active_migration_hours(migration_analyzer):
    mtv_plan_data = {
        'items': [
            {
                'status': {
                    'migration': {
                        'started': '2024-07-29T10:00:00Z',
                        'completed': '2024-07-29T12:00:00Z',
                    }
                }
            },
            {
                'status': {
                    'migration': {
                        'started': '2024-07-30T10:00:00Z',
                        'completed': '2024-07-30T13:00:00Z',
                    }
                }
            }
        ]
    }
    expected_hours = 5.0  # 2 hours + 3 hours = 5 hours total
    actual_hours = migration_analyzer.calculate_active_migration_hours(mtv_plan_data)
    assert actual_hours == expected_hours

# Complex test data for migration_success_info
mtv_plan_data = {
    "items": [
        {
            "status": {
                "migration": {
                    "started": "2025-03-22T12:00:00",
                    "completed": "2025-03-22T13:00:00",
                    "vms": [
                        {
                            "name": "vm1",
                            "warm": {'consecutiveFailures': 0, 'failures': 0, 'nextPrecopyAt': '2025-03-22T13:13:36Z', 'precopies': [{'createTaskId': 'task-755359', 'end': '2025-03-22T06:43:26Z', 'removeTaskId': 'task-755470', 'snapshot': 'snapshot-91386', 'start': '2025-03-22T05:43:26Z'}], 'successes': 14},
                            "conditions": [{"type": "Succeeded"}],
                            "pipeline": [{'annotations': {'unit': 'MB'}, 'completed': '2025-03-22T12:19:47Z', 'description': 'Copy disks.', 'name': 'DiskTransferV2v', 'phase': 'Completed', 'progress': {'completed': 153600, 'total': 153600}, 'started': '2025-03-22T12:08:26Z'}],
                        }
                    ]
                }
            },
            "spec": {
                "vms": ["vm1"]
            },
            "metadata": {
                "name": "plan1"
            }
        },
        {
            "status": {
                "migration": {
                    "started": "2025-03-22T13:00:00",
                    "completed": "2025-03-22T14:00:00",
                    "vms": [
                        {
                            "name": "vm3",
                            "warm": None,
                            "conditions": [{"type": "Failed"}],
                            "pipeline": [{'annotations': {'unit': 'MB'}, 'completed': '2025-03-22T13:19:47Z', 'description': 'Copy disks.', 'name': 'DiskTransferV2v', 'phase': 'Completed', 'progress': {'completed': 153600, 'total': 153600}, 'started': '2025-03-22T13:08:26Z'}],
                        }
                    ]
                }
            },
            "spec": {
                "vms": ["vm3"]
            },
            "metadata": {
                "name": "plan2"
            }
        }
    ]
}

# Test for get_migration_success_info
def test_get_migration_success_info(migration_analyzer):
    all_vms = defaultdict(list)
    successful_migrations, failed_migrations, migration_window = migration_analyzer.get_migration_success_info(mtv_plan_data, all_vms)
    
    # Check that we correctly identified successful and failed migrations
    assert len(successful_migrations) == 1
    assert len(failed_migrations) == 1
    assert successful_migrations[0]["name"] == "plan1"
    assert failed_migrations[0]["name"] == "plan2"
    
    # Check migration windows
    assert len(migration_window) >= 3  # Should have at least 3 hours
    assert successful_migrations[0]["migration_type"] == "warm"
    assert failed_migrations[0]["migration_type"] == "cold"

# Tests for _filter_successful_vms
@pytest.mark.parametrize(
    "test_id, all_vms, expected_count, expected_names",
    [
        (
            "mixed_success_failure",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "disk_size": 1024,
                        "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                        "duration": 60.0,
                        "succeeded": True,
                    },
                    {
                        "name": "vm2",
                        "disk_size": 2048,
                        "start_time": datetime.datetime(2024, 7, 25, 11, 0, 0),
                        "duration": 30.0,
                        "succeeded": False,
                    },
                ],
                "windows": [
                    {
                        "name": "vm3",
                        "disk_size": 4096,
                        "start_time": datetime.datetime(2024, 7, 25, 12, 0, 0),
                        "duration": 45.0,
                        "succeeded": True,
                    }
                ]
            },
            2,
            ["vm1", "vm3"],
        ),
        (
            "all_successful",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "disk_size": 1024,
                        "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                        "duration": 60.0,
                        "succeeded": True,
                    }
                ]
            },
            1,
            ["vm1"],
        ),
        (
            "empty_dict",
            {},
            0,
            [],
        ),
    ],
)
def test_filter_successful_vms(migration_analyzer, test_id, all_vms, expected_count, expected_names):
    filtered = migration_analyzer._filter_successful_vms(all_vms)
    
    assert len(filtered) == expected_count
    if expected_count > 0:
        assert all(vm["succeeded"] for vm in filtered)
        actual_names = [vm["name"] for vm in filtered]
        assert actual_names == expected_names


# Tests for _calculate_vm_transfer_speed
@pytest.mark.parametrize(
    "test_id, vm, expected_speed",
    [
        (
            "standard_transfer",
            {"disk_size": 3072, "duration": 60.0},
            3.0,
        ),
        (
            "fast_transfer",
            {"disk_size": 10240, "duration": 30.0},
            20.0,
        ),
        (
            "zero_duration",
            {"disk_size": 1024, "duration": 0.0},
            0.0,
        ),
    ],
)
def test_calculate_vm_transfer_speed(migration_analyzer, test_id, vm, expected_speed):
    speed = migration_analyzer._calculate_vm_transfer_speed(vm)
    assert abs(speed - expected_speed) < 0.01  # Allow small floating point differences


# Tests for _calculate_vm_totals
@pytest.mark.parametrize(
    "test_id, vms, expected_result",
    [
        (
            "two_vms",
            [
                {"disk_size": 1024, "duration": 60.0},
                {"disk_size": 2048, "duration": 30.0},
            ],
            (2, 3.0, 90.0),
        ),
        (
            "single_vm",
            [
                {"disk_size": 5120, "duration": 120.0},
            ],
            (1, 5.0, 120.0),
        ),
    ],
)
def test_calculate_vm_totals(migration_analyzer, test_id, vms, expected_result):
    total_vms, total_disk_gb, total_mins = migration_analyzer._calculate_vm_totals(vms)
    
    expected_vms, expected_disk, expected_mins = expected_result
    assert total_vms == expected_vms
    assert abs(total_disk_gb - expected_disk) < 0.01
    assert abs(total_mins - expected_mins) < 0.01


# Tests for prepare_vm_inform
@pytest.mark.parametrize(
    "test_id, all_vms, concurrent_hours, expected_result",
    [
        (
            "two_vms_sequential",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "disk_size": 2048,
                        "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                        "duration": 60.0,
                        "succeeded": True,
                    },
                    {
                        "name": "vm2",
                        "disk_size": 4096,
                        "start_time": datetime.datetime(2024, 7, 25, 11, 0, 0),
                        "duration": 120.0,
                        "succeeded": True,
                    },
                ]
            },
            2.0,
            {
                "total_vms": 2,
                "max_minutes": 120.0,
                "min_minutes": 60.0,
                "longest_vm_name": "vm2",
                "shortest_vm_name": "vm1",
                "largest_vm_name": "vm2",
                "largest_vm_disk_gb": 4.0,
                "smallest_vm_name": "vm1",
                "smallest_vm_disk_gb": 2.0,
                "average_time_mins": 90.0,
                "total_disk_size_gb": 6.0,
                "total_migration_hours": 2.0,
                "aggregate_speed_gb_per_hr": 3.0,
            },
        ),
        (
            "two_vms_concurrent_hours",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "disk_size": 10240,
                        "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                        "duration": 120.0,
                        "succeeded": True,
                    },
                    {
                        "name": "vm2",
                        "disk_size": 10240,
                        "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                        "duration": 120.0,
                        "succeeded": True,
                    },
                ]
            },
            2.0,
            {
                "total_vms": 2,
                "total_disk_size_gb": 20.0,
                "total_migration_hours": 2.0,
                "aggregate_speed_gb_per_hr": 10.0,
            },
        ),
        (
            "empty_all_vms",
            {},
            1.0,
            {},
        ),
        (
            "only_failed_vms",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "disk_size": 2048,
                        "start_time": datetime.datetime(2024, 7, 25, 10, 0, 0),
                        "duration": 60.0,
                        "succeeded": False,
                    }
                ]
            },
            1.0,
            {},
        ),
    ],
)
def test_prepare_vm_inform(migration_analyzer, test_id, all_vms, concurrent_hours, expected_result):
    vm_info = migration_analyzer.prepare_vm_inform(all_vms, concurrent_hours)
    
    if not expected_result:
        assert vm_info == {}
    else:
        for key, expected_value in expected_result.items():
            assert key in vm_info, f"Missing key: {key}"
            actual_value = vm_info[key]
            if isinstance(expected_value, float):
                assert abs(actual_value - expected_value) < 0.01, f"{key}: expected {expected_value}, got {actual_value}"
            else:
                assert actual_value == expected_value, f"{key}: expected {expected_value}, got {actual_value}"
