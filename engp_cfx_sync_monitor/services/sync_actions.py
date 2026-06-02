"""Manual sync, LaunchAgent restart, and folder open actions."""

from __future__ import annotations

import logging
import plistlib
import subprocess
import sys
from pathlib import Path

from engp_cfx_sync_monitor import config

logger = logging.getLogger(__name__)


def _uid() -> int:
    import os

    return os.getuid()


def _domain_target() -> str:
    return f"gui/{_uid()}"


def get_sync_command() -> list[str] | None:
    plist_path = config.LAUNCH_AGENT_PLIST
    if not plist_path.is_file():
        logger.warning("LaunchAgent plist not found: %s", plist_path)
        return None
    try:
        with plist_path.open("rb") as fh:
            data = plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException) as exc:
        logger.error("Failed to read plist: %s", exc)
        return None

    args = data.get("ProgramArguments")
    if isinstance(args, list) and args:
        return [str(a) for a in args]
    program = data.get("Program")
    if program:
        return [str(program)]
    return None


def run_manual_sync() -> tuple[bool, str]:
    cmd = get_sync_command()
    if not cmd:
        return False, (
            f"No sync command found. Ensure {config.LAUNCH_AGENT_PLIST} exists "
            "with ProgramArguments."
        )

    logger.info("Starting manual sync: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        return False, "Manual sync timed out after 1 hour"
    except OSError as exc:
        return False, str(exc)

    out = (proc.stdout or "")[-500:]
    err = (proc.stderr or "")[-500:]
    if proc.returncode == 0:
        msg = "Manual sync completed successfully."
        if out.strip():
            msg += f"\n{out.strip()}"
        return True, msg

    msg = f"Manual sync failed (exit {proc.returncode})."
    if err.strip():
        msg += f"\n{err.strip()}"
    elif out.strip():
        msg += f"\n{out.strip()}"
    return False, msg


def restart_launchagent() -> tuple[bool, str]:
    label = config.LAUNCH_AGENT_LABEL
    target = f"{_domain_target()}/{label}"
    plist = config.LAUNCH_AGENT_PLIST

    # Prefer kickstart if already loaded
    try:
        ks = subprocess.run(
            ["launchctl", "kickstart", "-k", target],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if ks.returncode == 0:
            logger.info("LaunchAgent kickstarted: %s", label)
            return True, f"Restarted {label} (kickstart)."
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("kickstart failed: %s", exc)

    # unload / load cycle
    if not plist.is_file():
        return False, f"Plist not found: {plist}"

    uid = _uid()
    domain = f"gui/{uid}"

    try:
        subprocess.run(
            ["launchctl", "bootout", domain, str(plist)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"bootout failed: {exc}"

    try:
        proc = subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "bootstrap failed").strip()
        return False, err[:400]

    logger.info("LaunchAgent reloaded: %s", label)
    return True, f"Reloaded {label} from plist."


def open_logs_folder() -> tuple[bool, str]:
    folder = config.LOGS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = str(folder.resolve())

    if sys.platform == "darwin":
        try:
            subprocess.run(["open", path], check=True, timeout=10)
            return True, f"Opened {path}"
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)

    return False, f"Open folder not supported on {sys.platform}; path: {path}"
