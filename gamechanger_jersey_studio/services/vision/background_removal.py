"""Background Removal — internal segmentation mask, not persisted."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from services.vision.confidence import clamp_confidence, confidence_from_sample_size
from services.vision.shirt_detection import ShirtDetectionOutput


@dataclass(frozen=True)
class SegmentationMask:
    mask: np.ndarray
    confidence: float


class BackgroundRemover:
    """Separate shirt pixels from background using a temporary mask."""

    def segment(self, shirt: ShirtDetectionOutput) -> SegmentationMask:
        pixels = shirt.crop_pixels.astype(np.float32)
        gray = np.mean(pixels, axis=2)
        background = float(np.median(gray))
        mask = np.abs(gray - background) > 15.0
        sample_count = int(mask.sum())
        confidence = confidence_from_sample_size(sample_count, target=800)
        if shirt.result.requires_review:
            confidence = clamp_confidence(confidence * 0.85)
        return SegmentationMask(mask=mask, confidence=clamp_confidence(confidence))
