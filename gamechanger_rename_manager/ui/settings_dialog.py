"""Settings dialog for Iconik and AWS credentials."""

from __future__ import annotations

import customtkinter as ctk

from gamechanger_rename_manager.config.settings import AppSettings, save_settings
from gamechanger_rename_manager.config.theme import ACCENT, COLORS


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, settings: AppSettings, on_saved) -> None:
        super().__init__(master)
        self.title("Settings")
        self.geometry("560x620")
        self.transient(master)
        self.grab_set()

        self._settings = settings
        self._on_saved = on_saved
        self._vars: dict[str, ctk.StringVar] = {}
        self._bools: dict[str, ctk.BooleanVar] = {}

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["panel"])
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        self._section(scroll, "Iconik")
        for label, key in [
            ("Base URL", "iconik_base_url"),
            ("App ID", "iconik_app_id"),
            ("Auth Token", "iconik_auth_token"),
            ("Collection UUID", "iconik_collection_uuid"),
        ]:
            self._row(scroll, label, key, secret=key == "iconik_auth_token")

        self._section(scroll, "AWS S3")
        for label, key in [
            ("Access Key ID", "aws_access_key_id"),
            ("Secret Access Key", "aws_secret_access_key"),
            ("Session Token (optional)", "aws_session_token"),
            ("Region", "aws_region"),
            ("S3 Bucket", "s3_bucket"),
            ("S3 Prefix", "s3_prefix"),
            ("Backup Prefix", "s3_backup_prefix"),
        ]:
            self._row(scroll, label, key, secret="secret" in key.lower())

        self._bools["enable_s3_backup"] = ctk.BooleanVar(value=settings.enable_s3_backup)
        ctk.CTkCheckBox(
            scroll,
            text="Enable S3 backup before rename (Phase 1)",
            variable=self._bools["enable_s3_backup"],
        ).pack(anchor="w", padx=8, pady=4)

        self._section(scroll, "Media tools")
        for label, key in [
            ("ffmpeg path", "ffmpeg_path"),
            ("ffprobe path", "ffprobe_path"),
            ("Audit log directory", "audit_log_dir"),
            ("Thumbnail cache directory", "thumbnail_cache_dir"),
        ]:
            self._row(scroll, label, key)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(btn_row, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_row,
            text="Save",
            fg_color=ACCENT,
            command=self._save,
        ).pack(side="right", padx=4)

    def _section(self, parent, title: str) -> None:
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=8, pady=(12, 4))

    def _row(self, parent, label: str, key: str, *, secret: bool = False) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(frame, text=label, width=160, anchor="w").pack(side="left")
        var = ctk.StringVar(value=str(getattr(self._settings, key, "")))
        self._vars[key] = var
        entry = ctk.CTkEntry(frame, textvariable=var, width=320, show="•" if secret else "")
        entry.pack(side="left", fill="x", expand=True)

    def _save(self) -> None:
        for key, var in self._vars.items():
            setattr(self._settings, key, var.get().strip())
        self._settings.enable_s3_backup = bool(self._bools["enable_s3_backup"].get())
        save_settings(self._settings)
        self._on_saved(self._settings)
        self.destroy()
