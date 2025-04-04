import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def plot_gantt_chart(data):
    """
    Plots a Gantt chart for the given dictionary of tasks.
    
    Parameters:
    - data (dict): A dictionary where each key represents an OS type, and the value is a list of VM dictionaries.
    """
    # Prepare task data
    all_tasks = []
    for os_key, tasks in data.items():
        for task in tasks:
            all_tasks.append({
                'label': f"{os_key} - {task['name']}",
                'start': task['start_time'],
                'end': task['end_time']
            })
    
    # Sort tasks by start time
    all_tasks.sort(key=lambda x: x['start'])
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, len(all_tasks) * 0.5))
    
    # Create positions and collect time limits
    task_labels = []
    all_starts = []
    all_ends = []
    
    for task in all_tasks:
        task_labels.append(task['label'])
        all_starts.append(task['start'])
        all_ends.append(task['end'])
    
    # Convert datetimes to numerical values for plotting
    start_dates_num = mdates.date2num(all_starts)
    end_dates_num = mdates.date2num(all_ends)
    
    # Calculate durations properly in matplotlib's date units
    durations = [end - start for start, end in zip(start_dates_num, end_dates_num)]
    
    # Plot each task bar
    for i, (start, duration) in enumerate(zip(start_dates_num, durations)):
        ax.barh(i, duration, left=start, height=0.5, color='skyblue')
    
    # Set y-axis labels
    ax.set_yticks(range(len(task_labels)))
    ax.set_yticklabels(task_labels)
    
    # Configure x-axis to show times properly
    ax.xaxis_date()
    
    # Format x-axis ticks
    hours = mdates.HourLocator(interval=1)
    ax.xaxis.set_major_locator(hours)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # Set axis limits properly
    ax.set_xlim(min(start_dates_num), max(end_dates_num))
    
    # Rotate tick labels for better readability
    fig.autofmt_xdate(rotation=45)
    
    # Add grid lines for readability
    ax.grid(axis='x', linestyle='-', alpha=0.2)
    
    # Labels and title
    plt.xlabel('Time')
    plt.ylabel('Tasks')
    plt.title('Gantt Chart')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the plot
    plt.savefig('migration_gantt_chart.png', dpi=300)
    plt.close()
