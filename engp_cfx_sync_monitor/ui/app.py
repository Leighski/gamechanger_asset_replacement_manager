"""Main CustomTkinter application window."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable

import customtkinter as ctk

from engp_cfx_sync_monitor import config
from engp_cfx_sync_monitor.services.sync_actions import (
    open_logs_folder,
    restart_launchagent,
    run_manual_sync,
)
from engp_cfx_sync_monitor.utils.polling import BackgroundPoller, MonitorSnapshot

logger = logging.getLogger(__name__)

# Status colours
_CLR_OK = "#2ecc71"
_CLR_WARN = "#f39c12"
_CLR_ERR = "#e74c3c"
_CLR_MUTED = "#95a5a6"
_CLR_TEXT = "#ecf0f1"


class StatusCard(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, title: str, **kwargs) -> None:
        super().__init__(master, corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_CLR_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.value_label = ctk.CTkLabel(
            self,
            text="—",
            font=ctk.CTkFont(size=14),
            text_color=_CLR_TEXT,
            wraplength=240,
            justify="left",
        )
        self.value_label.grid(row=1, column=0, sticky="w", padx=12, pady=(4, 12))

    def set_value(self, text: str, *, color: str = _CLR_TEXT) -> None:
        self.value_label.configure(text=text, text_color=color)


class LogPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, title: str, **kwargs) -> None:
        super().__init__(master, corner_radius=8, **kwargs)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Menlo", size=11),
            wrap="none",
            activate_scrollbars=True,
        )
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.textbox.configure(state="disabled")

    def set_content(self, content: str) -> None:
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", content)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class SyncMonitorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(config.APP_TITLE)
        self.geometry(config.WINDOW_SIZE)
        self.minsize(*config.MIN_WINDOW_SIZE)

        self._poller = BackgroundPoller(self._on_snapshot_thread)
        self._action_running = False
        self._last_snapshot: MonitorSnapshot | None = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._poller.start()
        self._set_status_bar("Starting…")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=config.APP_TITLE,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.refresh_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=_CLR_MUTED,
        )
        self.refresh_label.grid(row=0, column=1, sticky="e")

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        for i in range(5):
            cards.grid_columnconfigure(i, weight=1, uniform="cards")

        self.card_agent = StatusCard(cards, "LaunchAgent")
        self.card_agent.grid(row=0, column=0, sticky="nsew", padx=4)
        self.card_success = StatusCard(cards, "Last success")
        self.card_success.grid(row=0, column=1, sticky="nsew", padx=4)
        self.card_failure = StatusCard(cards, "Last failure")
        self.card_failure.grid(row=0, column=2, sticky="nsew", padx=4)
        self.card_nas = StatusCard(cards, "NAS mount")
        self.card_nas.grid(row=0, column=3, sticky="nsew", padx=4)
        self.card_s3 = StatusCard(cards, "AWS S3")
        self.card_s3.grid(row=0, column=4, sticky="nsew", padx=4)

        logs_frame = ctk.CTkFrame(self, fg_color="transparent")
        logs_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_columnconfigure(1, weight=1)
        logs_frame.grid_rowconfigure(0, weight=1)

        self.sync_log_panel = LogPanel(logs_frame, "Sync log")
        self.sync_log_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.error_log_panel = LogPanel(logs_frame, "Error log")
        self.error_log_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 8))
        actions.grid_columnconfigure(4, weight=1)

        self.btn_manual = ctk.CTkButton(
            actions, text="Manual sync", command=self._on_manual_sync, width=120
        )
        self.btn_manual.grid(row=0, column=0, padx=4)
        self.btn_restart = ctk.CTkButton(
            actions,
            text="Restart LaunchAgent",
            command=self._on_restart_agent,
            width=150,
        )
        self.btn_restart.grid(row=0, column=1, padx=4)
        self.btn_logs = ctk.CTkButton(
            actions, text="Open logs folder", command=self._on_open_logs, width=130
        )
        self.btn_logs.grid(row=0, column=2, padx=4)
        self.btn_refresh = ctk.CTkButton(
            actions,
            text="Refresh now",
            command=self._on_refresh_now,
            width=110,
            fg_color="#34495e",
        )
        self.btn_refresh.grid(row=0, column=3, padx=4)

        self.status_bar = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=_CLR_MUTED,
            anchor="w",
        )
        self.status_bar.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))

    def _on_snapshot_thread(self, snapshot: MonitorSnapshot) -> None:
        self.after(0, lambda: self._apply_snapshot(snapshot))

    def _apply_snapshot(self, snapshot: MonitorSnapshot) -> None:
        self._last_snapshot = snapshot
        la = snapshot.launchagent
        logs = snapshot.logs

        if la.running:
            agent_color = _CLR_OK
        elif la.loaded:
            agent_color = _CLR_WARN
        else:
            agent_color = _CLR_ERR
        self.card_agent.set_value(la.status_text, color=agent_color)

        self.card_success.set_value(
            logs.last_success or "—",
            color=_CLR_OK if logs.last_success else _CLR_MUTED,
        )
        self.card_failure.set_value(
            logs.last_failure or "—",
            color=_CLR_ERR if logs.last_failure else _CLR_MUTED,
        )
        self.card_nas.set_value(
            "OK" if snapshot.nas_ok else snapshot.nas_message[:80],
            color=_CLR_OK if snapshot.nas_ok else _CLR_ERR,
        )
        self.card_s3.set_value(
            "OK" if snapshot.s3_ok else snapshot.s3_message[:80],
            color=_CLR_OK if snapshot.s3_ok else _CLR_ERR,
        )

        self.sync_log_panel.set_content(logs.sync_tail)
        self.error_log_panel.set_content(logs.error_tail)

        ts = datetime.fromtimestamp(snapshot.polled_at).strftime("%H:%M:%S")
        self.refresh_label.configure(
            text=f"Updated {ts} · every {config.POLL_INTERVAL_SEC}s"
        )
        self._set_status_bar(
            f"{config.LAUNCH_AGENT_LABEL} · NAS: {config.NAS_PATH.name}"
        )

    def _set_status_bar(self, text: str) -> None:
        self.status_bar.configure(text=text)

    def _set_actions_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in (
            self.btn_manual,
            self.btn_restart,
            self.btn_logs,
            self.btn_refresh,
        ):
            btn.configure(state=state)

    def _run_action(
        self,
        label: str,
        worker: Callable[[], tuple[bool, str]],
        *,
        refresh_after: bool = True,
    ) -> None:
        if self._action_running:
            return
        self._action_running = True
        self._set_actions_enabled(False)
        self._set_status_bar(f"{label}…")

        def task() -> None:
            try:
                ok, message = worker()
            except Exception as exc:
                logger.exception("%s failed", label)
                ok, message = False, str(exc)

            def done() -> None:
                self._action_running = False
                self._set_actions_enabled(True)
                color = _CLR_OK if ok else _CLR_ERR
                self._set_status_bar(message[:500])
                self.status_bar.configure(text_color=color)
                if refresh_after:
                    self._poller.poll_now_async()

            self.after(0, done)

        threading.Thread(target=task, name=f"action-{label}", daemon=True).start()

    def _on_manual_sync(self) -> None:
        self._run_action("Manual sync", run_manual_sync)

    def _on_restart_agent(self) -> None:
        if not self._confirm(
            "Restart LaunchAgent?",
            f"This will restart {config.LAUNCH_AGENT_LABEL}.",
        ):
            return
        self._run_action("Restart LaunchAgent", restart_launchagent)

    def _on_open_logs(self) -> None:
        ok, msg = open_logs_folder()
        self._set_status_bar(msg)
        self.status_bar.configure(text_color=_CLR_OK if ok else _CLR_ERR)

    def _on_refresh_now(self) -> None:
        self._poller.poll_now_async()
        self._set_status_bar("Refreshing…")

    def _confirm(self, title: str, message: str) -> bool:
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x160")
        dialog.transient(self)
        dialog.grab_set()

        result = {"ok": False}

        ctk.CTkLabel(dialog, text=message, wraplength=360).pack(
            padx=20, pady=(24, 16)
        )

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=8)

        def yes() -> None:
            result["ok"] = True
            dialog.destroy()

        def no() -> None:
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="Cancel", command=no, width=90, fg_color="#555").pack(
            side="left", padx=8
        )
        ctk.CTkButton(btn_frame, text="Restart", command=yes, width=90).pack(
            side="left", padx=8
        )

        dialog.wait_window()
        return result["ok"]

    def _on_close(self) -> None:
        logger.info("Shutting down monitor")
        self._poller.stop()
        self.destroy()

    def run(self) -> None:
        self.mainloop()


def main() -> None:
    from engp_cfx_sync_monitor.utils.logging_setup import setup_logging

    setup_logging()
    logger.info("Launching %s", config.APP_TITLE)
    app = SyncMonitorApp()
    app.run()
