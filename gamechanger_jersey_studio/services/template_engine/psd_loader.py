"""PSD Template Loader — read-only PSD analysis."""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone
from pathlib import Path

from models.psd_template import (
    BlendMode,
    PSDAnalysisReport,
    PSDLayerNode,
    SmartObjectRecord,
)
from services.logging_manager import get_logger

logger = get_logger()


class PSDTemplateLoader:
    """Analyse PSD files without modifying them."""

    SUPPORTED_PSD_VERSIONS = {1}

    def analyse(self, template_id: str, psd_path: Path) -> PSDAnalysisReport:
        started = time.perf_counter()
        source = Path(psd_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"PSD not found: {source}")

        try:
            from psd_tools import PSDImage
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psd-tools is required for PSD analysis") from exc

        psd = PSDImage.open(source)
        layers: list[PSDLayerNode] = []
        smart_objects: list[SmartObjectRecord] = []
        warnings: list[str] = []
        layer_index = 0
        group_count = 0
        adjustment_count = 0
        masked_count = 0

        def walk(parent_id: str, nodes) -> None:
            nonlocal layer_index, group_count, adjustment_count, masked_count
            for node in nodes:
                layer_index += 1
                layer_id = f"L{layer_index:04d}"
                kind = str(getattr(node, "kind", "pixel") or "pixel")
                is_group = bool(getattr(node, "is_group", lambda: False)())
                if is_group:
                    group_count += 1
                is_smart = kind == "smartobject"
                is_adjustment = kind in {"curves", "levels", "hue_saturation", "gradient_map", "solidcolorfill"}
                if is_adjustment:
                    adjustment_count += 1
                has_mask = bool(getattr(node, "mask", None) is not None)
                if has_mask:
                    masked_count += 1

                offset = getattr(node, "offset", (0, 0))
                size = getattr(node, "size", (0, 0))
                blend = str(getattr(node, "blend_mode", "normal") or "normal")
                child_ids: list[str] = []
                node_obj = PSDLayerNode(
                    layer_id=layer_id,
                    name=str(getattr(node, "name", "") or f"Layer {layer_index}"),
                    parent_id=parent_id,
                    kind=kind,
                    visible=bool(getattr(node, "visible", True)),
                    opacity=float(getattr(node, "opacity", 255) or 255) / 255.0,
                    blend_mode=self._normalise_blend_mode(blend),
                    is_group=is_group,
                    is_smart_object=is_smart,
                    is_adjustment=is_adjustment,
                    has_mask=has_mask,
                    offset_x=int(offset[0]),
                    offset_y=int(offset[1]),
                    width=int(size[0]),
                    height=int(size[1]),
                    children=child_ids,
                )
                layers.append(node_obj)

                if is_smart:
                    smart_objects.append(
                        SmartObjectRecord(
                            smart_object_id=f"SO{len(smart_objects) + 1:04d}",
                            name=node_obj.name,
                            layer_id=layer_id,
                            parent_group=parent_id,
                            offset_x=node_obj.offset_x,
                            offset_y=node_obj.offset_y,
                            width=node_obj.width,
                            height=node_obj.height,
                        )
                    )

                if is_group and hasattr(node, "__iter__"):
                    walk(layer_id, node)

        walk("", list(psd))

        colour_mode = str(getattr(psd, "color_mode", "") or "")
        colour_profile = ""
        if hasattr(psd, "icc_profile") and psd.icc_profile:
            colour_profile = "embedded"
        version = int(getattr(psd, "version", 1) or 1)
        if version not in self.SUPPORTED_PSD_VERSIONS:
            warnings.append(f"Unsupported PSD version: {version}")

        resolution = float(getattr(psd, "resolution", (72.0, 72.0))[0] or 72.0)
        report = PSDAnalysisReport(
            template_id=template_id,
            analysed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            psd_path=str(source),
            psd_version=version,
            canvas_width=int(psd.width),
            canvas_height=int(psd.height),
            resolution_ppi=resolution,
            colour_profile=colour_profile,
            colour_mode=colour_mode,
            layer_count=len(layers),
            smart_object_count=len(smart_objects),
            group_count=group_count,
            adjustment_layer_count=adjustment_count,
            masked_layer_count=masked_count,
            layers=layers,
            smart_objects=smart_objects,
            warnings=warnings,
        )
        elapsed = (time.perf_counter() - started) * 1000.0
        logger.info(
            "PSD analysed — template={}, layers={}, smart_objects={}, {:.1f}ms",
            template_id,
            report.layer_count,
            report.smart_object_count,
            elapsed,
        )
        return report

    def can_read(self, psd_path: Path) -> bool:
        try:
            from psd_tools import PSDImage
        except ImportError:
            return False
        try:
            with PSDImage.open(psd_path) as psd:
                return psd.width > 0
        except Exception:
            return False

    @staticmethod
    def _normalise_blend_mode(value: str) -> str:
        normalized = value.lower().replace(" ", "_")
        try:
            return BlendMode(normalized).value
        except ValueError:
            return BlendMode.UNKNOWN.value

    def analyse_bytes(self, template_id: str, data: bytes, *, label: str = "memory.psd") -> PSDAnalysisReport:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".psd", delete=False) as handle:
            handle.write(data)
            path = Path(handle.name)
        try:
            return self.analyse(template_id, path)
        finally:
            path.unlink(missing_ok=True)
