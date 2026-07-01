"""Template Manager — orchestrate PSD template registration and publishing."""

from __future__ import annotations

import json
import time
from pathlib import Path

from models.psd_template import (
    AnchorPointSet,
    LayerMappingSet,
    PSDAnalysisReport,
    PSDTemplate,
    PublishedTemplateMappings,
    TemplateProjectSettings,
    TemplateRegistry,
    TemplateValidationReport,
)
from services.logging_manager import get_logger
from services.template_engine.anchor_points import AnchorPointService
from services.template_engine.layer_mapping import LayerMappingService
from services.template_engine.preview_generator import TemplatePreviewGenerator
from services.template_engine.psd_loader import PSDTemplateLoader
from services.template_engine.smart_objects import SmartObjectService
from services.template_engine.validator import TemplateValidator

logger = get_logger()

MANIFEST_NAME = "manifest.json"
TEMPLATE_NAME = "template.json"
ANALYSIS_NAME = "analysis.json"
MAPPINGS_NAME = "layer_mappings.json"
ANCHORS_NAME = "anchor_points.json"


class TemplateManager:
    """Permanent bridge between Jersey Studio and Gamechanger PSD templates."""

    def __init__(self, templates_root: Path | None = None) -> None:
        from core.paths import TEMPLATES_CONFIG_DIR

        self._root = templates_root or TEMPLATES_CONFIG_DIR
        self._loader = PSDTemplateLoader()
        self._mapping = LayerMappingService()
        self._anchors = AnchorPointService()
        self._smart_objects = SmartObjectService()
        self._validator = TemplateValidator()
        self._preview = TemplatePreviewGenerator()
        self._registry = TemplateRegistry()
        self._analysis_cache: dict[str, PSDAnalysisReport] = {}
        self._mapping_cache: dict[str, LayerMappingSet] = {}
        self._anchor_cache: dict[str, AnchorPointSet] = {}
        self._validation_cache: dict[str, TemplateValidationReport] = {}
        self._last_load_ms: float = 0.0

    @property
    def root(self) -> Path:
        return self._root

    @property
    def registry(self) -> TemplateRegistry:
        return self._registry

    @property
    def last_load_ms(self) -> float:
        return self._last_load_ms

    def load(self) -> TemplateRegistry:
        started = time.perf_counter()
        manifest_path = self._root / MANIFEST_NAME
        if not manifest_path.is_file():
            self._registry = TemplateRegistry()
            self._last_load_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return self._registry
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._registry = TemplateRegistry.model_validate(raw)
        self._analysis_cache.clear()
        self._mapping_cache.clear()
        self._anchor_cache.clear()
        self._validation_cache.clear()
        for template in self._registry.templates:
            self._load_template_assets(template)
        self._last_load_ms = round((time.perf_counter() - started) * 1000.0, 2)
        logger.info(
            "Template loaded — {} template(s) in {:.1f}ms",
            len(self._registry.templates),
            self._last_load_ms,
        )
        return self._registry

    def reload(self) -> TemplateRegistry:
        return self.load()

    def get_template(self, template_id: str) -> PSDTemplate | None:
        return self._registry.get(template_id)

    def list_templates(self) -> list[PSDTemplate]:
        return list(self._registry.templates)

    def analysis(self, template_id: str) -> PSDAnalysisReport | None:
        return self._analysis_cache.get(template_id)

    def mappings(self, template_id: str) -> LayerMappingSet | None:
        return self._mapping_cache.get(template_id)

    def anchors(self, template_id: str) -> AnchorPointSet | None:
        return self._anchor_cache.get(template_id)

    def validation(self, template_id: str) -> TemplateValidationReport | None:
        return self._validation_cache.get(template_id)

    def preview_path(self, template: PSDTemplate) -> Path | None:
        if not template.slug:
            return None
        slug_dir = self._root / template.slug
        if template.preview_image:
            path = slug_dir / template.preview_image
            if path.is_file():
                return path
        fallback = slug_dir / "preview.png"
        return fallback if fallback.is_file() else None

    def register_and_analyse(self, template: PSDTemplate) -> PSDAnalysisReport:
        slug_dir = self._root / template.slug
        slug_dir.mkdir(parents=True, exist_ok=True)
        (slug_dir / TEMPLATE_NAME).write_text(
            json.dumps(template.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        psd_path = slug_dir / Path(template.psd_path).name if template.psd_path else None
        if psd_path and psd_path.is_file():
            report = self._loader.analyse(template.template_id, psd_path)
            self._save_analysis(template.slug, report)
        else:
            report = self._analysis_cache.get(template.template_id)
            if report is None:
                raise FileNotFoundError(f"No PSD or cached analysis for {template.template_id}")
        return report

    def publish_mappings(self, template_id: str) -> PublishedTemplateMappings | None:
        template = self.get_template(template_id)
        mapping_set = self.mappings(template_id)
        anchor_set = self.anchors(template_id)
        analysis = self.analysis(template_id)
        if template is None or mapping_set is None:
            return None
        published = self._mapping.publish(template.template_id, template.version, mapping_set)
        if anchor_set is not None:
            published.anchors = list(anchor_set.anchors)
        published.analysis = analysis
        return published

    def active_template_id(self, settings: TemplateProjectSettings | None, manifest_build_profile: str) -> str:
        if settings and settings.active_template_id:
            return settings.active_template_id
        for template in self._registry.templates:
            if manifest_build_profile in template.build_profile_compatibility:
                return template.template_id
        if self._registry.templates:
            return self._registry.templates[0].template_id
        return "TEMPLATE_BROADCAST_0001"

    def select_template(self, template_id: str) -> PSDTemplate | None:
        template = self.get_template(template_id)
        if template is None:
            return None
        logger.info("Template selected — {}", template_id)
        return template

    def template_for_project(
        self,
        settings: TemplateProjectSettings | None,
        build_profile: str,
    ) -> PSDTemplate | None:
        template_id = self.active_template_id(settings, build_profile)
        return self.get_template(template_id)

    def template_psd_path(self, template_id: str) -> Path | None:
        template = self.get_template(template_id)
        if template is None or not template.slug or not template.psd_path:
            return None
        path = self._root / template.slug / Path(template.psd_path).name
        return path if path.is_file() else None

    def open_template_psd(self, template_id: str) -> Path:
        """Load PSD path through Template Engine — sole application entry point for PSD files."""
        path = self.template_psd_path(template_id)
        if path is None:
            raise FileNotFoundError(f"PSD template file not registered: {template_id}")
        logger.info("Template PSD opened — {} ({})", template_id, path.name)
        return path

    def _load_template_assets(self, template: PSDTemplate) -> None:
        slug_dir = self._root / template.slug
        analysis_path = slug_dir / ANALYSIS_NAME
        if analysis_path.is_file():
            report = PSDAnalysisReport.model_validate(json.loads(analysis_path.read_text(encoding="utf-8")))
            self._analysis_cache[template.template_id] = report

        mappings_path = slug_dir / MAPPINGS_NAME
        if mappings_path.is_file():
            self._mapping_cache[template.template_id] = self._mapping.load(mappings_path)

        anchors_path = slug_dir / ANCHORS_NAME
        if anchors_path.is_file():
            self._anchor_cache[template.template_id] = self._anchors.load(anchors_path)

        mapping_set = self._mapping_cache.get(template.template_id)
        anchor_set = self._anchor_cache.get(template.template_id)
        analysis = self._analysis_cache.get(template.template_id)
        if mapping_set and anchor_set:
            self._validation_cache[template.template_id] = self._validator.validate(
                template, analysis, mapping_set, anchor_set
            )

        self._preview.ensure_preview(template, self._root)

    def _save_analysis(self, slug: str, report: PSDAnalysisReport) -> None:
        path = self._root / slug / ANALYSIS_NAME
        path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        self._analysis_cache[report.template_id] = report
