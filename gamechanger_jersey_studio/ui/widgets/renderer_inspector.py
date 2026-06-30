"""Renderer Inspector — developer view for live render diagnostics."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from models.renderer import RenderLayerId, RenderStats
from ui.theme import Theme
from ui.typography import Typography


class RendererInspector(QFrame):
    """Show active layers, timings, cache stats, and memory usage."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panelElevated")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD)
        layout.setSpacing(Theme.SPACING_SM)

        heading = QLabel("Renderer Inspector")
        heading.setFont(Typography.caption())
        heading.setStyleSheet(f"color: {Theme.TEXT_MUTED};")

        self._summary = QLabel("No render data")
        self._summary.setFont(Typography.caption())
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(f"color: {Theme.TEXT};")

        layout.addWidget(heading)
        layout.addWidget(self._summary)

    def update_stats(self, stats: RenderStats, active_layers: list[RenderLayerId]) -> None:
        layer_lines = []
        for timing in stats.layer_timings:
            status = "hit" if timing.cache_hit else "miss"
            layer_lines.append(f"• {timing.layer_id}: {timing.duration_ms:.1f} ms ({status})")
        active = ", ".join(layer.value for layer in active_layers) or "—"
        text = (
            f"Render: {stats.total_ms:.1f} ms ({stats.quality.value})\n"
            f"Size: {stats.width}×{stats.height}\n"
            f"Cache: {stats.cache_hits} hits / {stats.cache_misses} misses\n"
            f"Memory: {stats.memory_usage_mb:.2f} MB\n"
            f"Active layers: {active}\n"
        )
        if layer_lines:
            text += "\n" + "\n".join(layer_lines)
        self._summary.setText(text)

    def clear(self) -> None:
        self._summary.setText("No render data")
