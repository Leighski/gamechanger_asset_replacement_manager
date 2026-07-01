"""PSD Render Service — production PSD rendering pipeline."""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from models.design_specification import DesignSpecification
from models.psd_render import (
    PIPELINE_STAGES,
    PSDRenderLog,
    PSDRenderProgress,
    PSDRenderResult,
    PSDRenderStage,
    PSDRenderStageLog,
    PSDRenderValidationIssue,
)
from models.psd_template import LayerMappingRule, PublishedTemplateMappings
from services.catalogue_manager_service import CatalogueManagerService
from services.logging_manager import get_logger
from services.psd_rendering.layer_colour_service import COLOUR_FIELDS, LayerColourService
from services.psd_rendering.layer_visibility_service import LayerVisibilityService
from services.psd_rendering.pattern_placement_service import PatternPlacementService
from services.psd_rendering.psd_export_service import PSDExportService
from services.psd_rendering.psd_render_validator import PSDRenderValidator
from services.psd_rendering.smart_object_render_service import SmartObjectRenderService
from services.psd_rendering.texture_placement_service import TexturePlacementService
from services.rendering.component_assembler import ComponentAssembler
from services.template_engine.manager import TemplateManager

logger = get_logger()


class PSDRenderError(RuntimeError):
    """Raised when production PSD rendering cannot complete."""


class PSDRenderService:
    """Data-driven production PSD renderer."""

    def __init__(
        self,
        template_manager: TemplateManager,
        catalogue: CatalogueManagerService,
    ) -> None:
        self._templates = template_manager
        self._assembler = ComponentAssembler(catalogue)
        self._colours = LayerColourService()
        self._patterns = PatternPlacementService()
        self._textures = TexturePlacementService()
        self._visibility = LayerVisibilityService()
        self._smart_objects = SmartObjectRenderService()
        self._export = PSDExportService()
        self._validator = PSDRenderValidator()

    def render(
        self,
        spec: DesignSpecification,
        mappings: PublishedTemplateMappings,
        *,
        project_name: str,
        output_folder: str,
        progress_callback: Callable[[PSDRenderProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> PSDRenderResult:
        started = time.perf_counter()
        render_log = PSDRenderLog(
            template_id=mappings.template_id,
            template_version=mappings.template_version,
            project_name=project_name,
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        progress = PSDRenderProgress(remaining_stages=list(PIPELINE_STAGES))

        def emit(stage: PSDRenderStage, *, layer: str = "", warning: str = "", error: str = "") -> None:
            progress.current_stage = stage
            progress.current_layer = layer
            progress.remaining_stages = [s for s in PIPELINE_STAGES if s not in progress.completed_stages and s != stage]
            progress.elapsed_ms = (time.perf_counter() - started) * 1000.0
            if warning:
                progress.warnings.append(warning)
                render_log.warnings.append(warning)
            if error:
                progress.errors.append(error)
                render_log.errors.append(error)
            if progress_callback:
                progress_callback(progress)

        def stage_done(stage: PSDRenderStage, stage_started: float, *, layer: str = "", message: str = "") -> None:
            duration = (time.perf_counter() - stage_started) * 1000.0
            render_log.stages.append(
                PSDRenderStageLog(stage=stage, duration_ms=round(duration, 2), layer_name=layer, message=message)
            )
            progress.completed_stages.append(stage)
            logger.info("PSD render stage complete — {} {:.1f}ms {}", stage.value, duration, message)

        def should_abort() -> bool:
            return cancel_check is not None and cancel_check()

        psd = None
        output_dir: Path | None = None
        try:
            # 1. Open PSD
            stage_started = time.perf_counter()
            if should_abort():
                raise PSDRenderError("Render cancelled")
            emit(PSDRenderStage.OPEN_PSD)
            source_psd = self._templates.open_template_psd(mappings.template_id)
            output_dir = self._export.build_output_dir(output_folder, project_name)
            working_psd = output_dir / f"{project_name}_working.psd"
            shutil.copy2(source_psd, working_psd)
            from psd_tools import PSDImage

            psd = PSDImage.open(working_psd)
            layer_index = self._layer_index(psd)
            stage_done(PSDRenderStage.OPEN_PSD, stage_started, message=str(working_psd))

            # 2. Resolve mappings
            stage_started = time.perf_counter()
            emit(PSDRenderStage.RESOLVE_MAPPINGS)
            rules_by_field = self._group_rules(mappings)
            stage_done(PSDRenderStage.RESOLVE_MAPPINGS, stage_started, message=f"{len(mappings.mappings)} rules")

            # 3. Resolve components
            stage_started = time.perf_counter()
            emit(PSDRenderStage.RESOLVE_COMPONENTS)
            component_ids = self._assembler.spec_references(spec)
            render_log.component_ids = component_ids
            stage_done(PSDRenderStage.RESOLVE_COMPONENTS, stage_started, message=f"{len(component_ids)} components")

            # Pre-validation before mutating
            issues = self._validator.validate(spec, mappings, self._assembler, layer_index)
            render_log.validation_issues = issues
            error_issues = [issue for issue in issues if issue.severity == "error"]
            if error_issues:
                raise PSDRenderError("; ".join(issue.message for issue in error_issues))

            # 4. Apply colours
            stage_started = time.perf_counter()
            if should_abort():
                raise PSDRenderError("Render cancelled")
            emit(PSDRenderStage.APPLY_COLOURS)
            colours = self._colours.spec_colours(spec)
            render_log.colours_applied = colours
            for field, colour in colours.items():
                if not colour:
                    continue
                for rule in rules_by_field.get(field, []):
                    layer = layer_index.get(rule.psd_layer_name)
                    if layer is None:
                        continue
                    emit(PSDRenderStage.APPLY_COLOURS, layer=rule.psd_layer_name)
                    self._colours.apply_to_layer_pixels(layer, colour)
            stage_done(PSDRenderStage.APPLY_COLOURS, stage_started)

            # 5. Apply patterns
            stage_started = time.perf_counter()
            emit(PSDRenderStage.APPLY_PATTERNS)
            pattern_rules = rules_by_field.get("pattern", [])
            if pattern_rules and spec.pattern:
                pattern_image, _ = self._assembler.load_field_image(
                    "pattern", spec.pattern, psd.size
                )
                for rule in pattern_rules:
                    layer = layer_index.get(rule.psd_layer_name)
                    if layer is None:
                        continue
                    canvas_size = (layer.width, layer.height) if layer.width and layer.height else psd.size
                    placed = self._patterns.build_pattern_image(
                        pattern_image,
                        hex_colour=spec.secondary_colour or spec.primary_colour,
                        scale=spec.pattern_scale,
                        rotation_degrees=spec.pattern_rotation,
                        opacity=spec.pattern_opacity,
                        canvas_size=canvas_size,
                    )
                    self._smart_objects.replace_layer_content(layer, placed)
                    render_log.patterns_applied.append(rule.psd_layer_name)
                    emit(PSDRenderStage.APPLY_PATTERNS, layer=rule.psd_layer_name)
            stage_done(PSDRenderStage.APPLY_PATTERNS, stage_started)

            # 6. Apply textures
            stage_started = time.perf_counter()
            emit(PSDRenderStage.APPLY_TEXTURES)
            texture_rules = rules_by_field.get("texture_style", [])
            if texture_rules and spec.texture_style:
                texture_image, _ = self._assembler.load_field_image(
                    "texture_style", spec.texture_style, psd.size
                )
                for rule in texture_rules:
                    layer = layer_index.get(rule.psd_layer_name)
                    if layer is None:
                        continue
                    try:
                        base = layer.topil().convert("RGBA")
                    except Exception:
                        continue
                    textured = self._textures.apply_texture(base, texture_image)
                    self._smart_objects.replace_layer_content(layer, textured)
                    render_log.textures_applied.append(rule.psd_layer_name)
                    emit(PSDRenderStage.APPLY_TEXTURES, layer=rule.psd_layer_name)
            stage_done(PSDRenderStage.APPLY_TEXTURES, stage_started)

            # 7. Update Smart Objects (collar, etc.)
            stage_started = time.perf_counter()
            emit(PSDRenderStage.UPDATE_SMART_OBJECTS)
            smart_fields = ("collar_style", "sleeve_style", "trim_style", "material_style")
            for field in smart_fields:
                reference = str(spec.get_field(field) or "").strip()
                if not reference:
                    continue
                try:
                    component_image, component = self._assembler.load_field_image(field, reference, psd.size)
                except Exception:
                    continue
                colour_field = {
                    "collar_style": spec.collar_colour,
                    "sleeve_style": spec.sleeve_colour,
                    "trim_style": spec.trim_colour,
                    "material_style": spec.primary_colour,
                }.get(field, "")
                prepared = self._smart_objects.component_image(component_image, hex_colour=colour_field)
                for rule in rules_by_field.get(field, []):
                    layer = layer_index.get(rule.psd_layer_name)
                    if layer is None:
                        continue
                    if self._smart_objects.replace_layer_content(layer, prepared):
                        label = rule.smart_object_id or rule.psd_layer_name
                        render_log.smart_objects_updated.append(label)
                        emit(PSDRenderStage.UPDATE_SMART_OBJECTS, layer=rule.psd_layer_name)
            stage_done(PSDRenderStage.UPDATE_SMART_OBJECTS, stage_started)

            # 8. Toggle layers
            stage_started = time.perf_counter()
            emit(PSDRenderStage.TOGGLE_LAYERS)
            visibility_path = self._templates.root / self._templates.get_template(mappings.template_id).slug / "layer_visibility.json"  # type: ignore[union-attr]
            rules = self._visibility.load_rules(visibility_path)
            toggled = self._visibility.apply_visibility(psd, mappings, spec, visibility_rules=rules)
            render_log.layers_toggled = toggled
            stage_done(PSDRenderStage.TOGGLE_LAYERS, stage_started, message=f"{len(toggled)} toggles")

            # 9. Validate
            stage_started = time.perf_counter()
            emit(PSDRenderStage.VALIDATE)
            post_issues = self._validator.validate(spec, mappings, self._assembler, layer_index)
            render_log.validation_issues.extend(
                [issue for issue in post_issues if issue not in render_log.validation_issues]
            )
            if self._validator.has_errors(post_issues):
                raise PSDRenderError("Post-render validation failed")
            for issue in post_issues:
                if issue.severity == "warning":
                    emit(PSDRenderStage.VALIDATE, warning=issue.message)
            stage_done(PSDRenderStage.VALIDATE, stage_started)

            # 10. Save
            stage_started = time.perf_counter()
            emit(PSDRenderStage.SAVE)
            psd_path = output_dir / f"{project_name}_render.psd"
            png_path = output_dir / f"{project_name}_preview.png"
            log_path = output_dir / "render_log.json"
            self._export.save_psd(psd, psd_path)
            self._export.save_png_preview(psd, png_path)
            stage_done(PSDRenderStage.SAVE, stage_started, message=str(psd_path))
            render_log.success = True
            render_log.total_ms = round((time.perf_counter() - started) * 1000.0, 2)
            self._export.save_render_log(render_log, log_path)
            logger.info("PSD render completed — {} in {:.1f}ms", psd_path, render_log.total_ms)
            return PSDRenderResult(
                success=True,
                psd_path=str(psd_path),
                png_path=str(png_path),
                log_path=str(log_path),
                output_dir=str(output_dir),
                log=render_log,
            )
        except Exception as exc:
            render_log.success = False
            render_log.errors.append(str(exc))
            render_log.total_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if output_dir is not None:
                log_path = output_dir / "render_log.json"
                self._export.save_render_log(render_log, log_path)
                return PSDRenderResult(success=False, error=str(exc), output_dir=str(output_dir), log_path=str(log_path), log=render_log)
            logger.error("PSD render failed — {}", exc)
            return PSDRenderResult(success=False, error=str(exc), log=render_log)

    @staticmethod
    def _layer_index(psd) -> dict[str, object]:
        return {str(layer.name): layer for layer in psd.descendants() if getattr(layer, "name", None)}

    @staticmethod
    def _group_rules(mappings: PublishedTemplateMappings) -> dict[str, list[LayerMappingRule]]:
        grouped: dict[str, list[LayerMappingRule]] = {}
        for rule in mappings.mappings:
            grouped.setdefault(rule.design_spec_field, []).append(rule)
        return grouped
