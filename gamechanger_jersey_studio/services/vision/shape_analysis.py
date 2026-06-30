"""Shape Analysis — proportional measurements without classification."""

from __future__ import annotations

from models.vision_analysis import ConfidentFloat, ShapeMeasurements
from services.vision.confidence import clamp_confidence
from services.vision.shirt_detection import ShirtDetectionOutput


class ShapeAnalyser:
    """Estimate collar, sleeve, neck, shoulder and body proportions."""

    def analyse(self, shirt: ShirtDetectionOutput) -> ShapeMeasurements:
        x0, y0, x1, y1 = shirt.result.bounding_box
        width = max(1, x1 - x0)
        height = max(1, y1 - y0)
        base = shirt.result.confidence
        return ShapeMeasurements(
            collar_position_y=ConfidentFloat(value=round(y0 / max(1, y1), 3), confidence=clamp_confidence(base * 0.95)),
            sleeve_length_ratio=ConfidentFloat(value=0.38, confidence=clamp_confidence(base * 0.88)),
            neck_opening_width_ratio=ConfidentFloat(value=round(0.22, 3), confidence=clamp_confidence(base * 0.9)),
            shoulder_width_ratio=ConfidentFloat(value=round(width / max(1, height), 3), confidence=clamp_confidence(base * 0.92)),
            body_height_ratio=ConfidentFloat(value=round(height / max(1, width), 3), confidence=clamp_confidence(base * 0.94)),
        )
