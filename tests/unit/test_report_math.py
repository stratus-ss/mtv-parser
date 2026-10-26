import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "mtv_parser" / "mtv_plan_parser.py"

WINDOW_YAML = """\
items:
- metadata:
    name: fast
  spec:
    vms:
    - fastvm
  status:
    migration:
      started: "2026-10-08T18:21:17"
      completed: "2026-10-08T19:21:48"
      vms:
      - name: fastvm
        operatingSystem: rhel8_64Guest
        started: "2026-10-08T18:21:17"
        completed: "2026-10-08T19:21:48"
        conditions:
        - type: Succeeded
        pipeline:
        - name: DiskTransfer
          phase: Completed
          started: "2026-10-08T18:22:29"
          completed: "2026-10-08T19:03:42"
          progress:
            total: 31960064
            completed: 31960064
- metadata:
    name: pair
  spec:
    vms:
    - short
    - long
  status:
    migration:
      started: "2026-10-03T03:32:58"
      completed: "2026-10-03T04:31:42"
      vms:
      - name: short
        operatingSystem: rhel8_64Guest
        started: "2026-10-03T03:32:58"
        completed: "2026-10-03T04:11:57"
        conditions:
        - type: Succeeded
        pipeline:
        - name: DiskTransfer
          phase: Completed
          started: "2026-10-03T03:33:45"
          completed: "2026-10-03T03:40:00"
          progress:
            total: 1048576
            completed: 1048576
      - name: long
        operatingSystem: rhel8_64Guest
        started: "2026-10-03T03:32:58"
        completed: "2026-10-03T04:31:42"
        conditions:
        - type: Succeeded
        pipeline:
        - name: DiskTransfer
          phase: Completed
          started: "2026-10-03T03:34:00"
          completed: "2026-10-03T04:17:21"
          progress:
            total: 24160256
            completed: 24160256
- metadata:
    name: lateplan
  spec:
    vms:
    - lateplan
  status:
    migration:
      started: "2026-10-15T19:49:10"
      completed: "2026-10-15T20:03:53"
      vms:
      - name: lateplan
        operatingSystem: rhel8_64Guest
        started: "2026-10-15T19:49:10"
        completed: "2026-10-15T20:03:53"
        conditions:
        - type: Succeeded
        pipeline:
        - name: DiskTransfer
          phase: Completed
          started: "2026-10-15T17:43:56"
          completed: "2026-10-15T17:47:53"
          progress:
            total: 226304
            completed: 226304
"""


def _write_window(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plans" / "multiple"
    plan_dir.mkdir(parents=True)
    window = plan_dir / "window.yaml"
    window.write_text(WINDOW_YAML)


def _run_parser(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _lines_with(stdout: str, label: str) -> list[str]:
    matches = []
    for line in stdout.splitlines():
        if label in line:
            matches.append(line)
    return matches


def _line(stdout: str, label: str) -> str:
    matches = _lines_with(stdout, label)
    assert len(matches) == 1
    return matches[0]


def test_window_prints_audit_edges(tmp_path: Path):
    _write_window(tmp_path)
    result = _run_parser(tmp_path, "--since", "2026-10-01", "--until", "2026-10-10")
    assert result.returncode == 0
    stdout = result.stdout
    assert "2" in _line(stdout, "Number of Cold Migration Plans:")
    assert "3" in _line(stdout, "Number of Cold Migrated VMs:")
    assert "30944.5" in _line(stdout, "Highest plan GiB/hour over plan runtime:")
    assert "43.4" in _line(stdout, "Longest VM disk-copy minutes:")
    assert "45434.5" in _line(stdout, "Highest VM GiB/hour over disk-copy time:")
    assert "Longest plan GiB/hour over plan runtime:" not in stdout
    assert "lateplan" not in stdout

    runtime_lines = _lines_with(stdout, "Average runtime in minutes:")
    assert len(runtime_lines) == 2
    assert "59.6" in runtime_lines[0]
    assert "52.7" in runtime_lines[1]

    hour_lines = _lines_with(stdout, "Hours migrations were running:")
    assert len(hour_lines) == 2
    assert "1.99" in hour_lines[0]
    assert "1.99" in hour_lines[1]

    size_lines = _lines_with(stdout, "Approximate plan size (GiB) completed in an hour:")
    assert len(size_lines) == 2
    assert "28090.1" in size_lines[0]
    assert "28090.1" in size_lines[1]


def test_since_only_includes_late_plan(tmp_path: Path):
    _write_window(tmp_path)
    result = _run_parser(tmp_path, "--since", "2026-10-01")
    assert result.returncode == 0
    assert "lateplan" in result.stdout
    assert "VMS CONTINUING PAST UNTIL" not in result.stdout
    assert "3" in _line(result.stdout, "Number of Cold Migration Plans:")


def test_until_only_excludes_late_plan(tmp_path: Path):
    _write_window(tmp_path)
    result = _run_parser(tmp_path, "--until", "2026-10-10")
    assert result.returncode == 0
    assert "lateplan" not in result.stdout
    assert "2" in _line(result.stdout, "Number of Cold Migration Plans:")


def test_bad_date_fails_before_plans(tmp_path: Path):
    result = _run_parser(tmp_path, "--since", "2026-13-40")
    assert result.returncode != 0
    assert "Invalid date format. Expected YYYY-MM-DD" in result.stderr
    assert "No migration data available" not in result.stdout
