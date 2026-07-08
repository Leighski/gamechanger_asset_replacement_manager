"""Colour Analysis — measure dominant jersey colours with confidence."""

from __future__ import annotations

import colorsys

import numpy as np

from models.vision_analysis import ColourChannels, ColourMeasurement
from services.vision.background_removal import SegmentationMask
from services.vision.confidence import clamp_confidence, confidence_from_sample_size, confidence_from_variance
from services.vision.shirt_detection import ShirtDetectionOutput

COLOUR_NAMES = (
    ("Primary Colour", 0),
    ("Secondary Colour", 1),
    ("Accent Colour", 2),
    ("Trim Colour", 3),
    ("Collar Colour", 4),
    ("Sleeve Colour", 5),
)

CATALOGUE_SWATCHES = {
    "Sky Blue": (105, 179, 231),
    "White": (245, 245, 245),
    "Navy": (20, 36, 68),
    "Red": (200, 30, 30),
    "Black": (28, 28, 28),
    "Gold": (212, 175, 55),
}


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = [channel / 255.0 for channel in rgb]
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    x /= 0.95047
    y /= 1.0
    z /= 1.08883
    fx = x ** (1 / 3) if x > 0.008856 else (7.787 * x) + (16 / 116)
    fy = y ** (1 / 3) if y > 0.008856 else (7.787 * y) + (16 / 116)
    fz = z ** (1 / 3) if z > 0.008856 else (7.787 * z) + (16 / 116)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _channels(rgb: tuple[int, int, int]) -> ColourChannels:
    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return ColourChannels(
        rgb=rgb,
        hsv=(round(h * 360.0, 1), round(s * 100.0, 1), round(v * 100.0, 1)),
        lab=tuple(round(channel, 1) for channel in _rgb_to_lab(rgb)),
        hex_value=_rgb_to_hex(rgb),
    )


def _nearest_catalogue(rgb: tuple[int, int, int]) -> str:
    best_name = ""
    best_distance = float("inf")
    for name, swatch in CATALOGUE_SWATCHES.items():
        distance = sum((a - b) ** 2 for a, b in zip(rgb, swatch, strict=True))
        if distance < best_distance:
            best_distance = distance
            best_name = name
    return best_name


class ColourAnalyser:
    """Measure dominant colours from segmented shirt pixels."""

    def analyse(self, shirt: ShirtDetectionOutput, mask: SegmentationMask) -> list[ColourMeasurement]:
        pixels = shirt.crop_pixels.reshape(-1, 3)
        active = mask.mask.reshape(-1)
        samples = pixels[active]
        if samples.size == 0:
            samples = shirt.crop_pixels.reshape(-1, 3)
        samples = samples.astype(np.float32)
        quantised = (samples // 16).astype(np.int16)
        unique, counts = np.unique(quantised, axis=0, return_counts=True)
        order = np.argsort(counts)[::-1]
        measurements: list[ColourMeasurement] = []
        for index, cluster_index in enumerate(order[: len(COLOUR_NAMES)]):
            cluster = unique[cluster_index]
            rgb = tuple(int(min(255, max(0, channel * 16 + 8))) for channel in cluster)
            name, _ = COLOUR_NAMES[index]
            sample_count = int(counts[cluster_index])
            cluster_pixels = samples[np.all(quantised == cluster, axis=1)]
            variance = float(np.var(cluster_pixels)) if cluster_pixels.size else 0.0
            confidence = clamp_confidence(
                min(
                    confidence_from_sample_size(sample_count),
                    confidence_from_variance(variance),
                )
            )
            measurements.append(
                ColourMeasurement(
                    name=name,
                    channels=_channels(rgb),
                    confidence=confidence,
                    catalogue_match=_nearest_catalogue(rgb),
                )
            )
        while len(measurements) < len(COLOUR_NAMES):
            index = len(measurements)
            name, _ = COLOUR_NAMES[index]
            fallback = measurements[-1] if measurements else None
            if fallback is None:
                rgb = (128, 128, 128)
                confidence = 0.0
                catalogue = ""
            else:
                rgb = fallback.channels.rgb
                confidence = clamp_confidence(fallback.confidence * 0.5)
                catalogue = fallback.catalogue_match
            measurements.append(
                ColourMeasurement(
                    name=name,
                    channels=_channels(rgb),
                    confidence=confidence,
                    catalogue_match=catalogue,
                )
            )
        return measurements
