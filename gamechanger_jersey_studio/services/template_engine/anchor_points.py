"""Anchor Point Service — template anchor registry."""

from __future__ import annotations

import json
from pathlib import Path

from models.psd_template import AnchorPoint, AnchorPointSet
from services.logging_manager import get_logger

logger = get_logger()


class AnchorPointService:
    """Load and query anchor points for PSD templates."""

    def load(self, path: Path) -> AnchorPointSet:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AnchorPointSet.model_validate(raw)

    def save(self, anchor_set: AnchorPointSet, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(anchor_set.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get(self, anchor_set: AnchorPointSet, anchor_id: str) -> AnchorPoint | None:
        for anchor in anchor_set.anchors:
            if anchor.anchor_id == anchor_id:
                return anchor
        return None

    def by_role(self, anchor_set: AnchorPointSet, role: str) -> list[AnchorPoint]:
        return [anchor for anchor in anchor_set.anchors if anchor.role == role]

    def validate_required(self, anchor_set: AnchorPointSet, required_roles: list[str]) -> list[str]:
        present = {anchor.role for anchor in anchor_set.anchors}
        return [role for role in required_roles if role not in present]
