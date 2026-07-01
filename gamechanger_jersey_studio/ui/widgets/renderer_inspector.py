"""Expanded Renderer Inspector — live preview and PSD render diagnostics."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from models.psd_render import PSDRenderLog
from models.renderer import RenderLayerId, RenderStats
from ui.theme import Theme
from ui.typography import Typography


class RendererInspector(QFrame):
    """Show live render stats and optional PSD production render details."""

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
            f"Live render: {stats.total_ms:.1f} ms ({stats.quality.value})\n"
            f"Size: {stats.width}×{stats.height}\n"
            f"Cache: {stats.cache_hits} hits / {stats.cache_misses} misses\n"
            f"Memory: {stats.memory_usage_mb:.2f} MB\n"
            f"Active layers: {active}\n"
        )
        if layer_lines:
            text += "\n" + "\n".join(layer_lines)
        self._summary.setText(text)

    def update_psd_render(self, log: PSDRenderLog) -> None:
        lines = [
            f"PSD render: {'OK' if log.success else 'FAILED'} ({log.total_ms:.1f} ms)",
            f"Template: {log.template_id} v{log.template_version}",
            f"Components: {len(log.component_ids)}",
            f"Colours: {', '.join(f'{k}={v}' for k, v in list(log.colours_applied.items())[:4])}",
            f"Patterns: {', '.join(log.patterns_applied) or '—'}",
            f"Textures: {', '.join(log.textures_applied) or '—'}",
            f"Smart Objects: {', '.join(log.smart_objects_updated) or '—'}",
        ]
        for stage in log.stages:
            lines.append(f"• {stage.stage.value}: {stage.duration_ms:.1f} ms")
        if log.warnings:
            lines.append("Warnings:")
            lines.extend(f"  ! {warning}" for warning in log.warnings)
        if log.errors:
            lines.append("Errors:")
            lines.extend(f"  × {error}" for error in log.errors)
        self._summary.setText("\n".join(lines))

    def clear(self) -> None:
        self._summary.setText("No render data")
