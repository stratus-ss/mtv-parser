import os
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def _to_naive_utc(value: datetime) -> datetime:
    """Normalize datetimes to naive UTC for consistent matplotlib date math."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _cluster_tasks(tasks: list[dict], gap_hours: float = 12.0) -> list[list[dict]]:
    """Split tasks into waves when consecutive activity is separated by gap_hours."""
    if not tasks:
        return []

    ordered = sorted(tasks, key=lambda t: t["start"])
    clusters: list[list[dict]] = [[ordered[0]]]
    gap = gap_hours / 24.0  # matplotlib date units are days

    for task in ordered[1:]:
        cluster_end = max(t["end"] for t in clusters[-1])
        # New wave if this task starts long after the previous wave finished
        if (mdates.date2num(task["start"]) - mdates.date2num(cluster_end)) > gap:
            clusters.append([task])
        else:
            clusters[-1].append(task)

    return clusters


def _configure_time_axis(ax, start_nums, end_nums) -> None:
    span_days = float(max(end_nums) - min(start_nums))
    padding = max(span_days * 0.05, 1 / 48)  # at least ~30 minutes
    ax.set_xlim(min(start_nums) - padding, max(end_nums) + padding)

    if span_days <= 0.5:
        major = mdates.HourLocator(interval=1)
        minor = mdates.MinuteLocator(interval=15)
        fmt = mdates.DateFormatter("%H:%M")
    elif span_days <= 2:
        major = mdates.HourLocator(interval=2)
        minor = mdates.HourLocator(interval=1)
        fmt = mdates.DateFormatter("%b %d\n%H:%M")
    elif span_days <= 7:
        major = mdates.HourLocator(interval=6)
        minor = mdates.HourLocator(interval=3)
        fmt = mdates.DateFormatter("%b %d\n%H:%M")
    else:
        major = mdates.AutoDateLocator(minticks=4, maxticks=8)
        minor = mdates.DayLocator()
        fmt = mdates.ConciseDateFormatter(major)

    ax.xaxis.set_major_locator(major)
    ax.xaxis.set_minor_locator(minor)
    ax.xaxis.set_major_formatter(fmt)
    ax.xaxis_date()
    ax.grid(axis="x", which="major", linestyle="-", alpha=0.35)
    ax.grid(axis="x", which="minor", linestyle=":", alpha=0.2)


def _draw_cluster(ax, tasks: list[dict]) -> None:
    labels = [task["label"] for task in tasks]
    starts = [task["start"] for task in tasks]
    ends = [task["end"] for task in tasks]
    start_nums = mdates.date2num(starts)
    end_nums = mdates.date2num(ends)
    durations = end_nums - start_nums

    for i, (start, duration) in enumerate(zip(start_nums, durations)):
        ax.barh(i, duration, left=start, height=0.55, color="steelblue", edgecolor="navy", linewidth=0.5)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    _configure_time_axis(ax, start_nums, end_nums)

    wave_start = min(starts).strftime("%Y-%m-%d %H:%M")
    wave_end = max(ends).strftime("%Y-%m-%d %H:%M")
    ax.set_title(f"Wave: {wave_start} → {wave_end} UTC", fontsize=10)


def plot_gantt_chart(data: dict, output_path: str = "charts/migration_gantt_chart.png") -> str | None:
    """
    Plots a Gantt chart for the given dictionary of tasks.

    Migrations separated by large time gaps are drawn in separate panels so
    short transfers are not crushed by multi-week spans.

    Parameters:
    - data (dict): A dictionary where each key represents an OS type, and the value is a list of VM dictionaries.
    - output_path (str): Path to save the PNG chart.

    Returns:
    - The output path if a chart was written, otherwise None.
    """
    all_tasks = []
    for os_key, tasks in data.items():
        for task in tasks:
            start = task.get("start_time")
            end = task.get("end_time")
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue
            if end <= start:
                continue
            all_tasks.append(
                {
                    "os": os_key,
                    "name": task["name"],
                    "start": _to_naive_utc(start),
                    "end": _to_naive_utc(end),
                }
            )

    if not all_tasks:
        return None

    all_tasks.sort(key=lambda t: t["start"])

    # Label repeated VMs as attempt 1..N in chronological order
    name_totals: dict[str, int] = {}
    for task in all_tasks:
        name_totals[task["name"]] = name_totals.get(task["name"], 0) + 1
    name_seen: dict[str, int] = {}
    for task in all_tasks:
        name_seen[task["name"]] = name_seen.get(task["name"], 0) + 1
        label = f"{task['os']} - {task['name']}"
        if name_totals[task["name"]] > 1:
            label = f"{label} (attempt {name_seen[task['name']]})"
        task["label"] = label

    clusters = _cluster_tasks(all_tasks)
    heights = [max(len(cluster) * 0.55, 2.2) for cluster in clusters]
    fig, axes = plt.subplots(
        nrows=len(clusters),
        ncols=1,
        figsize=(14, sum(heights) + 0.8 * len(clusters)),
        squeeze=False,
        gridspec_kw={"height_ratios": heights},
    )

    for ax, cluster in zip(axes[:, 0], clusters):
        _draw_cluster(ax, cluster)
        ax.set_ylabel("VMs")

    axes[-1, 0].set_xlabel("Time (UTC)")
    fig.suptitle("Migration Gantt Chart", fontsize=14, y=1.01)
    fig.tight_layout()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path
