"""Enterprise MAM dark theme tokens."""

from __future__ import annotations

ACCENT = "#1f6feb"
ACCENT_HOVER = "#388bfd"

COLORS = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "panel_border": "#30363d",
    "text": "#e6edf3",
    "text_muted": "#8b949e",
    "input_bg": "#0d1117",
    "console_bg": "#010409",
}

# Standardised operational status colours
STATUS_COLORS = {
    "info": "#1f6feb",
    "success": "#2ea043",
    "warning": "#d29922",
    "critical": "#da3633",
    "muted": "#6e7681",
    "pending": "#8b949e",
    # Legacy aliases used by integrity levels
    "ok": "#2ea043",
    "warn": "#d29922",
    "error": "#da3633",
}

# Variant pill badges — bg, fg (white), optional glow border when selected
VARIANT_BADGE: dict[str, dict[str, str]] = {
    "MAIN": {
        "label": "MAIN + COMS",
        "bg": "#1f6feb",
        "fg": "#ffffff",
        "border": "#58a6ff",
    },
    "CFX": {
        "label": "CLEANFX",
        "bg": "#8957e5",
        "fg": "#ffffff",
        "border": "#a371f7",
    },
    "MT": {
        "label": "MULTI-TRACK",
        "bg": "#238636",
        "fg": "#ffffff",
        "border": "#3fb950",
    },
    "UNKNOWN": {
        "label": "UNKNOWN",
        "bg": "#484f58",
        "fg": "#ffffff",
        "border": "#6e7681",
    },
}

ALERT_BADGE = {
    "duplicate": {
        "label": "⚠ DUPLICATION",
        "bg": "#d29922",
        "fg": "#0d1117",
    },
    "critical": {
        "label": "CRIT",
        "bg": "#da3633",
        "fg": "#ffffff",
    },
    "warning": {
        "label": "WARN",
        "bg": "#d29922",
        "fg": "#0d1117",
    },
}

PILL_RADIUS = 14
PILL_HEIGHT = 26

HOVER_BG = "#21262d"
SELECTED_BG = "#1c2d4a"
CARD_BG = "#161b22"
CARD_BORDER = "#30363d"
