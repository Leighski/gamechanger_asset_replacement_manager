"""Layer Mapping Service — configurable Design Specification → PSD layer rules."""

from __future__ import annotations

import json
from pathlib import Path

from models.psd_template import LayerMappingRule, LayerMappingSet, PublishedTemplateMappings
from services.logging_manager import get_logger

logger = get_logger()


class LayerMappingService:
    """Load and publish layer mapping configuration."""

    def load(self, path: Path) -> LayerMappingSet:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LayerMappingSet.model_validate(raw)

    def save(self, mapping_set: LayerMappingSet, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(mapping_set.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def publish(self, template_id: str, template_version: str, mapping_set: LayerMappingSet) -> PublishedTemplateMappings:
        logger.info(
            "Layer mapping created — template={}, rules={}",
            template_id,
            len(mapping_set.mappings),
        )
        return PublishedTemplateMappings(
            template_id=template_id,
            template_version=template_version,
            mappings=list(mapping_set.mappings),
        )

    def resolve_field(
        self,
        published: PublishedTemplateMappings,
        design_spec_field: str,
    ) -> list[LayerMappingRule]:
        return [rule for rule in published.mappings if rule.design_spec_field == design_spec_field]

    def psd_target_for_field(
        self,
        published: PublishedTemplateMappings,
        design_spec_field: str,
    ) -> str:
        rules = self.resolve_field(published, design_spec_field)
        if not rules:
            return ""
        rule = rules[0]
        return rule.smart_object_id or rule.psd_layer_id or rule.psd_layer_name
