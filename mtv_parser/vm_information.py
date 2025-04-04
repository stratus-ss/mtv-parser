from datetime import datetime
from datetime import timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any, Union

def calculate_effective_migration_time(vm: Dict[str, Any], entry: Dict[str, Any]) -> float:
    """
    Calculate the effective migration time based on when the precopy duration drops significantly.

    Args:
        vm (Dict[str, Any]): A dictionary containing VM information.
        entry (Dict[str, Any]): A dictionary containing migration status.

    Returns:
        float: The effective migration time in minutes.
    """
    significant_drop_threshold = 0.5  # 50% drop

    # Find all precopies for this VM
    all_precopies = []
    if "warm" in vm and "precopies" in vm["warm"]:
        for precopy in vm["warm"]["precopies"]:
            if "start" in precopy and "end" in precopy:
                start_time = datetime.fromisoformat(precopy["start"])
                end_time = datetime.fromisoformat(precopy["end"])
                duration = (end_time - start_time).total_seconds() / 60  # Minutes
                all_precopies.append({
                    "start": start_time,
                    "end": end_time,
                    "duration": duration
                })
    
    # Sort precopies by start time
    all_precopies.sort(key=lambda x: x["start"])
    
    if not all_precopies:
        # Fallback to regular migration times if no precopies
        start = datetime.fromisoformat(entry["status"]["migration"]["started"])
        end = datetime.fromisoformat(entry["status"]["migration"]["completed"])
        return (end - start).total_seconds() / 60
    
    # Get the start time from the first precopy
    migration_start = all_precopies[0]["start"]
    
    # Get the initial duration
    initial_duration = all_precopies[0]["duration"]
    
    # Find when the precopy duration drops significantly
    migration_end = all_precopies[-1]["end"]  # Default to the last precopy
    
    for i in range(1, len(all_precopies)):
        current_duration = all_precopies[i]["duration"]
        
        # If we find a significant drop from the initial duration
        if current_duration < initial_duration * significant_drop_threshold:
            migration_end = all_precopies[i]["end"]
            break
    
    # Calculate effective migration time in minutes
    effective_minutes = (migration_end - migration_start).total_seconds() / 60
    
    return effective_minutes


def extract_vm_information(vm: Dict[str, Any]) -> Dict[str, Dict[str, Union[int, timedelta]]]:
    """
    Calculate the total disk size for a migration plan.

    Args:
        vm (Dict[str, Any]): A dictionary containing VM information.

    Returns:
        Dict[str, Dict[str, Union[int, timedelta]]]: A dictionary with disk size and transfer details.
    """
    total_disk_size = 0
    total_disk_transfer_time = timedelta(seconds=0)
    disk_transfer_start_time = timedelta(seconds=0)
    vm_information = {}
    # for vm in entry["status"]["migration"]["vms"]:
    os_name = vm.get('operatingSystem', "unknown")
    vm_name = vm.get('name')

    for phase in vm["pipeline"]:
        if phase["name"] == "DiskTransfer" and "progress" in phase and "total" in phase["progress"]:
            total_disk_size += phase["progress"]["total"]
            disk_transfer_start_time = datetime.fromisoformat(phase['started'])
            disk_transfer_end_time = datetime.fromisoformat(phase["completed"])
            total_disk_transfer_time = disk_transfer_end_time - disk_transfer_start_time
    vm_information.update({os_name: {'name': vm_name, 'disk_size': total_disk_size, 
                                        'start_time': disk_transfer_start_time,
                                        'duration': total_disk_transfer_time.total_seconds() /60}})
    return vm_information


def sort_migration_events(all_vms: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Sort migration events by start time.

    Args:
        all_vms (Dict[str, List[Dict[str, Any]]]): A dictionary of VMs with their migration details.

    Returns:
        List[Dict[str, Any]]: A list of sorted migration events.
    """
    events = []
    
    # Process the all_vms dictionary
    for os_type, vms in all_vms.items():
        for vm in vms:
            vm_name = vm['name']
            # Extract start time and calculate end time
            start_time = vm.get('start_time')
            transfer_time_minutes = vm.get('duration')
            
            # Skip if we don't have the necessary time data
            if not start_time or not transfer_time_minutes:
                continue
                
            # Calculate end time by adding transfer time (in minutes) to start time
            end_time = start_time + timedelta(minutes=transfer_time_minutes)
            
            # Add a single event with both start and end times
            events.append({
                "time": start_time,
                "type": "start",
                "os": os_type,
                "name": vm_name,
                "duration": transfer_time_minutes
            })
            events.append({
                "time": end_time,
                "type": "end",
                "os": os_type,
                "name": vm_name,
                "duration": transfer_time_minutes
            })
    
    # Sort events by start time
    events.sort(key=lambda x: x["time"])
    return events

def create_timeline(event_list: List[Dict[str, Any]], concurrent_counts: Dict[str, int], 
                    current_vms: Dict[str, List[str]], max_concurrent: Dict[str, int]) -> Tuple[List[Dict[str, Any]], int, Optional[datetime], float, float]:
    """
    Create a timeline of migration events and track concurrent migrations.

    Args:
        event_list (List[Dict[str, Any]]): A list of sorted migration events.
        concurrent_counts (Dict[str, int]): A dictionary to track concurrent counts by OS.
        current_vms (Dict[str, List[str]]): A dictionary to track currently migrating VMs by OS.
        max_concurrent (Dict[str, int]): A dictionary to track maximum concurrent migrations by OS.

    Returns:
        Tuple[List[Dict[str, Any]], int, Optional[datetime], float, float]: A tuple containing the timeline, max concurrent total, peak time, total VM minutes, and total duration minutes.
    """
    total_vm_minutes = 0
    total_duration_minutes = 0
    peak_time = None
    max_concurrent_total = 0
    temp_list = []
    for event in event_list:
        os_type = event["os"]
        event_time = event["time"]
        
        duration_minutes = event['duration']
        current_vms_count = sum(concurrent_counts.values())
        total_vm_minutes += current_vms_count * duration_minutes
        total_duration_minutes += duration_minutes
        
        if event["type"] == "start":
            concurrent_counts[os_type] += 1
            current_vms[os_type].append(event["name"])
        else:  # end event
            concurrent_counts[os_type] -= 1
            if event["name"] in current_vms[os_type]:
                current_vms[os_type].remove(event["name"])
        
        # Update maximum concurrency for this OS type
        max_concurrent[os_type] = max(max_concurrent[os_type], concurrent_counts[os_type])
        
        # Calculate total concurrent VMs across all OS types
        total_concurrent = sum(concurrent_counts.values())
        
        # Update overall peak concurrency
        if total_concurrent > max_concurrent_total:
            max_concurrent_total = total_concurrent
            peak_time = event_time
        
        # Record the state at this point in time
        timeline_point = {
            "time": event_time,
            "concurrent_counts": dict(concurrent_counts),
            "current_vms": {k: list(v) for k, v in current_vms.items()},
            "total_concurrent": total_concurrent
        }
        temp_list.append(timeline_point)
    return(temp_list, max_concurrent_total, peak_time, total_vm_minutes, total_duration_minutes)

def significant_drops(timeline_data: List[Dict[str, Any]], peak_time: Optional[datetime], max_concurrent_total: int) -> List[Dict[str, Any]]:
    """
    Identify significant drops in concurrent migrations after the peak.

    Args:
        timeline_data (List[Dict[str, Any]]): A list of timeline points.
        peak_time (Optional[datetime]): The time of the peak concurrency.
        max_concurrent_total (int): The maximum total concurrency.

    Returns:
        List[Dict[str, Any]]: A list of significant drops.
    """
    drop_threshold = 0.5  # 50% drop
    drop_list = []
    for i in range(1, len(timeline_data)):
        prev_count = timeline_data[i-1]["total_concurrent"]
        curr_count = timeline_data[i]["total_concurrent"]
        
        # Only consider significant drops from near-peak levels
        if prev_count > max_concurrent_total * 0.8 and curr_count < prev_count * (1 - drop_threshold):
            minutes_after_peak = (timeline_data[i]["time"] - peak_time).total_seconds() / 60 if peak_time else 0
            drop_list.append({
                "time": timeline_data[i]["time"],
                "from": prev_count,
                "to": curr_count,
                "duration_mins": minutes_after_peak
            })
    return drop_list

def get_hourly_counts(hourly_snapshots: List[datetime], timeline_data: List[Dict[str, Any]]) -> Dict[datetime, int]:
    """
    Calculate the number of concurrent migrations at each hour.

    Args:
        hourly_snapshots (List[datetime]): A list of hourly timestamps.
        timeline_data (List[Dict[str, Any]]): A list of timeline points.

    Returns:
        Dict[datetime, int]: A dictionary mapping each hour to the number of concurrent migrations.
    """
    hourly_counts = {}
    for hour in hourly_snapshots:
        # Find the last event before this hour
        last_event_before = None
        for event_data in timeline_data:
            if event_data["time"] <= hour:
                last_event_before = event_data
            else:
                break
        
        if last_event_before:
            hourly_counts[hour] = last_event_before["total_concurrent"]
        else:
            hourly_counts[hour] = 0
    return hourly_counts

def analyze_concurrent_migrations(all_vms: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Analyze concurrent VM migrations based on transfer start times and durations.

    Args:
        all_vms (Dict[str, List[Dict[str, Any]]]): A dictionary of VMs with their migration details.

    Returns:
        Dict[str, Any]: A dictionary containing analysis results.
    """
    # Create a list to store all VM migration events
    events = sort_migration_events(all_vms)
    # No events? Return empty data
    if not events:
        return {
            "max_concurrent": {},
            "max_concurrent_total": 0,
            "timeline": [],
            "average_concurrent_vms": 0,
            "hourly_concurrent_vms": []
        }
    
    # Track concurrent migrations
    concurrent_counts = defaultdict(int)
    max_concurrent = defaultdict(int)
    current_vms = defaultdict(list)
    timeline_data = []
        
    # Get the start and end time range for hourly calculations
    start_time = events[0]["time"]
    end_time = events[-1]["time"]
    
    # Calculate hourly snapshots
    hourly_snapshots = []
    current_hour = start_time.replace(minute=0, second=0, microsecond=0)
    
    while current_hour <= end_time:
        hourly_snapshots.append(current_hour)
        current_hour += timedelta(hours=1)
    
    total_duration_minutes = 0
    
    # Process events in chronological order
    timeline_data, max_concurrent_total, peak_time, total_vm_minutes, total_duration_minutes = create_timeline(events, concurrent_counts, current_vms, max_concurrent)
    # Calculate average concurrent VMs
    avg_concurrent_vms = round(total_vm_minutes / total_duration_minutes, 2) if total_duration_minutes > 0 else 0
    
    # Calculate VM count at each hourly snapshot
    hourly_counts = get_hourly_counts(hourly_snapshots, timeline_data)
    
    # Format hourly data for report
    hourly_concurrent_vms = [{"hour": hour, "vms": count} for hour, count in sorted(hourly_counts.items())]    
    
    return {
        "max_concurrent": dict(max_concurrent),
        "max_concurrent_total": max_concurrent_total,
        "peak_time": peak_time,
        "average_concurrent_vms": avg_concurrent_vms,
        "timeline": timeline_data,
        "significant_drops": significant_drops(timeline_data, peak_time, max_concurrent_total),
        "hourly_concurrent_vms": hourly_concurrent_vms
    }
