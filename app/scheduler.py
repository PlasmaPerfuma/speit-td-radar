# -*- coding: utf-8 -*-
"""Schedule config + Windows Task Scheduler integration.

Schedule rules live in ``data/schedule.json`` so they can change every semester
without touching code or re-running the installer.

Example::

    {
      "task_name": "TD Radar Poll",
      "command": "C:\\\\...\\\\tdradar.exe",
      "arguments": "canvas poll --once --download --process",
      "trigger": {
        "type": "weekly",
        "time": "11:30",
        "weekdays": ["MON", "TUE"],
        "interval_minutes": 5,
        "until": "23:59",
        "other_days_time": "12:00"
      }
    }
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import paths

SCHEDULE_PATH = paths.DATA_DIR / "schedule.json"

DEFAULT_SCHEDULE = {
    "task_name": "TD Radar Poll",
    "command": "",
    "arguments": "canvas poll --once --download --process",
    "trigger": {
        "type": "weekly",
        "time": "11:30",
        "weekdays": ["MON", "TUE"],
        "interval_minutes": 5,
        "until": "23:59",
        "other_days_time": "12:00",
    },
}

WEEKDAY_MAP = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday",
    "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday",
}


def default_command() -> str:
    """Executable to schedule.

    Packaged: the exe itself. Dev checkout: the exe in dist/ when present,
    otherwise ``python app\\tdradar.py``.
    """
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable
    for candidate in (paths.ROOT / "dist" / "tdradar" / "tdradar.exe",
                      paths.DATA_DIR.parent / "tdradar" / "tdradar.exe"):
        if candidate.exists():
            return str(candidate)
    return f'"{sys.executable}" "{paths.APP / "tdradar.py"}"'


def load_schedule() -> dict:
    if SCHEDULE_PATH.exists():
        try:
            data = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg = json.loads(json.dumps(DEFAULT_SCHEDULE))
                cfg.update({k: v for k, v in data.items() if k != "trigger"})
                cfg["trigger"].update(data.get("trigger") or {})
                return cfg
        except Exception:
            pass
    cfg = json.loads(json.dumps(DEFAULT_SCHEDULE))
    cfg["command"] = default_command()
    return cfg


def save_schedule(cfg: dict) -> Path:
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return SCHEDULE_PATH


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        raise RuntimeError("PowerShell not found")
    return exe


def _run_ps(script: str) -> tuple[int, str]:
    """Run a PowerShell script file and return (exit code, output).

    The script is written to a temp file and executed with ``-File`` because
    inline ``-Command`` mangles ``&``, quotes, and ``$`` in task actions.
    Output is captured through a file: pipes are blocked in some sandbox modes.
    """
    import os
    import tempfile
    import time as _t
    fd, script_tmp = tempfile.mkstemp(prefix="schedule_", suffix=".ps1",
                                      dir=str(paths.DATA_DIR))
    os.close(fd)
    script_path = Path(script_tmp)
    out_path = script_path.with_suffix(".log")
    proc = None
    try:
        script_path.write_text(script, encoding="utf-8-sig")
        with out_path.open("w", encoding="utf-8", errors="replace") as handle:
            proc = subprocess.run(
                [_powershell(), "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
                stdout=handle, stderr=subprocess.STDOUT,
            )
        text = out_path.read_text(encoding="utf-8", errors="replace")
    finally:
        for p in (script_path, out_path):
            for _ in range(5):
                try:
                    p.unlink()
                    break
                except OSError:
                    _t.sleep(0.2)
    return (proc.returncode if proc else 1), text


def _ps_quote(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def build_actions(cfg: dict) -> list[dict]:
    t = cfg["trigger"]
    others = [d for d in WEEKDAY_MAP if d not in t["weekdays"]]
    actions = [
        {
            "weekday": WEEKDAY_MAP[d],
            "time": t["time"],
            "interval": int(t["interval_minutes"]),
            "until": t["until"],
        }
        for d in t["weekdays"]
    ]
    if others and t.get("other_days_time"):
        actions.append({
            "weekday": ",".join(WEEKDAY_MAP[d] for d in others),
            "time": t["other_days_time"],
            "interval": 0,
            "until": "",
        })
    return actions


def install(cfg: dict) -> str:
    """Create/replace the scheduled task. Returns the task name.

    Uses ``New-ScheduledTaskAction -Execute/-Argument`` and
    ``Register-ScheduledTask`` inside a PowerShell script file. Going through
    ``schtasks /TR`` is avoided on purpose: schtasks re-splits the action
    string, which corrupts paths containing spaces.
    """
    from datetime import datetime

    name = cfg["task_name"]
    cmd = cfg["command"] or default_command()
    t = cfg["trigger"]

    def hhmm(value: str) -> str:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")

    def duration() -> str:
        start = datetime.strptime(hhmm(t["time"]), "%H:%M")
        end = datetime.strptime(hhmm(t["until"]), "%H:%M")
        total = ((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)) % (24 * 60)
        if total == 0:
            total = 24 * 60
        return f"{total // 60}:{total % 60:02d}"

    actions = build_actions(cfg)
    lines = [
        "$ErrorActionPreference='Stop'",
        f"$exe = {_ps_quote(cmd)}",
        f"$arg = {_ps_quote(cfg['arguments'])}",
        "$action = New-ScheduledTaskAction -Execute $exe -Argument $arg",
        "$triggers = @()",
    ]
    for a in actions:
        days = a["weekday"]  # build_actions already emits full day names
        lines.append(
            f"$triggers += New-ScheduledTaskTrigger -Weekly -DaysOfWeek {days} "
            f"-At '{a['time']}'")
        if a["interval"]:
            lines.append(
                "($triggers[-1]).Repetition = (New-ScheduledTaskTrigger -Once "
                f"-At '{a['time']}' "
                f"-RepetitionInterval (New-TimeSpan -Minutes {a['interval']}) "
                f"-RepetitionDuration (New-TimeSpan -Hours {int(duration().split(':')[0])} "
                f"-Minutes {int(duration().split(':')[1])})).Repetition")
    lines += [
        "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable "
        "-DontStopIfGoingOnBatteries -AllowStartIfOnBatteries "
        "-MultipleInstances IgnoreNew",
        "$principal = New-ScheduledTaskPrincipal -UserId \"$env:USERNAME\" "
        "-LogonType Interactive",
        f"Register-ScheduledTask -TaskName {_ps_quote(name)} -Action $action "
        "-Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null",
        "Write-Output 'installed'",
    ]
    code, out = _run_ps("\n".join(lines))
    if "installed" not in out:
        raise RuntimeError(f"Register-ScheduledTask failed ({code}):\n{out}")
    return name


def uninstall(cfg: dict) -> bool:
    names = [cfg["task_name"], cfg["task_name"] + "_other_days"]
    quoted = ", ".join(_ps_quote(n) for n in names)
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"foreach ($n in @({quoted})) {{"
        "  schtasks.exe /Delete /TN $n /F | Out-Null"
        "}"
        "Write-Output 'removed'"
    )
    code, out = _run_ps(script)
    if "removed" not in out:
        raise RuntimeError(f"schtasks /Delete failed ({code}):\n{out}")
    return True


def status(cfg: dict) -> dict:
    name = cfg["task_name"]
    names = [name, name + "_other_days"]
    quoted = ", ".join(_ps_quote(n) for n in names)
    found = {}
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"foreach ($n in @({quoted})) {{"
        "  $t = Get-ScheduledTask -TaskName $n;"
        "  if (-not $t) { continue }"
        "  $i = Get-ScheduledTaskInfo -TaskName $n;"
        "  Write-Output ('FOUND=' + $n);"
        "  Write-Output ('STATE=' + $t.State);"
        "  Write-Output ('LASTRUN=' + $i.LastRunTime);"
        "  Write-Output ('LASTRESULT=' + $i.LastTaskResult);"
        "  Write-Output ('NEXTRUN=' + $i.NextRunTime);"
        "}"
    )
    code, out = _run_ps(script)
    for line in (out or "").splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key == "FOUND":
            found["installed"] = True
            found["state"] = "Ready"
            found["tasks"] = found.get("tasks", []) + [value]
        elif key == "STATE":
            found["state"] = value
        elif key == "LASTRUN":
            found["last_run"] = value
        elif key == "LASTRESULT":
            found["last_result"] = value
        elif key == "NEXTRUN":
            found["next_run"] = value
    return found or {"installed": False, "state": "missing"}
