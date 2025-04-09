import pytest
from datetime import datetime, timedelta
from mtv_parser.vm_information import (
    calculate_effective_migration_time,
    extract_vm_information,
    sort_migration_events,
    create_timeline,
    significant_drops,
    get_hourly_counts,
    analyze_concurrent_migrations,
)
from collections import defaultdict


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
    "test_id,vm, expected_information",
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
                    }
                ],
                "operatingSystem": "linux",
                "name": "test_vm",
                "migration_type": "cold",
            },
            {
                "linux": {
                    "name": "test_vm",
                    "disk_size": 1024,
                    "start_time": datetime(2024, 7, 25, 10, 0, 0),
                    "duration": 60.0,
                    "migration_type": "cold",
                    
                }
            },
        ),
        # Edge cases: DiskTransfer phase missing
        (
            "edge_disktransfer_missing",
            {"pipeline": [], "operatingSystem": "linux", "name": "test_vm", "migration_type": "cold",},
            {
                "linux": {
                    "name": "test_vm",
                    "disk_size": 0,
                    "start_time": timedelta(seconds=0),
                    "duration": 0.0,
                    "migration_type": "cold",
                }
            },
        ),
    ],
)
def test_extract_vm_information(test_id, vm, expected_information):
    actual_information = extract_vm_information(vm)
    assert actual_information == expected_information


@pytest.mark.parametrize(
    "test_id,all_vms, expected_events",
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
def test_sort_migration_events(test_id, all_vms, expected_events):
    actual_events = sort_migration_events(all_vms)
    assert actual_events == expected_events


@pytest.mark.parametrize(
    "test_id,event_list, expected_timeline, expected_max_concurrent, expected_peak_time, ",
    [
        (
            "base_case",
            [
                {
                    "time": datetime(2024, 7, 27, 10, 0, 0),
                    "type": "start",
                    "os": "linux",
                    "name": "vm1",
                    "duration": 60,
                },
                {
                    "time": datetime(2024, 7, 27, 11, 0, 0),
                    "type": "end",
                    "os": "linux",
                    "name": "vm1",
                    "duration": 60,
                },
            ],
            [
                {
                    "time": datetime(2024, 7, 27, 10, 0, 0),
                    "concurrent_counts": {"linux": 1},
                    "current_vms": {"linux": ["vm1"]},
                    "total_concurrent": 1,
                },
                {
                    "time": datetime(2024, 7, 27, 11, 0, 0),
                    "concurrent_counts": {"linux": 0},
                    "current_vms": {"linux": []},
                    "total_concurrent": 0,
                },
            ],
            1,
            datetime(2024, 7, 27, 10, 0, 0),
        ),
    ],
)
def test_create_timeline(
    test_id,
    event_list,
    expected_timeline,
    expected_max_concurrent,
    expected_peak_time,
):

    concurrent_counts = defaultdict(int)
    current_vms = defaultdict(list)
    max_concurrent = defaultdict(int)

    (
        actual_timeline,
        actual_max_concurrent,
        actual_peak_time,
    ) = create_timeline(event_list, concurrent_counts, current_vms, max_concurrent)

    assert actual_timeline == expected_timeline
    assert actual_max_concurrent == expected_max_concurrent
    assert actual_peak_time == expected_peak_time


@pytest.mark.parametrize(
    "test_id, event_list, expected_timeline, expected_max_concurrent, expected_peak_time",
    [
        (
            "edge_empty_event_list",
            [],
            [],
            0,
            None,
        ),
    ],
)
def test_create_timeline_empty_events(
    test_id,
    event_list,
    expected_timeline,
    expected_max_concurrent,
    expected_peak_time,
):
    concurrent_counts = defaultdict(int)
    current_vms = defaultdict(list)
    max_concurrent = defaultdict(int)
    (
        actual_timeline,
        actual_max_concurrent,
        actual_peak_time,
    ) = create_timeline(event_list, concurrent_counts, current_vms, max_concurrent)
    assert actual_timeline == expected_timeline
    assert actual_max_concurrent == expected_max_concurrent
    assert actual_peak_time == expected_peak_time


@pytest.mark.parametrize(
    "test_id,timeline_data, peak_time, max_concurrent_total, expected_drops",
    [
        # Happy path: Significant drop
        (
            "significant_drop",
            [
                {"time": datetime(2024, 7, 28, 10, 0, 0), "total_concurrent": 2},
                {"time": datetime(2024, 7, 28, 10, 15, 0), "total_concurrent": 0},
            ],
            datetime(2024, 7, 28, 10, 0, 0),
            2,
            [
                {
                    "time": datetime(2024, 7, 28, 10, 15, 0),
                    "from": 2,
                    "to": 0,
                    "duration_mins": 15.0,
                }
            ],
        ),
        # Edge cases: No drop
        (
            "edge_no_drop",
            [
                {"time": datetime(2024, 7, 28, 10, 0, 0), "total_concurrent": 2},
                {"time": datetime(2024, 7, 28, 10, 15, 0), "total_concurrent": 2},
            ],
            datetime(2024, 7, 28, 10, 0, 0),
            2,
            [],
        ),
        # Edge cases: No peak time
        (
            "edge_no_peak",
            [
                {"time": datetime(2024, 7, 28, 10, 0, 0), "total_concurrent": 2},
                {"time": datetime(2024, 7, 28, 10, 15, 0), "total_concurrent": 0},
            ],
            None,
            2,
            [
                {
                    "time": datetime(2024, 7, 28, 10, 15, 0),
                    "from": 2,
                    "to": 0,
                    "duration_mins": 0,
                }
            ],
        ),
        # Edge cases: Empty timeline
        ("edge_empty_timeline", [], datetime(2024, 7, 28, 10, 0, 0), 2, []),
    ],
)
def test_significant_drops(
    test_id, timeline_data, peak_time, max_concurrent_total, expected_drops
):
    actual_drops = significant_drops(timeline_data, peak_time, max_concurrent_total)
    assert actual_drops == expected_drops


@pytest.mark.parametrize(
    "test_id,hourly_snapshots, timeline_data, expected_counts",
    [
        # Happy path: Events before and within hourly snapshots
        (
            "events",
            [datetime(2024, 7, 29, 10, 0, 0), datetime(2024, 7, 29, 11, 0, 0)],
            [
                {"time": datetime(2024, 7, 29, 9, 30, 0), "total_concurrent": 1},
                {"time": datetime(2024, 7, 29, 10, 30, 0), "total_concurrent": 2},
            ],
            {datetime(2024, 7, 29, 10, 0, 0): 1, datetime(2024, 7, 29, 11, 0, 0): 2},
        ),
        # Edge cases: No events before hourly snapshots
        (
            "edge_no_prior_events",
            [datetime(2024, 7, 29, 10, 0, 0)],
            [],
            {datetime(2024, 7, 29, 10, 0, 0): 0},
        ),
        # Edge cases: Empty timeline
        (
            "edge_empty_timeline",
            [datetime(2024, 7, 29, 10, 0, 0)],
            [],
            {datetime(2024, 7, 29, 10, 0, 0): 0},
        ),
    ],
)
def test_get_hourly_counts(test_id, hourly_snapshots, timeline_data, expected_counts):

    actual_counts = get_hourly_counts(hourly_snapshots, timeline_data)

    assert actual_counts == expected_counts


@pytest.mark.parametrize(
    "test_id, all_vms, has_hourly, expected_max_concurrent, expected_max_total",
    [
        # Single VM
        (
            "single_vm",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 60.0,
                    }
                ]
            },
            True,
            {"linux": 1},
            1,
        ),
        # Two concurrent VMs of same OS
        (
            "concurrent_vms",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 60.0,
                    },
                    {
                        "name": "vm2",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 60.0,
                    },
                ]
            },
            True,
            {"linux": 2},
            2,
        ),
        # VMs from different OS types
        (
            "multiple_os",
            {
                "linux": [
                    {
                        "name": "linux_vm",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 60.0,
                    }
                ],
                "windows": [
                    {
                        "name": "win_vm",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 60.0,
                    }
                ],
            },
            True,
            {"linux": 1, "windows": 1},
            2,
        ),
        # Overlapping migrations
        (
            "overlapping_migrations",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 60.0,
                    },
                    {
                        "name": "vm2",
                        "start_time": datetime(2024, 7, 30, 10, 30, 0),
                        "duration": 60.0,
                    },
                ]
            },
            True,
            {"linux": 2},
            2,
        ),
        # Non-overlapping migrations
        (
            "non_overlapping_migrations",
            {
                "linux": [
                    {
                        "name": "vm1",
                        "start_time": datetime(2024, 7, 30, 10, 0, 0),
                        "duration": 30.0,
                    },
                    {
                        "name": "vm2",
                        "start_time": datetime(2024, 7, 30, 11, 0, 0),
                        "duration": 30.0,
                    },
                ]
            },
            True,
            {"linux": 1},
            1,
        ),
        # VMs with missing time data
    ],
)
def test_analyze_concurrent_migrations(
    test_id, all_vms, has_hourly, expected_max_concurrent, expected_max_total
):
    # Call the function to test
    result = analyze_concurrent_migrations(all_vms)

    # Verify structure of the result
    assert "max_concurrent" in result
    assert "max_concurrent_total" in result
    assert "timeline" in result
    assert "average_concurrent_vms" in result
    assert "hourly_concurrent_vms" in result
    assert "significant_drops" in result

    # Check key expected values
    assert result["max_concurrent"] == expected_max_concurrent
    assert result["max_concurrent_total"] == expected_max_total

    # Validate hourly data if present
    if has_hourly and result["hourly_concurrent_vms"]:
        # Verify hourly snapshots are chronologically ordered
        for i in range(1, len(result["hourly_concurrent_vms"])):
            assert (
                result["hourly_concurrent_vms"][i]["hour"]
                > result["hourly_concurrent_vms"][i - 1]["hour"]
            )
