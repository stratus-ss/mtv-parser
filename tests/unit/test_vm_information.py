import pytest
from datetime import datetime, timedelta
from collections import defaultdict

# Import the standalone function and MigrationAnalyzer class from production code
from mtv_parser.vm_information import calculate_effective_migration_time
from mtv_parser.migration_information import MigrationAnalyzer


@pytest.fixture
def migration_analyzer():
    """Fixture to provide MigrationAnalyzer instance for testing."""
    return MigrationAnalyzer()


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
                "migration_type" : "warm"
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
        # Multiple precopies with significant drop
        (
            "multiple_precopies_drop",
            {
                "warm": {
                    "precopies": [
                        {"start": "2024-07-24T10:00:00", "end": "2024-07-24T11:00:00"},
                        {"start": "2024-07-24T11:00:00", "end": "2024-07-24T11:30:00"},
                    ]
                },
                "migration_type" : "warm"
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
        # Multiple precopies without significant drop
        (
            "multiple_precopies_no_drop",
            {
                "warm": {
                    "precopies": [
                        {"start": "2024-07-24T10:00:00", "end": "2024-07-24T10:45:00"},
                        {"start": "2024-07-24T10:45:00", "end": "2024-07-24T11:30:00"},
                    ]
                },
                "migration_type" : "warm"
            },
            {
                "status": {
                    "migration": {
                        "started": "2024-07-24T09:00:00",
                        "completed": "2024-07-24T12:00:00",
                    }
                },
                "migration_type" : "warm"
            },
            90.0,
        ),
        # Edge cases: No precopies
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
        # Edge cases: Empty precopies list
        (
            "edge_empty_precopies",
            {"warm": {"precopies": []}},
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
        # Edge cases: Precopy with missing start or end time
        (
            "edge_missing_time",
            {"warm": {"precopies": [{"start": "2024-07-24T10:00:00"}]}},
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
def test_calculate_effective_migration_time(test_id, vm, entry, expected_time):
    actual_time = calculate_effective_migration_time(vm, entry)
    assert actual_time == expected_time


@pytest.mark.parametrize(
    "test_id, vm, effective_duration, expected_information",
    [
        # Happy path: DiskTransfer phase present
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
            },
            60.0,
            {
                "linux": {
                    "name": "test_vm",
                    "disk_size": 1024,
                    "start_time": datetime(2024, 7, 25, 10, 0, 0),
                    "duration": 60.0,
                    "migration_type": "cold",
                    "migration_window": [
                        datetime(2024, 7, 25, 10, 0, 0),
                        datetime(2024, 7, 25, 11, 0, 0)
                    ]
                }
            },
        ),
        # Edge cases: DiskTransfer phase marked as Pending
        (
            "edge_vm_pending",
            {
                "pipeline": [
                    {
                        "name": "DiskTransfer",
                        "phase": "Pending"
                    }
                ],
                "operatingSystem": "linux",
                "name": "test_vm",
                "migration_type": "cold",
            },
            0.0,
            {
                "linux": {
                    "name": "test_vm",
                    "disk_size": 0,
                    "start_time": timedelta(seconds=0),
                    "duration": 0.0,
                    "migration_type": "cold",
                    "migration_window": None
                }
            },
        ),
    ],
)
def test_extract_vm_information(migration_analyzer, test_id, vm, effective_duration, expected_information):
    """Test extract_vm_information using current production MigrationAnalyzer class."""
    actual_information = migration_analyzer.extract_vm_information(vm, effective_duration)
    assert actual_information == expected_information


@pytest.mark.parametrize(
    "test_id, all_vms, expected_events",
    [
        # Happy path: VMs with start and end times
        (
            "start_end",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "start_time": datetime(2024, 7, 26, 10, 0, 0),
                        "duration": 60.0,
                    }
                ]
            },
            [
                {
                    "time": datetime(2024, 7, 26, 10, 0, 0),
                    "type": "start",
                    "os": "linux",
                    "name": "vm1",
                    "duration": 60.0,
                    "event_end": datetime(2024, 7, 26, 11, 0, 0)
                },
                {
                    "time": datetime(2024, 7, 26, 11, 0, 0),
                    "type": "end",
                    "os": "linux",
                    "name": "vm1",
                    "duration": 60.0,
                },
            ],
        ),
        # Edge cases: Missing start time
        ("edge_no_start", {"linux": [{"name": "vm1", "duration": 60.0}]}, []),
        # Edge cases: Missing duration
        (
            "edge_no_duration",
            {"linux": [{"name": "vm1", "start_time": datetime(2024, 7, 26, 10, 0, 0)}]},
            [],
        ),
        # Edge cases: Empty all_vms
        ("edge_empty_all_vms", {}, []),
    ],
)
def test_sort_migration_events(migration_analyzer, test_id, all_vms, expected_events):
    """Test sort_migration_events using current production MigrationAnalyzer class."""
    actual_events = migration_analyzer.sort_migration_events(all_vms)
    assert actual_events == expected_events


# Note: The following tests (create_timeline, significant_drops, get_hourly_counts, 
# analyze_concurrent_migrations with all_vms input) test functionality that has been
# refactored in the production code. The timeline creation now happens inline in
# mtv_plan_parser.py (lines 63-81) and MigrationAnalyzer.analyze_concurrent_migrations()
# now takes pre-computed hourly data rather than raw VM data.
#
# These functions are tested in test_migration_information.py with the current signatures.
# To test the end-to-end timeline functionality, integration tests would be more appropriate.
