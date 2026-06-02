"""Main CustomTkinter application — Gamechanger Rename Manager."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from io import BytesIO
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from gamechanger_rename_manager.config.settings import APP_NAME, AppSettings, load_settings, save_settings
from gamechanger_rename_manager.config.theme import (
    ACCENT,
    CARD_BG,
    CARD_BORDER,
    COLORS,
    HOVER_BG,
    SELECTED_BG,
    STATUS_COLORS,
)
from gamechanger_rename_manager.ui.badges import (
    populate_asset_badges,
    populate_search_result_badges,
    status_dot_color,
)
from gamechanger_rename_manager.services.asset_model import AssetRecord
from gamechanger_rename_manager.services.iconik_client import IconikClient, enrich_assets
from gamechanger_rename_manager.services.integrity import analyze_assets
from gamechanger_rename_manager.services.s3_service import S3Service
from gamechanger_rename_manager.services.thumbnail_service import ThumbnailService
from gamechanger_rename_manager.services.variant import detect_variant
from gamechanger_rename_manager.ui.settings_dialog import SettingsDialog
from gamechanger_rename_manager.ui.tooltip import ToolTip
from gamechanger_rename_manager.workflows.rename_transaction import RenameTransactionEngine

logger = logging.getLogger(__name__)

WINDOW_SIZE = "1600x960"
MIN_SIZE = (1280, 760)
PREVIEW_MAX = (960, 540)



class RenameManagerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.filename_font = ctk.CTkFont(family="Menlo", size=14, weight="bold")
        self.meta_font = ctk.CTkFont(size=11)
        self.secondary_font = ctk.CTkFont(size=11)
        self.tertiary_font = ctk.CTkFont(family="Menlo", size=10)
        self.badge_font = ctk.CTkFont(size=10, weight="bold")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(APP_NAME)
        self.geometry(WINDOW_SIZE)
        self.minsize(*MIN_SIZE)
        self.configure(fg_color=COLORS["bg"])

        self._settings = load_settings()
        self._ui_queue: queue.Queue = queue.Queue()
        self._search_results: list[AssetRecord] = []
        self._filtered_results: list[AssetRecord] = []
        self._selected: AssetRecord | None = None
        self._selected_card: ctk.CTkFrame | None = None
        self.current_preview_image: ctk.CTkImage | None = None
        self._preview_placeholder_ctk: ctk.CTkImage | None = None
        self._thumb_pil: Image.Image | None = None
        self._thumb_pil_display: Image.Image | None = None
        self._preview_asset_id: str = ""
        self._preview_load_generation: int = 0
        self._preview_resize_after_id: str | None = None
        self._preview_render_generation: int = 0
        self._result_cards: dict[str, ctk.CTkFrame] = {}
        self._busy = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0, height=52)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        ctk.CTkLabel(
            header,
            text="Archive integrity · Iconik + S3 transactional rename",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=1, padx=8, sticky="w")
        ctk.CTkButton(
            header,
            text="Settings",
            width=100,
            fg_color=COLORS["panel_border"],
            command=self._open_settings,
        ).grid(row=0, column=2, padx=16, pady=8, sticky="e")

        # Resizable three-column layout (~38% / 34% / 28%)
        self._paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=10,
            sashrelief=tk.RAISED,
            opaqueresize=True,
            bg=COLORS["bg"],
            bd=0,
        )
        self._paned.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)

        self._left_host = tk.Frame(self._paned, bg=COLORS["panel"])
        self._center_host = tk.Frame(self._paned, bg=COLORS["panel"])
        self._right_host = tk.Frame(self._paned, bg=COLORS["panel"])

        init_w = 1600
        self._paned.add(self._left_host, minsize=520, width=int(init_w * 0.38))
        self._paned.add(self._center_host, minsize=420, width=int(init_w * 0.34))
        self._paned.add(self._right_host, minsize=340, width=int(init_w * 0.28))

        self._build_left_panel(self._left_host)
        self._build_center_panel(self._center_host)
        self._build_right_panel(self._right_host)
        self._build_bottom_console()

        self._set_rename_enabled(False)

    def _build_left_panel(self, host: tk.Frame) -> None:
        left = ctk.CTkFrame(host, fg_color=COLORS["panel"], corner_radius=10)
        left.pack(fill="both", expand=True)
        left.grid_rowconfigure(3, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left,
            text="Search",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        search_row = ctk.CTkFrame(left, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        search_row.grid_columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_row,
            textvariable=self.search_var,
            placeholder_text="Filename or Asset ID…",
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda _e: self._start_search())
        ctk.CTkButton(
            search_row,
            text="Search",
            width=80,
            fg_color=ACCENT,
            command=self._start_search,
        ).grid(row=0, column=1)

        filter_row = ctk.CTkFrame(left, fg_color="transparent")
        filter_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 4))
        filter_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(filter_row, text="Collection", font=self.badge_font, text_color=COLORS["text_muted"]).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.collection_filter_var = tk.StringVar(value="All collections")
        self.collection_filter = ctk.CTkComboBox(
            filter_row,
            variable=self.collection_filter_var,
            values=["All collections"],
            command=self._apply_collection_filter,
            width=280,
        )
        self.collection_filter.grid(row=0, column=1, sticky="ew")

        self.results_frame = ctk.CTkScrollableFrame(
            left,
            fg_color=COLORS["bg"],
            label_text="Results — click to select asset",
        )
        self.results_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=8)
        self.results_frame.grid_columnconfigure(0, weight=1)

        self.search_status = ctk.CTkLabel(
            left,
            text="No search yet",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        )
        self.search_status.grid(row=4, column=0, sticky="w", padx=12, pady=(0, 10))

    def _build_center_panel(self, host: tk.Frame) -> None:
        center = ctk.CTkFrame(host, fg_color=COLORS["panel"], corner_radius=10)
        center.pack(fill="both", expand=True)
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            center,
            text="Asset preview",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.preview_card = ctk.CTkFrame(center, fg_color=COLORS["bg"], corner_radius=12)
        self.preview_card.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        self.preview_card.grid_rowconfigure(0, weight=1)
        self.preview_card.grid_columnconfigure(0, weight=1)
        self.preview_card.bind("<Configure>", self._on_preview_resize)

        self.thumb_label = ctk.CTkLabel(
            self.preview_card,
            text="No asset selected",
            text_color=COLORS["text_muted"],
            font=ctk.CTkFont(size=13),
        )
        self.thumb_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self._init_preview_placeholder_image()

        self.preview_badge_row = ctk.CTkFrame(center, fg_color="transparent")
        self.preview_badge_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 0))

        self.preview_meta = ctk.CTkLabel(
            center,
            text="",
            font=self.meta_font,
            text_color=COLORS["text_muted"],
            wraplength=900,
            justify="left",
            anchor="w",
        )
        self.preview_meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(2, 4))

        self.detail_box = ctk.CTkTextbox(
            center,
            height=160,
            font=ctk.CTkFont(family="Menlo", size=12),
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
        )
        self.detail_box.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 16))
        self.detail_box.insert("1.0", "Select an asset from search results to view details.")
        self.detail_box.configure(state="disabled")

    def _build_right_panel(self, host: tk.Frame) -> None:
        right = ctk.CTkFrame(host, fg_color=COLORS["panel"], corner_radius=10)
        right.pack(fill="both", expand=True)
        right.grid_rowconfigure(9, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right,
            text="Rename planner",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        ctk.CTkLabel(right, text="New filename", anchor="w").grid(row=1, column=0, sticky="ew", padx=12)
        self.new_name_var = tk.StringVar()
        self.new_name_entry = ctk.CTkEntry(
            right,
            textvariable=self.new_name_var,
            placeholder_text="Select asset first…",
            state="disabled",
            font=self.filename_font,
        )
        self.new_name_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=4)

        opts = ctk.CTkFrame(right, fg_color="transparent")
        opts.grid(row=3, column=0, sticky="ew", padx=12, pady=4)
        self.dry_run_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts,
            text="Dry Run (no changes)",
            variable=self.dry_run_var,
            text_color=STATUS_COLORS["warning"],
        ).pack(side="left")

        ctk.CTkLabel(
            right,
            text="Integrity warnings",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=4, column=0, sticky="nw", padx=12, pady=(8, 0))

        self.warnings_badge_row = ctk.CTkFrame(right, fg_color="transparent")
        self.warnings_badge_row.grid(row=5, column=0, sticky="ew", padx=12, pady=(4, 0))

        self.warnings_box = ctk.CTkTextbox(
            right,
            height=100,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS["bg"],
            text_color=COLORS["text_muted"],
        )
        self.warnings_box.grid(row=6, column=0, sticky="ew", padx=12, pady=4)
        self.warnings_box.insert("1.0", "—")
        self.warnings_box.configure(state="disabled")

        ctk.CTkLabel(
            right,
            text="Transaction preview",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=7, column=0, sticky="nw", padx=12, pady=(8, 0))

        self.plan_badge_row = ctk.CTkFrame(right, fg_color="transparent")
        self.plan_badge_row.grid(row=8, column=0, sticky="ew", padx=12, pady=(4, 0))

        self.preview_box = ctk.CTkTextbox(
            right,
            font=ctk.CTkFont(family="Menlo", size=11),
            fg_color=COLORS["bg"],
            text_color=COLORS["text_muted"],
        )
        self.preview_box.grid(row=9, column=0, sticky="nsew", padx=12, pady=4)
        self.preview_box.insert("1.0", "Plan will appear after asset selection.")
        self.preview_box.configure(state="disabled")

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=10, column=0, sticky="ew", padx=12, pady=12)
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions,
            text="Refresh plan",
            fg_color=COLORS["panel_border"],
            command=self._refresh_plan,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.execute_btn = ctk.CTkButton(
            actions,
            text="Execute transaction",
            fg_color=ACCENT,
            command=self._execute_transaction,
        )
        self.execute_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.new_name_var.trace_add("write", lambda *_: self._refresh_plan())

    def _build_bottom_console(self) -> None:
        bottom = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=10)
        bottom.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        bottom.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bottom,
            text="Live log",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))

        self.console = ctk.CTkTextbox(
            bottom,
            height=150,
            font=ctk.CTkFont(family="Menlo", size=11),
            fg_color=COLORS["console_bg"],
            text_color=COLORS["text"],
            wrap="word",
        )
        self.console.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        self.console.insert("1.0", f"{APP_NAME} ready.\n")
        self.console.configure(state="disabled")

        self.progress = ctk.CTkProgressBar(bottom, mode="indeterminate", progress_color=ACCENT)
        self.progress.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.progress.grid_remove()

    def _log(self, msg: str) -> None:
        self.console.configure(state="normal")
        self.console.insert("end", msg + "\n")
        self.console.see("end")
        self.console.configure(state="disabled")

    def _preview_log(self, msg: str) -> None:
        self._log(f"[preview] {msg}")

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._ui_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "search_done":
                    self._on_search_done(item[1], item[2])
                elif kind == "thumb":
                    # Queue carries JPEG bytes only — never CTkImage (main-thread only).
                    self._on_thumbnail_bytes_ready(item[1], item[2], item[3], item[4])
                elif kind == "transaction_done":
                    self._on_transaction_done(item[1])
                elif kind == "busy":
                    self._set_busy(item[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.progress.grid()
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _open_settings(self) -> None:
        SettingsDialog(self, self._settings, self._on_settings_saved)

    def _on_settings_saved(self, settings: AppSettings) -> None:
        self._settings = settings
        self._log("Settings saved.")

    def _start_search(self) -> None:
        q = self.search_var.get().strip()
        if not q:
            messagebox.showwarning(APP_NAME, "Enter a filename or asset ID to search.")
            return
        if not self._settings.iconik_base_url or not self._settings.iconik_app_id:
            messagebox.showwarning(APP_NAME, "Configure Iconik credentials in Settings first.")
            return
        self._log(f"Searching Iconik: {q!r}")
        self._set_busy(True)
        self.search_status.configure(text="Searching…")

        def worker() -> None:
            try:
                client = IconikClient(self._settings)

                def log_fn(msg: str) -> None:
                    self._ui_queue.put(("log", msg))

                hits, err = client.search(q, log=logger)
                if err:
                    self._ui_queue.put(("search_done", [], err))
                    return
                log_fn(f"Search API returned {len(hits)} hit(s)")
                assets, excluded_deleted = enrich_assets(client, hits, log=logger)
                if excluded_deleted:
                    log_fn(
                        f"Excluded {excluded_deleted} soft-deleted asset(s) from operational results"
                    )
                for a in assets:
                    v = detect_variant(a.display_filename)
                    log_fn(f"Variant {a.asset_id}: {v.value} file={a.display_filename}")
                s3 = S3Service(self._settings) if self._settings.s3_bucket else None
                analyze_assets(assets, s3)
                self._ui_queue.put(("search_done", assets, None))
            except Exception as exc:
                logger.exception("Search failed")
                self._ui_queue.put(("search_done", [], str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_done(self, assets: list[AssetRecord], err: str | None) -> None:
        self._set_busy(False)
        self._search_results = assets
        self._selected = None
        self._selected_card = None
        self._set_rename_enabled(False)
        self._update_collection_filter_options(assets)

        if err:
            self.search_status.configure(text=f"Error: {err}")
            self._log(f"Search error: {err}")
            self._clear_results_ui()
            for frame in (self.preview_badge_row, self.warnings_badge_row, self.plan_badge_row):
                for child in frame.winfo_children():
                    child.destroy()
            return

        self._apply_collection_filter()
        self._log(f"Search returned {len(assets)} asset(s). Select one to continue.")

    def _update_collection_filter_options(self, assets: list[AssetRecord]) -> None:
        paths: set[str] = set()
        for a in assets:
            for p in a.collection_paths:
                if p:
                    paths.add(p)
            if a.collection_breadcrumb:
                paths.add(a.collection_breadcrumb)
        options = ["All collections"] + sorted(paths)
        self.collection_filter.configure(values=options)
        self.collection_filter_var.set("All collections")

    def _apply_collection_filter(self, _choice: str | None = None) -> None:
        filt = self.collection_filter_var.get()
        if filt == "All collections":
            self._filtered_results = list(self._search_results)
        else:
            self._filtered_results = [
                a
                for a in self._search_results
                if filt in a.collection_paths or a.collection_breadcrumb == filt
            ]
        self._clear_results_ui()
        self.search_status.configure(
            text=f"{len(self._filtered_results)} shown / {len(self._search_results)} total"
        )
        for i, asset in enumerate(self._filtered_results):
            self._add_result_card(asset, i)

    def _clear_results_ui(self) -> None:
        for child in self.results_frame.winfo_children():
            child.destroy()
        self._result_cards.clear()

    def _add_result_card(self, asset: AssetRecord, row: int) -> None:
        fn = asset.display_filename or "—"
        card = ctk.CTkFrame(
            self.results_frame,
            fg_color=CARD_BG,
            corner_radius=10,
            border_width=2,
            border_color=CARD_BORDER,
        )
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)
        self._result_cards[asset.asset_id] = card

        ctk.CTkFrame(
            card,
            fg_color=status_dot_color(asset.integrity_status),
            width=4,
            corner_radius=4,
        ).grid(row=0, column=0, rowspan=7, sticky="ns", padx=(10, 6), pady=12)

        # 1. Filename (primary)
        fn_label = ctk.CTkLabel(
            card,
            text=fn,
            font=self.filename_font,
            anchor="w",
            justify="left",
            text_color=COLORS["text"],
        )
        fn_label.grid(row=0, column=1, sticky="ew", padx=6, pady=(12, 6))
        ToolTip(fn_label, fn)

        # 2. Variant + 3. Duplication warning
        badge_row = ctk.CTkFrame(card, fg_color="transparent")
        badge_row.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 6))
        populate_search_result_badges(badge_row, asset)

        # 4. Collection breadcrumb
        crumb = asset.collection_breadcrumb or "(no collection path)"
        ctk.CTkLabel(
            card,
            text=crumb,
            font=self.secondary_font,
            text_color=COLORS["text_muted"],
            anchor="w",
            wraplength=520,
            justify="left",
        ).grid(row=2, column=1, sticky="w", padx=6, pady=(0, 2))

        # 5. Asset ID
        id_label = ctk.CTkLabel(
            card,
            text=f"ID: {asset.asset_id}",
            font=self.secondary_font,
            anchor="w",
            text_color=COLORS["text_muted"],
        )
        id_label.grid(row=3, column=1, sticky="w", padx=6, pady=2)
        ToolTip(id_label, asset.asset_id)

        # 6. Duration / metadata
        title_label = ctk.CTkLabel(
            card,
            text=f"Title: {asset.title or '—'}",
            font=self.tertiary_font,
            anchor="w",
            text_color=COLORS["text_muted"],
        )
        title_label.grid(row=4, column=1, sticky="w", padx=6, pady=2)

        dur = f"{asset.duration_sec:.1f}s" if asset.duration_sec else "—"
        dur_label = ctk.CTkLabel(
            card,
            text=f"Duration: {dur}",
            font=self.tertiary_font,
            anchor="w",
            text_color=COLORS["text_muted"],
        )
        dur_label.grid(row=5, column=1, sticky="w", padx=6, pady=2)

        path_line = asset.storage_path or asset.s3_key or "—"
        path_label = ctk.CTkLabel(
            card,
            text=path_line,
            font=self.tertiary_font,
            anchor="w",
            text_color=COLORS["text_muted"],
        )
        path_label.grid(row=6, column=1, sticky="w", padx=6, pady=(2, 12))
        ToolTip(path_label, path_line)

        def select(_e=None, a=asset, c=card) -> None:
            self._select_asset(a, c)

        def on_enter(_e=None, c=card) -> None:
            if c is not self._selected_card:
                c.configure(fg_color=HOVER_BG)

        def on_leave(_e=None, c=card) -> None:
            if c is not self._selected_card:
                c.configure(fg_color=CARD_BG)

        bind_widgets = (card, fn_label, id_label, title_label, dur_label, path_label, badge_row)
        for w in bind_widgets:
            w.bind("<Button-1>", select)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
        for child in badge_row.winfo_children():
            child.bind("<Button-1>", select)

    def _select_asset(self, asset: AssetRecord, card: ctk.CTkFrame) -> None:
        if self._selected_card:
            self._selected_card.configure(fg_color=CARD_BG, border_color=CARD_BORDER)
        self._selected = asset
        self._selected_card = card
        card.configure(fg_color=SELECTED_BG, border_color=ACCENT)

        self._preview_load_generation += 1
        self._preview_asset_id = asset.asset_id
        self._preview_log(f"asset selected: {asset.asset_id} ({asset.display_filename})")
        self._set_preview_loading()

        self._log(f"Selected asset {asset.asset_id} — {asset.display_filename}")
        self._set_rename_enabled(True)
        self.new_name_var.set(asset.display_filename)
        self._update_details(asset)
        self._update_warnings(asset)
        self._update_badge_summaries(asset)
        self._refresh_plan()
        self._update_preview_meta(asset)
        self._load_thumbnail_async(asset, self._preview_load_generation)

    def _update_preview_meta(self, asset: AssetRecord) -> None:
        populate_asset_badges(self.preview_badge_row, asset, selected=True)
        dur = f"{asset.duration_sec:.1f}s" if asset.duration_sec else "—"
        self.preview_meta.configure(
            text=(
                f"{asset.display_filename}\n"
                f"{asset.collection_breadcrumb or '—'}\n"
                f"Title: {asset.title or '—'}   ·   Duration: {dur}"
            )
        )

    def _update_badge_summaries(self, asset: AssetRecord) -> None:
        populate_asset_badges(self.warnings_badge_row, asset, selected=False)
        populate_asset_badges(self.plan_badge_row, asset, selected=False)

    def _set_rename_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.new_name_entry.configure(state=state)
        self.execute_btn.configure(state=state)

    def _update_details(self, asset: AssetRecord) -> None:
        dur = f"{asset.duration_sec:.2f}s" if asset.duration_sec else "—"
        crumbs = "\n  ".join(asset.collection_paths) if asset.collection_paths else asset.collection_breadcrumb or "—"
        text = (
            f"Filename:     {asset.display_filename}\n"
            f"Asset ID:     {asset.asset_id}\n"
            f"Title:        {asset.title}\n"
            f"File set:     {asset.file_set_name}\n"
            f"File set ID:  {asset.fileset_id}\n"
            f"Duration:     {dur}\n"
            f"Variant:      {asset.variant.value}\n"
            f"Collection:   {crumbs}\n"
            f"Storage:      {asset.storage_path or '—'}\n"
            f"S3 key:       {asset.s3_key or '—'}\n"
            f"Integrity:    {asset.integrity_status.value}\n"
            f"Thumbnail:    {asset.thumbnail_url or '(none in metadata)'}\n"
        )
        self.detail_box.configure(state="normal")
        self.detail_box.delete("1.0", "end")
        self.detail_box.insert("1.0", text)
        self.detail_box.configure(state="disabled")

    def _update_warnings(self, asset: AssetRecord) -> None:
        lines = []
        for i in asset.integrity_issues:
            tag = i.level.value.upper()
            lines.append(f"[{tag}] {i.message}")
        if not lines:
            lines = ["No integrity warnings."]
        self.warnings_box.configure(state="normal")
        self.warnings_box.delete("1.0", "end")
        self.warnings_box.insert("1.0", "\n".join(lines))
        self.warnings_box.configure(state="disabled")

    def _refresh_plan(self) -> None:
        if not self._selected:
            return
        populate_asset_badges(self.plan_badge_row, self._selected, selected=False)
        new_name = self.new_name_var.get().strip()
        engine = RenameTransactionEngine(self._settings)
        plan = engine.build_plan(self._selected, new_name)
        lines = [f"{op.phase}: {op.description}" for op in plan.operations]
        if plan.warnings:
            lines.append("")
            lines.append("Plan warnings:")
            for w in plan.warnings:
                lines.append(f"  [{w.level.value}] {w.message}")
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", "\n".join(lines) or "(empty plan)")
        self.preview_box.configure(state="disabled")

    def _init_preview_placeholder_image(self) -> None:
        """Single placeholder CTkImage created on main thread (never use image=None)."""
        ph = Image.new("RGB", (2, 2), color=(22, 27, 34))
        self._preview_placeholder_ctk = ctk.CTkImage(
            light_image=ph,
            dark_image=ph,
            size=(2, 2),
        )

    def _clear_preview_image_refs(self, *, message: str = "Loading preview…") -> None:
        """Safely drop Tk image refs before assigning a new preview."""
        self.current_preview_image = None
        self._thumb_pil = None
        self._thumb_pil_display = None
        if self._preview_placeholder_ctk is not None:
            self.thumb_label.configure(image=self._preview_placeholder_ctk, text=message)
            self.thumb_label.image = self._preview_placeholder_ctk
        else:
            self.thumb_label.configure(text=message)

    def _set_preview_loading(self) -> None:
        self._clear_preview_image_refs(message="Loading preview…")

    def _load_thumbnail_async(self, asset: AssetRecord, generation: int) -> None:
        aid = asset.asset_id

        def worker() -> None:
            client = IconikClient(self._settings)

            def log_fn(msg: str) -> None:
                self._ui_queue.put(("log", f"[thumb] {msg}"))

            svc = ThumbnailService(self._settings, iconik=client)
            img, source = svc.load_for_asset(asset, max_size=PREVIEW_MAX, log=log_fn)
            if img is None:
                self._ui_queue.put(("log", "[preview] worker: no image returned"))
                return
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=88)
            # JPEG bytes only — CTkImage is created on main thread in _render_preview_image().
            self._ui_queue.put(("thumb", buf.getvalue(), source, aid, generation))

        threading.Thread(target=worker, daemon=True, name=f"thumb-{aid}").start()

    def _on_thumbnail_bytes_ready(
        self,
        jpeg_bytes: bytes,
        source: str,
        asset_id: str,
        generation: int,
    ) -> None:
        """Main-thread handler: decode PIL from bytes, then schedule CTkImage render."""
        if generation != self._preview_load_generation:
            self._preview_log(f"stale image ignored (gen {generation})")
            return
        if asset_id != self._preview_asset_id:
            self._preview_log(f"stale image ignored (asset {asset_id})")
            return
        try:
            pil = Image.open(BytesIO(jpeg_bytes)).convert("RGB")
        except OSError as exc:
            self._preview_log(f"image decode failed: {exc}")
            self._clear_preview_image_refs(message="Preview unavailable")
            return

        self._thumb_pil = pil
        self._preview_log(f"image loaded ({source}) {pil.width}x{pil.height}")
        self._schedule_preview_render(generation)

    def _schedule_preview_render(self, generation: int) -> None:
        """Ensure CTkImage creation runs on the main UI thread event loop."""
        self._preview_render_generation = generation
        self.after(0, lambda g=generation: self._render_preview_image(g))

    def _render_preview_image(self, generation: int | None = None) -> None:
        """Create a fresh CTkImage on the main thread and assign to the preview label."""
        if generation is not None and generation != self._preview_load_generation:
            return
        if not self._thumb_pil:
            return

        self.preview_card.update_idletasks()
        card_w = self.preview_card.winfo_width()
        card_h = self.preview_card.winfo_height()
        if card_w > 1 and card_h > 1:
            w = max(card_w - 32, 400)
            h = max(card_h - 32, 300)
        else:
            w, h = PREVIEW_MAX

        self._thumb_pil_display = self._thumb_pil.copy()
        self._thumb_pil_display.thumbnail((w, h), Image.Resampling.LANCZOS)

        # Release previous CTkImage before creating a new one (avoids stale pyimage refs).
        self.current_preview_image = None
        self.thumb_label.image = self._preview_placeholder_ctk

        new_ctk = ctk.CTkImage(
            light_image=self._thumb_pil_display,
            dark_image=self._thumb_pil_display,
            size=(self._thumb_pil_display.width, self._thumb_pil_display.height),
        )
        self.current_preview_image = new_ctk
        self.thumb_label.configure(image=self.current_preview_image, text="")
        self.thumb_label.image = self.current_preview_image
        self._preview_log(
            f"image rendered {self._thumb_pil_display.width}x{self._thumb_pil_display.height}"
        )
        self._preview_log("preview refresh complete")

    def _on_preview_resize(self, _event=None) -> None:
        if not self._thumb_pil:
            return
        if self._preview_resize_after_id:
            self.after_cancel(self._preview_resize_after_id)
        self._preview_resize_after_id = self.after(120, self._debounced_preview_resize)

    def _debounced_preview_resize(self) -> None:
        self._preview_resize_after_id = None
        if self._thumb_pil and self._preview_asset_id:
            self._schedule_preview_render(self._preview_load_generation)

    def _execute_transaction(self) -> None:
        if not self._selected:
            messagebox.showwarning(APP_NAME, "Select an asset from search results first.")
            return
        new_name = self.new_name_var.get().strip()
        if not new_name:
            messagebox.showwarning(APP_NAME, "Enter a new filename.")
            return
        dry = self.dry_run_var.get()
        if not dry:
            if not messagebox.askyesno(
                APP_NAME,
                "Dry Run is OFF. This will modify S3 and Iconik.\n\nProceed?",
            ):
                return

        asset = self._selected
        self._log(f"{'Dry-run' if dry else 'Executing'} transaction for {asset.asset_id}")
        self._set_busy(True)

        def worker() -> None:
            def log_fn(m: str) -> None:
                self._ui_queue.put(("log", m))

            try:
                engine = RenameTransactionEngine(self._settings)
                result = engine.execute(asset, new_name, dry_run=dry, log=log_fn)
                self._ui_queue.put(("transaction_done", result))
            except Exception as exc:
                logger.exception("Transaction error")
                self._ui_queue.put(("log", f"Transaction exception: {exc}"))
                self._ui_queue.put(("busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_transaction_done(self, result) -> None:
        self._set_busy(False)
        if result.success:
            self._log(result.message)
            if not result.dry_run and self._selected:
                self._selected.file_set_name = result.plan.new_filename
                self._update_details(self._selected)
                self._update_preview_meta(self._selected)
        else:
            self._log(f"FAILED: {result.message}")
            messagebox.showerror(APP_NAME, result.message)

    def _on_close(self) -> None:
        save_settings(self._settings)
        self.destroy()


def run_app() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = RenameManagerApp()
    app.mainloop()
