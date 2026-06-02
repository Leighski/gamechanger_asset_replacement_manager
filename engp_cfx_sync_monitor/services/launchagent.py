"""LaunchAgent status via launchctl."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass

from engp_cfx_sync_monitor import config

logger = logging.getLogger(__name__)

_PID_RE = re.compile(r'"PID"\s*=\s*(\d+)', re.I)
_STATE_RE = re.compile(r'state\s*=\s*(\w+)', re.I)
_LAST_EXIT_RE = re.compile(r'last exit (?:code|status)\s*=\s*(-?\d+)', re.I)


@dataclass(frozen=True)
class LaunchAgentStatus:
    label: str
    loaded: bool
    running: bool
    pid: int | None
    state: str
    last_exit_code: int | None
    detail: str

    @property
    def status_text(self) -> str:
        if not self.loaded:
            return "Not loaded"
        if self.running:
            return f"Running (PID {self.pid})" if self.pid else "Running"
        if self.state and self.state.lower() not in ("not running", "unknown"):
            return self.state
        return "Loaded (idle)"


def _uid() -> int:
    import os

    return os.getuid()


def _domain_target() -> str:
    return f"gui/{_uid()}"


def get_launchagent_status() -> LaunchAgentStatus:
    label = config.LAUNCH_AGENT_LABEL
    target = f"{_domain_target()}/{label}"

    try:
        proc = subprocess.run(
            ["launchctl", "print", target],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        logger.error("launchctl not found")
        return LaunchAgentStatus(
            label=label,
            loaded=False,
            running=False,
            pid=None,
            state="unknown",
            last_exit_code=None,
            detail="launchctl not available",
        )
    except subprocess.TimeoutExpired:
        return LaunchAgentStatus(
            label=label,
            loaded=False,
            running=False,
            pid=None,
            state="unknown",
            last_exit_code=None,
            detail="launchctl timed out",
        )

    if proc.returncode != 0:
        # Fallback: list grep
        listed = _check_list(label)
        if listed:
            return listed
        err = (proc.stderr or proc.stdout or "").strip()[:200]
        return LaunchAgentStatus(
            label=label,
            loaded=False,
            running=False,
            pid=None,
            state="not loaded",
            last_exit_code=None,
            detail=err or "Agent not loaded",
        )

    text = proc.stdout or ""
    pid = None
    m = _PID_RE.search(text)
    if m:
        pid = int(m.group(1))

    state = "unknown"
    sm = _STATE_RE.search(text)
    if sm:
        state = sm.group(1)

    last_exit = None
    em = _LAST_EXIT_RE.search(text)
    if em:
        last_exit = int(em.group(1))

    running = pid is not None and pid > 0
    if not running and state.lower() in ("running", "active"):
        running = True

    return LaunchAgentStatus(
        label=label,
        loaded=True,
        running=running,
        pid=pid if pid and pid > 0 else None,
        state=state,
        last_exit_code=last_exit,
        detail="OK",
    )


def _check_list(label: str) -> LaunchAgentStatus | None:
    try:
        proc = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if proc.returncode != 0:
        return None

    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == label:
            pid_str, status_str = parts[0], parts[1]
            try:
                pid = int(pid_str)
            except ValueError:
                pid = -1
            running = pid > 0
            last_exit = None
            if status_str not in ("-", "0") and status_str.lstrip("-").isdigit():
                last_exit = int(status_str)
            return LaunchAgentStatus(
                label=label,
                loaded=True,
                running=running,
                pid=pid if running else None,
                state="running" if running else "idle",
                last_exit_code=last_exit,
                detail="from launchctl list",
            )
    return None
