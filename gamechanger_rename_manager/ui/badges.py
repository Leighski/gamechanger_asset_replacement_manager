"""Reusable pill badges for variant, ID, and integrity status."""

from __future__ import annotations

import customtkinter as ctk

from gamechanger_rename_manager.config.theme import (
    ALERT_BADGE,
    PILL_HEIGHT,
    PILL_RADIUS,
    STATUS_COLORS,
    VARIANT_BADGE,
)
from gamechanger_rename_manager.services.asset_model import AssetRecord, IntegrityLevel


def _pill_font() -> ctk.CTkFont:
    return ctk.CTkFont(size=10, weight="bold")


def _auto_pill_width(text: str, *, min_width: int = 44) -> int:
    """Estimate pill width from label length (avoids truncation on long operator labels)."""
    stripped = text.strip()
    return max(min_width, int(len(stripped) * 6.8) + 22)


def create_pill(
    parent: ctk.CTkBaseClass,
    text: str,
    *,
    bg: str,
    fg: str,
    border: str | None = None,
    width: int | None = None,
    min_width: int = 44,
) -> ctk.CTkLabel:
    label_text = f" {text.strip()} "
    pill_width = width if width is not None else _auto_pill_width(label_text, min_width=min_width)
    kwargs: dict = {
        "text": label_text,
        "font": _pill_font(),
        "fg_color": bg,
        "text_color": fg,
        "corner_radius": PILL_RADIUS,
        "height": PILL_HEIGHT,
        "width": pill_width,
    }
    return ctk.CTkLabel(parent, **kwargs)


def create_variant_pill(
    parent: ctk.CTkBaseClass,
    variant: str,
    *,
    selected: bool = False,
) -> ctk.CTkLabel:
    spec = VARIANT_BADGE.get(variant, VARIANT_BADGE["UNKNOWN"])
    border = spec["border"] if selected else None
    return create_pill(
        parent,
        spec["label"],
        bg=spec["bg"],
        fg=spec["fg"],
        border=border,
    )


def create_id_pill(parent: ctk.CTkBaseClass, asset_id: str) -> ctk.CTkLabel:
    short = asset_id if len(asset_id) <= 12 else f"{asset_id[:8]}…"
    return create_pill(
        parent,
        short,
        bg=STATUS_COLORS["info"],
        fg="#ffffff",
    )


def create_duplicate_pill(parent: ctk.CTkBaseClass) -> ctk.CTkLabel:
    spec = ALERT_BADGE["duplicate"]
    return create_pill(
        parent,
        spec["label"],
        bg=spec["bg"],
        fg=spec["fg"],
        min_width=120,
    )


def create_integrity_pill(parent: ctk.CTkBaseClass, level: IntegrityLevel) -> ctk.CTkLabel | None:
    if level == IntegrityLevel.ERROR:
        spec = ALERT_BADGE["critical"]
        return create_pill(parent, spec["label"], bg=spec["bg"], fg=spec["fg"])
    if level == IntegrityLevel.WARN:
        spec = ALERT_BADGE["warning"]
        return create_pill(parent, spec["label"], bg=spec["bg"], fg=spec["fg"])
    if level == IntegrityLevel.OK:
        return create_pill(
            parent,
            "OK",
            bg=STATUS_COLORS["success"],
            fg="#ffffff",
        )
    return None


def clear_frame(frame: ctk.CTkFrame) -> None:
    for child in frame.winfo_children():
        child.destroy()


def populate_asset_badges(
    frame: ctk.CTkFrame,
    asset: AssetRecord,
    *,
    selected: bool = False,
    show_dup: bool = True,
    show_integrity: bool = True,
    show_id: bool = True,
) -> None:
    """Compact badge bar for preview / planner headers (variant, optional ID, dup, integrity)."""
    clear_frame(frame)
    col = 0
    pill = create_variant_pill(frame, asset.variant.value, selected=selected)
    pill.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")
    col += 1

    if show_dup and asset.has_duplicate_filename:
        dup = create_duplicate_pill(frame)
        dup.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")
        col += 1

    if show_id:
        id_pill = create_id_pill(frame, asset.asset_id)
        id_pill.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")
        col += 1

    if show_integrity and asset.integrity_status != IntegrityLevel.OK:
        ip = create_integrity_pill(frame, asset.integrity_status)
        if ip:
            ip.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")


def populate_search_result_badges(
    frame: ctk.CTkFrame,
    asset: AssetRecord,
) -> None:
    """
    Search card badges: variant then duplication warning (operational priority).
    Asset ID is shown separately below collection breadcrumb.
    """
    clear_frame(frame)
    col = 0
    pill = create_variant_pill(frame, asset.variant.value, selected=False)
    pill.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")
    col += 1

    if asset.has_duplicate_filename:
        dup = create_duplicate_pill(frame)
        dup.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")
        col += 1

    if asset.integrity_status != IntegrityLevel.OK:
        ip = create_integrity_pill(frame, asset.integrity_status)
        if ip:
            ip.grid(row=0, column=col, padx=(0, 6), pady=2, sticky="w")


def status_dot_color(level: IntegrityLevel) -> str:
    return {
        IntegrityLevel.OK: STATUS_COLORS["success"],
        IntegrityLevel.WARN: STATUS_COLORS["warning"],
        IntegrityLevel.ERROR: STATUS_COLORS["critical"],
    }.get(level, STATUS_COLORS["muted"])
