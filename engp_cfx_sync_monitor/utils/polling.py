"""Thread-safe background poller with main-thread callbacks."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

from engp_cfx_sync_monitor import config
from engp_cfx_sync_monitor.services.launchagent import LaunchAgentStatus, get_launchagent_status
from engp_cfx_sync_monitor.services.logs_parser import LogSnapshot, read_log_snapshot
from engp_cfx_sync_monitor.services.nas_check import check_nas_mount
from engp_cfx_sync_monitor.services.s3_check import check_s3_connectivity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorSnapshot:
    launchagent: LaunchAgentStatus
    logs: LogSnapshot
    nas_ok: bool
    nas_message: str
    s3_ok: bool
    s3_message: str
    polled_at: float


def collect_snapshot() -> MonitorSnapshot:
    la = get_launchagent_status()
    logs = read_log_snapshot()
    nas_ok, nas_msg = check_nas_mount()
    s3_ok, s3_msg = check_s3_connectivity()
    return MonitorSnapshot(
        launchagent=la,
        logs=logs,
        nas_ok=nas_ok,
        nas_message=nas_msg,
        s3_ok=s3_ok,
        s3_message=s3_msg,
        polled_at=time.time(),
    )


class BackgroundPoller:
    """Polls status on a daemon thread; delivers results via callback on caller thread."""

    def __init__(
        self,
        on_snapshot: Callable[[MonitorSnapshot], None],
        *,
        interval_sec: float | None = None,
    ) -> None:
        self._on_snapshot = on_snapshot
        self._interval = interval_sec or config.POLL_INTERVAL_SEC
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._busy = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="engp-cfx-poller",
            daemon=True,
        )
        self._thread.start()
        logger.info("Background poller started (interval=%ss)", self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._interval + 2)
        logger.info("Background poller stopped")

    def poll_now_async(self) -> None:
        """Trigger an immediate poll without waiting for the interval."""
        threading.Thread(
            target=self._single_poll,
            name="engp-cfx-poll-now",
            daemon=True,
        ).start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._single_poll()
            self._stop.wait(self._interval)

    def _single_poll(self) -> None:
        with self._lock:
            if self._busy:
                return
            self._busy = True
        try:
            snapshot = collect_snapshot()
            self._on_snapshot(snapshot)
        except Exception:
            logger.exception("Poll failed")
        finally:
            with self._lock:
                self._busy = False
