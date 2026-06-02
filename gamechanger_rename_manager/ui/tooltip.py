"""Simple hover tooltip for Tk/CTk widgets."""

from __future__ import annotations

import tkinter as tk


class ToolTip:
    def __init__(self, widget: tk.Misc, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self._text = text

    def _show(self, _event=None) -> None:
        if not self._text or self._tip:
            return
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self._text,
            justify="left",
            background="#21262d",
            foreground="#e6edf3",
            relief="solid",
            borderwidth=1,
            font=("Menlo", 11),
            padx=8,
            pady=6,
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self._tip:
            self._tip.destroy()
            self._tip = None
