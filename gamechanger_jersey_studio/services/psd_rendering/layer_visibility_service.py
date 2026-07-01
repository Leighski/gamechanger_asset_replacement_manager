"""Layer Visibility Service — toggle optional PSD layers from Design Specification."""

from __future__ import annotations

import json
from pathlib import Path

from models.psd_template import LayerMappingRule, PublishedTemplateMappings


class LayerVisibilityService:
    """Show mapped layers; hide optional variants not referenced by the spec."""

    def load_rules(self, path: Path) -> dict[str, list[str]]:
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {key: list(value) for key, value in raw.get("hide_when_unmapped", {}).items()}

    def apply_visibility(
        self,
        psd,
        mappings: PublishedTemplateMappings,
        spec,
        *,
        visibility_rules: dict[str, list[str]] | None = None,
    ) -> list[str]:
        mapped_names = {rule.psd_layer_name for rule in mappings.mappings if rule.psd_layer_name}
        toggled: list[str] = []
        active_fields = {
            rule.design_spec_field
            for rule in mappings.mappings
            if str(spec.get_field(rule.design_spec_field) or "").strip()
        }

        for layer in psd.descendants():
            name = str(getattr(layer, "name", "") or "")
            if not name:
                continue
            if name in mapped_names:
                layer.visible = True
                toggled.append(f"show:{name}")
                continue
            if visibility_rules:
                for field, hide_layers in visibility_rules.items():
                    if field not in active_fields and name in hide_layers:
                        layer.visible = False
                        toggled.append(f"hide:{name}")
        return toggled

    def mapped_layer_names(self, mappings: PublishedTemplateMappings) -> set[str]:
        return {rule.psd_layer_name for rule in mappings.mappings if rule.psd_layer_name}
