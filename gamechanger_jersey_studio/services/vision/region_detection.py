"""Region Detection — locate collar, sleeves, body, shoulders, side panels, trim."""

from __future__ import annotations

import numpy as np

from models.vision_analysis import RegionPolygon
from services.vision.confidence import clamp_confidence
from services.vision.shirt_detection import ShirtDetectionOutput


class RegionDetector:
    """Estimate jersey regions from shirt crop geometry."""

    def detect(self, shirt: ShirtDetectionOutput) -> list[RegionPolygon]:
        x0, y0, x1, y1 = shirt.result.bounding_box
        crop_w = max(1, x1 - x0)
        crop_h = max(1, y1 - y0)
        regions: list[RegionPolygon] = []

        def rect(name: str, rx0: float, ry0: float, rx1: float, ry1: float, confidence: float) -> RegionPolygon:
            return RegionPolygon(
                name=name,
                points=[
                    (int(x0 + rx0 * crop_w), int(y0 + ry0 * crop_h)),
                    (int(x0 + rx1 * crop_w), int(y0 + ry0 * crop_h)),
                    (int(x0 + rx1 * crop_w), int(y0 + ry1 * crop_h)),
                    (int(x0 + rx0 * crop_w), int(y0 + ry1 * crop_h)),
                ],
                confidence=clamp_confidence(confidence),
            )

        base_confidence = shirt.result.confidence
        regions.extend(
            [
                rect("Collar", 0.35, 0.0, 0.65, 0.12, base_confidence * 0.96),
                rect("Sleeves", 0.0, 0.12, 0.18, 0.45, base_confidence * 0.9),
                rect("Sleeves", 0.82, 0.12, 1.0, 0.45, base_confidence * 0.9),
                rect("Body", 0.2, 0.12, 0.8, 0.88, base_confidence * 0.98),
                rect("Shoulders", 0.18, 0.1, 0.82, 0.22, base_confidence * 0.93),
                rect("Side Panels", 0.15, 0.35, 0.28, 0.8, base_confidence * 0.88),
                rect("Side Panels", 0.72, 0.35, 0.85, 0.8, base_confidence * 0.88),
                rect("Trim", 0.3, 0.86, 0.7, 0.95, base_confidence * 0.85),
            ]
        )
        return regions
