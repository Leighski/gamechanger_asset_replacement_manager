"""Pattern Analysis foundation — measure coverage, density, orientation, frequency."""

from __future__ import annotations

import numpy as np

from models.vision_analysis import ConfidentFloat, PatternMeasurements
from services.vision.background_removal import SegmentationMask
from services.vision.confidence import clamp_confidence, confidence_from_edge_strength
from services.vision.shirt_detection import ShirtDetectionOutput


class PatternAnalyser:
    """Estimate pattern metrics without identifying pattern type."""

    def analyse(self, shirt: ShirtDetectionOutput, mask: SegmentationMask) -> PatternMeasurements:
        gray = np.mean(shirt.crop_pixels.astype(np.float32), axis=2)
        active = mask.mask
        if active.any():
            values = gray[active]
        else:
            values = gray.reshape(-1)
        variance = float(np.var(values))
        coverage = float(active.mean() * 100.0) if active.size else 80.0
        gradient_y = np.abs(np.diff(gray, axis=0)).mean() if gray.shape[0] > 1 else 0.0
        gradient_x = np.abs(np.diff(gray, axis=1)).mean() if gray.shape[1] > 1 else 0.0
        edge_strength = float((gradient_x + gradient_y) / 2.0 / 255.0)
        orientation = 0.0
        if gradient_x > gradient_y * 1.2:
            orientation = 90.0
        elif gradient_y > gradient_x * 1.2:
            orientation = 0.0
        else:
            orientation = 45.0
        density = clamp_confidence(min(100.0, variance / 4.0))
        frequency = clamp_confidence(min(100.0, edge_strength * 180.0))
        base = confidence_from_edge_strength(edge_strength)
        return PatternMeasurements(
            coverage_percent=ConfidentFloat(value=round(coverage, 1), confidence=clamp_confidence(base * 0.9)),
            density=ConfidentFloat(value=density, confidence=clamp_confidence(base * 0.81)),
            orientation_degrees=ConfidentFloat(value=orientation, confidence=clamp_confidence(base * 0.86)),
            frequency=ConfidentFloat(value=frequency, confidence=clamp_confidence(base * 0.8)),
        )
