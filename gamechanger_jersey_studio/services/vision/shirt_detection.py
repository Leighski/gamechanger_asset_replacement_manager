"""Shirt Detection — locate the football shirt within the image."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.vision_analysis import ShirtDetectionResult
from services.vision.confidence import clamp_confidence, confidence_from_area_ratio
from services.vision.image_normalisation import NormalisedImage


@dataclass(frozen=True)
class ShirtDetectionOutput:
    result: ShirtDetectionResult
    crop_pixels: np.ndarray


class ShirtDetector:
    """Heuristic shirt detection based on central foreground mass."""

    def detect(self, image: NormalisedImage) -> ShirtDetectionOutput:
        height, width = image.height, image.width
        gray = np.mean(image.pixels.astype(np.float32), axis=2)
        background = np.median(gray)
        foreground = np.abs(gray - background) > 18.0

        margin_y = int(height * 0.08)
        margin_x = int(width * 0.08)
        foreground[:margin_y, :] = False
        foreground[-margin_y:, :] = False
        foreground[:, :margin_x] = False
        foreground[:, -margin_x:] = False

        if not foreground.any():
            box = (margin_x, margin_y, width - margin_x, height - margin_y)
            confidence = 35.0
        else:
            ys, xs = np.where(foreground)
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            pad_x = max(4, int((x1 - x0) * 0.04))
            pad_y = max(4, int((y1 - y0) * 0.04))
            x0 = max(0, x0 - pad_x)
            y0 = max(0, y0 - pad_y)
            x1 = min(width - 1, x1 + pad_x)
            y1 = min(height - 1, y1 + pad_y)
            box = (x0, y0, x1, y1)
            area_ratio = ((x1 - x0) * (y1 - y0)) / max(1, width * height)
            confidence = confidence_from_area_ratio(area_ratio)

        x0, y0, x1, y1 = box
        outline = [
            (x0, y0),
            (x1, y0),
            (x1, y1),
            (x0, y1),
        ]
        crop = image.pixels[y0 : y1 + 1, x0 : x1 + 1].copy()
        requires_review = confidence < 70.0
        result = ShirtDetectionResult(
            bounding_box=box,
            outline_points=outline,
            confidence=clamp_confidence(confidence),
            requires_review=requires_review,
        )
        return ShirtDetectionOutput(result=result, crop_pixels=crop)
