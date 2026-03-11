import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def plot_gantt_chart(data: dict) -> None:
    """
    Plots a Gantt chart for the given dictionary of tasks.

    Parameters:
    - data (dict): A dictionary where each key represents an OS type, and the value is a list of VM dictionaries.
    """
    # Prepare task data
    all_tasks = []
    for os_key, tasks in data.items():
        for task in tasks:
            all_tasks.append(
                {
                    "label": f"{os_key} - {task['name']}",
                    "start": task["start_time"],
                    "end": task["end_time"],
                }
            )

    # Sort tasks by start time
    all_tasks.sort(key=lambda x: x["start"])

    # Create figure
    fig, ax = plt.subplots(figsize=(12, len(all_tasks) * 0.5))

    # Create positions and collect time limits
    task_labels = []
    all_starts = []
    all_ends = []

    for task in all_tasks:
        task_labels.append(task["label"])
        all_starts.append(task["start"])
        all_ends.append(task["end"])

    # Convert datetimes to numerical values for plotting
    start_dates_num = mdates.date2num(all_starts)
    end_dates_num = mdates.date2num(all_ends)

    # Calculate durations properly in matplotlib's date units
    durations = [end - start for start, end in zip(start_dates_num, end_dates_num)]

    # Plot each task bar
    for i, (start, duration) in enumerate(zip(start_dates_num, durations)):
        ax.barh(i, duration, left=start, height=0.5, color="skyblue")

    # Set y-axis labels
    ax.set_yticks(range(len(task_labels)))
    ax.set_yticklabels(task_labels)

    # Configure x-axis to show times properly
    ax.xaxis_date()

    # Format x-axis ticks
    hours = mdates.HourLocator(interval=1)
    ax.xaxis.set_major_locator(hours)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # Set axis limits properly
    ax.set_xlim(min(start_dates_num), max(end_dates_num))

    # Rotate tick labels for better readability
    fig.autofmt_xdate(rotation=45)

    # Add grid lines for readability
    ax.grid(axis="x", linestyle="-", alpha=0.2)

    # Labels and title
    plt.xlabel("Time")
    plt.ylabel("Tasks")
    plt.title("Gantt Chart")

    # Adjust layout
    plt.tight_layout()

    # Save the plot
    plt.savefig("charts/migration_gantt_chart.png", dpi=300)
    plt.show()
    plt.close()


def _detect_migration_windows(all_tasks: List[Dict], gap_hours: int = 28) -> List[List[Dict]]:
    """Group tasks into windows based on time gaps.
    
    Args:
        all_tasks: List of task dictionaries sorted by start time
        gap_hours: Minimum gap in hours to define a new window
        
    Returns:
        List of task lists, one per migration window
    """
    if not all_tasks:
        return []
    
    windows = []
    current_window = [all_tasks[0]]
    
    for i in range(1, len(all_tasks)):
        current_task = all_tasks[i]
        previous_task = all_tasks[i - 1]
        
        time_gap = (current_task["start"] - previous_task["end"]).total_seconds() / 3600
        
        if time_gap >= gap_hours:
            windows.append(current_window)
            current_window = [current_task]
        else:
            current_window.append(current_task)
    
    if current_window:
        windows.append(current_window)
    
    return windows


def _smart_time_formatter(time_span_hours: float) -> tuple:
    """Return appropriate locator and formatter based on time span.
    
    Args:
        time_span_hours: Duration of the time span in hours
        
    Returns:
        Tuple of (locator, formatter) for matplotlib axis
    """
    if time_span_hours < 48:
        locator = mdates.HourLocator(interval=max(1, int(time_span_hours / 24)))
        formatter = mdates.DateFormatter("%Y-%m-%d %H:%M")
    elif time_span_hours <= 720:  # 30 days
        locator = mdates.DayLocator(interval=max(1, int(time_span_hours / 720)))
        formatter = mdates.DateFormatter("%Y-%m-%d")
    else:
        locator = mdates.WeekLocator()
        formatter = mdates.DateFormatter("%Y-%m-%d")
    
    return locator, formatter


def _get_os_color_map() -> Dict[str, str]:
    """Get color mapping for OS types.
    
    Returns:
        Dictionary mapping OS type to hex color
    """
    base_colors = {
        'unknown': '#1f77b4',
        'otherGuest64': '#ff7f0e',
        'windows2019srv_64Guest': '#2ca02c',
        'windows2022srvNext_64Guest': '#d62728',
        'rhel8_64Guest': '#9467bd',
        'rhel9_64Guest': '#8c564b',
        'centos8_64Guest': '#e377c2',
        'centos7_64Guest': '#7f7f7f',
    }
    
    return base_colors


def plot_gantt_charts_by_window(data: dict, gap_hours: int = 28, output_dir: str = "charts") -> List[str]:
    """Generate multiple Gantt charts, one per migration window.
    
    Args:
        data: Dictionary where each key represents an OS type, and the value is a list of VM dictionaries
        gap_hours: Minimum gap in hours between migrations to define a new window (default: 28)
        output_dir: Directory to save output charts (default: "charts")
        
    Returns:
        List of generated PNG filenames
    """
    os_colors = _get_os_color_map()
    
    # Flatten all tasks from OS-keyed dict into single list
    all_tasks = []
    for os_key, tasks in data.items():
        for task in tasks:
            all_tasks.append({
                "label": f"{os_key} - {task['name']}",
                "start": task["start_time"],
                "end": task["end_time"],
                "os_type": os_key,
                "name": task["name"],
            })
    
    if not all_tasks:
        return []
    
    # Sort tasks by start time
    all_tasks.sort(key=lambda x: x["start"])
    
    # Detect migration windows
    windows = _detect_migration_windows(all_tasks, gap_hours)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    generated_files = []
    
    # Generate a chart for each window
    for window_idx, window_tasks in enumerate(windows, start=1):
        if not window_tasks:
            continue
            
        # Calculate time span for this window
        start_time = min(task["start"] for task in window_tasks)
        end_time = max(task["end"] for task in window_tasks)
        time_span_hours = (end_time - start_time).total_seconds() / 3600
        
        # Dynamic figure height
        num_tasks = len(window_tasks)
        fig_height = max(6, min(num_tasks * 0.4, 30))
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, fig_height))
        
        # Prepare data for plotting
        task_labels = []
        start_dates_num = []
        durations = []
        colors = []
        
        for task in window_tasks:
            task_labels.append(task["label"])
            start_num = mdates.date2num(task["start"])
            end_num = mdates.date2num(task["end"])
            start_dates_num.append(start_num)
            durations.append(end_num - start_num)
            
            # Get color for this OS type
            os_type = task["os_type"]
            color = os_colors.get(os_type, '#17becf')
            colors.append(color)
        
        # Plot bars with colors
        for i, (start, duration, color) in enumerate(zip(start_dates_num, durations, colors)):
            ax.barh(i, duration, left=start, height=0.6, color=color, edgecolor='black', linewidth=0.5)
        
        # Set y-axis labels with dynamic font size
        ax.set_yticks(range(len(task_labels)))
        font_size = max(6, min(10, 10 - num_tasks * 0.03))
        ax.set_yticklabels(task_labels, fontsize=font_size)
        
        # Configure x-axis with smart formatting
        ax.xaxis_date()
        locator, formatter = _smart_time_formatter(time_span_hours)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        
        # Set axis limits
        ax.set_xlim(min(start_dates_num), max(durations[i] + start_dates_num[i] for i in range(len(start_dates_num))))
        
        # Rotate tick labels
        fig.autofmt_xdate(rotation=45)
        
        # Add grid
        ax.grid(axis="x", linestyle="--", alpha=0.3)
        
        # Create title with window info
        start_date_str = start_time.strftime("%Y-%m-%d")
        end_date_str = end_time.strftime("%Y-%m-%d")
        title = f"Migration Window {window_idx} - {start_date_str} to {end_date_str} ({num_tasks} VMs)"
        plt.title(title, fontsize=12, fontweight='bold')
        plt.xlabel("Time", fontsize=10)
        plt.ylabel("Virtual Machines", fontsize=10)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save the plot
        filename = f"migration_gantt_window_{window_idx:02d}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        generated_files.append(filename)
    
    return generated_files


def plot_interactive_gantt_chart(data: dict, output_path: str = "charts/migration_gantt_interactive.html") -> str:
    """Generate interactive HTML Gantt chart using Plotly.
    
    Args:
        data: Dictionary where each key represents an OS type, and the value is a list of VM dictionaries
        output_path: Path for output HTML file (default: "charts/migration_gantt_interactive.html")
        
    Returns:
        Path to generated HTML file
        
    Raises:
        ImportError: If Plotly is not installed
    """
    if not PLOTLY_AVAILABLE:
        raise ImportError("Plotly is required for interactive charts. Install with: pip install plotly")
    
    os_colors = _get_os_color_map()
    
    # Flatten all tasks from OS-keyed dict
    all_tasks = []
    for os_key, tasks in data.items():
        for task in tasks:
            # Calculate duration in minutes for hover display
            duration_minutes = (task["end_time"] - task["start_time"]).total_seconds() / 60
            
            all_tasks.append({
                "Task": f"{task['name']}",
                "Start": task["start_time"],
                "Finish": task["end_time"],
                "Resource": os_key,
                "VM_Name": task["name"],
                "Disk_Size": task.get("disk_size", 0),
                "Duration_Minutes": round(duration_minutes, 2),
            })
    
    if not all_tasks:
        return output_path
    
    # Sort by start time
    all_tasks.sort(key=lambda x: x["Start"])
    
    # Create the figure using Plotly
    fig = go.Figure()
    
    # Group tasks by OS type for color coding
    for os_type in set(task["Resource"] for task in all_tasks):
        os_tasks = [task for task in all_tasks if task["Resource"] == os_type]
        color = os_colors.get(os_type, '#17becf')
        
        for i, task in enumerate(os_tasks):
            # Calculate duration in seconds for the bar width
            duration_seconds = (task['Finish'] - task['Start']).total_seconds()
            
            # Create hover text with detailed information
            hover_text = (
                f"<b>{task['VM_Name']}</b><br>"
                f"OS Type: {task['Resource']}<br>"
                f"Start: {task['Start'].strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"End: {task['Finish'].strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"Duration: {task['Duration_Minutes']:.2f} minutes<br>"
                f"Disk Size: {task['Disk_Size']:.2f} GB"
            )
            
            # Add trace for this task - use seconds for x value
            fig.add_trace(go.Bar(
                x=[duration_seconds],
                y=[task['Task']],
                base=task['Start'],
                orientation='h',
                marker=dict(color=color, line=dict(color='black', width=0.5)),
                name=os_type,
                legendgroup=os_type,
                showlegend=(i == 0),  # Only show legend once per OS type
                hovertemplate=hover_text + "<extra></extra>",
            ))
    
    # Update layout
    fig.update_layout(
        title={
            'text': "Interactive Migration Gantt Chart",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'family': 'Arial, sans-serif'}
        },
        xaxis=dict(
            title="Timeline",
            type='date',
            rangeslider=dict(visible=True),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1d", step="day", stepmode="backward"),
                    dict(count=7, label="1w", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(step="all", label="All")
                ])
            )
        ),
        yaxis=dict(
            title="Virtual Machines",
            autorange="reversed",
        ),
        barmode='overlay',
        height=max(600, len(all_tasks) * 20),
        hovermode='closest',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(size=10),
        legend=dict(
            title="OS Type",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01
        )
    )
    
    # Add grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save as standalone HTML
    fig.write_html(output_path, include_plotlyjs='cdn')
    
    return output_path
