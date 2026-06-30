"""Confidence calculation utilities for Vision Engine measurements."""

from __future__ import annotations

import math


def clamp_confidence(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def confidence_from_sample_size(sample_count: int, *, target: int = 500) -> float:
    if sample_count <= 0:
        return 0.0
    ratio = min(1.0, sample_count / target)
    return clamp_confidence(40.0 + ratio * 60.0)


def confidence_from_variance(variance: float, *, scale: float = 2500.0) -> float:
    if variance <= 0:
        return 99.0
    return clamp_confidence(100.0 - min(100.0, (variance / scale) * 100.0))


def confidence_from_edge_strength(strength: float) -> float:
    return clamp_confidence(50.0 + strength * 50.0)


def confidence_from_area_ratio(area_ratio: float) -> float:
    if area_ratio < 0.05:
        return clamp_confidence(area_ratio * 400.0)
    if area_ratio > 0.85:
        return clamp_confidence(100.0 - (area_ratio - 0.85) * 200.0)
    return clamp_confidence(70.0 + area_ratio * 30.0)


def combine_confidences(*values: float) -> float:
    filtered = [value for value in values if value > 0]
    if not filtered:
        return 0.0
    mean = sum(filtered) / len(filtered)
    penalty = math.sqrt(sum((value - mean) ** 2 for value in filtered) / len(filtered)) * 0.15
    return clamp_confidence(mean - penalty)
