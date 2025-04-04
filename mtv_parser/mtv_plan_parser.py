import yaml
from datetime import datetime, timedelta
from collections import defaultdict
from clioutput import CLIOutput
from vm_information import extract_vm_information, analyze_concurrent_migrations, calculate_effective_migration_time
from visualization import plot_gantt_chart



def add_to_dict(vm_information: dict, dict_to_update: dict, effective_duration: float) -> list[dict]:
    dict_key = next(iter(vm_information.keys()))
    transfer_start = vm_information[dict_key]['start_time']
    transfer_end_time = transfer_start + timedelta(minutes=effective_duration)
    if not transfer_start or not effective_duration:
        return
    dict_to_update[dict_key].append({
        'name': vm_information[dict_key]['name'],
        'disk_size': vm_information[dict_key]['disk_size'],
        'start_time': transfer_start,
        'end_time': transfer_end_time,
        'duration': effective_duration, 
    })
    return(dict_to_update)


def main():
    with open("examples/vm-plans-sample2.yaml", "r") as yaml_file:
        mtv_plan_data = yaml.safe_load(yaml_file)

    output = CLIOutput()
    successful_migrations = []
    failed_migrations = []
    all_vms = defaultdict(list)
    for entry in mtv_plan_data["items"]:
        total_disk_for_current_migration = 0
        if "completed" in entry["status"]["migration"].keys():
            for vms in entry["status"]["migration"]["vms"]:
                
                # Calculate effective duration using the new function
                effective_duration = calculate_effective_migration_time(vms, entry)
                
                # Calculate total disk size
                vm_information = extract_vm_information(vms)
                total_disk_for_current_migration += next(iter(vm_information.values()))['disk_size']
                add_to_dict(vm_information, all_vms, effective_duration)
                
                number_of_vms = len(entry["spec"]["vms"])
                vms_failed = False
                for vm in vms["conditions"]:
                    if vm["type"] != "Succeeded":
                        vms_failed = True
                
            
            migration_dict = {
                "name": entry["metadata"]["name"],
                "total_duration_mins": effective_duration,
                "vms": number_of_vms,
                "vms_failed": f"{vms_failed}",
                "total_disk_size": total_disk_for_current_migration,
                "duration": effective_duration,
                "start_time":  next(iter(vm_information.values()))['start_time']
            }
            
            if vms_failed:
                failed_migrations.append(migration_dict)
            else:
                successful_migrations.append(migration_dict)
    plot_gantt_chart(all_vms)
    concurrency_data = analyze_concurrent_migrations(all_vms)
    if failed_migrations:
        output.write(output.migration_output(failed_migrations, "failed"))
        output.write(("\n\n"))
    output.write(output.migration_output(successful_migrations, "successful"))
    output.write(("\n\n"))
    output.write(output.operating_system_report(all_vms))
    output.write(("\n\n"))
    output.write(output.generate_concurrency_report(concurrency_data))
    output.close()


if __name__ == "__main__":
    main()
