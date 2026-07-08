"""Gamechanger mapping vocabulary — detect → supported Gamechanger equivalents.

Recognition describes what exists on the uploaded image.
Mapping translates findings into supported Gamechanger catalogue / template IDs.

The Gamechanger collar library authority is the approved V-neck family only.
Unsupported collar styles are always remapped to the nearest V-neck — never reproduced.
"""

from __future__ import annotations

from models.garment_recognition.enums import (
    DetectedCollarStyle,
    DetectedSleeveConstruction,
    PatternFamily,
    StripeOrientation,
)

# Single production garment template — no multi-template expansion.
GAMECHANGER_PRODUCTION_TEMPLATE_ID = "GARMENT_ENGLISH_FOOTBALL_BASE_0001"

# Approved V-neck family — catalogue authority for all collar mappings.
GAMECHANGER_VNECK_COLLAR_ID = "COLLAR_0002"
GAMECHANGER_SUPPORTED_COLLAR_IDS: frozenset[str] = frozenset({GAMECHANGER_VNECK_COLLAR_ID})

# Default construction / pattern catalogue IDs used when mapping.
GAMECHANGER_DEFAULT_SLEEVE_ID = "SLEEVE_0001"
GAMECHANGER_DEFAULT_PATTERN_SOLID = "PATTERN_0001"
GAMECHANGER_PATTERN_HOOPS = "PATTERN_0002"
GAMECHANGER_PATTERN_STRIPES = "PATTERN_0003"
GAMECHANGER_PATTERN_CHEVRON = "PATTERN_0004"
GAMECHANGER_PATTERN_GRADIENT = "PATTERN_0005"
GAMECHANGER_PATTERN_HALFTONE = "PATTERN_0006"

COLLAR_MAPPING: dict[DetectedCollarStyle, str] = {
    DetectedCollarStyle.V_NECK: GAMECHANGER_VNECK_COLLAR_ID,
    DetectedCollarStyle.CREW: GAMECHANGER_VNECK_COLLAR_ID,
    DetectedCollarStyle.POLO: GAMECHANGER_VNECK_COLLAR_ID,
    DetectedCollarStyle.HYBRID: GAMECHANGER_VNECK_COLLAR_ID,
    DetectedCollarStyle.HENLEY: GAMECHANGER_VNECK_COLLAR_ID,
    DetectedCollarStyle.MANDARIN: GAMECHANGER_VNECK_COLLAR_ID,
    DetectedCollarStyle.UNKNOWN: GAMECHANGER_VNECK_COLLAR_ID,
}

SLEEVE_MAPPING: dict[DetectedSleeveConstruction, str] = {
    DetectedSleeveConstruction.SET_IN: "SLEEVE_0001",
    DetectedSleeveConstruction.RAGLAN: "SLEEVE_0002",
    DetectedSleeveConstruction.CAP: "SLEEVE_0003",
    DetectedSleeveConstruction.LONG: "SLEEVE_0004",
    DetectedSleeveConstruction.TAPERED: "SLEEVE_0005",
    DetectedSleeveConstruction.UNKNOWN: GAMECHANGER_DEFAULT_SLEEVE_ID,
}

PATTERN_FAMILY_MAPPING: dict[PatternFamily, str] = {
    PatternFamily.SOLID: GAMECHANGER_DEFAULT_PATTERN_SOLID,
    PatternFamily.STRIPES: GAMECHANGER_PATTERN_STRIPES,
    PatternFamily.HOOPS: GAMECHANGER_PATTERN_HOOPS,
    PatternFamily.GRADIENT: GAMECHANGER_PATTERN_GRADIENT,
    PatternFamily.HALFTONE: GAMECHANGER_PATTERN_HALFTONE,
    PatternFamily.NOISE: GAMECHANGER_PATTERN_HALFTONE,
    PatternFamily.HEXAGON: "PATTERN_0004",  # nearest geometric / chevron stand-in
    PatternFamily.HONEYCOMB: "PATTERN_0004",
    PatternFamily.GEOMETRIC: "PATTERN_0004",
    PatternFamily.CARBON_WEAVE: GAMECHANGER_PATTERN_HALFTONE,
    PatternFamily.BRUSH: GAMECHANGER_PATTERN_GRADIENT,
    PatternFamily.WAVE: GAMECHANGER_PATTERN_GRADIENT,
    PatternFamily.DIAGONAL_FADE: GAMECHANGER_PATTERN_GRADIENT,
    PatternFamily.CAMOUFLAGE: GAMECHANGER_PATTERN_HALFTONE,
    PatternFamily.CHEVRON: GAMECHANGER_PATTERN_CHEVRON,
    PatternFamily.UNKNOWN: GAMECHANGER_DEFAULT_PATTERN_SOLID,
}

STRIPE_ORIENTATION_TO_PATTERN: dict[StripeOrientation, str] = {
    StripeOrientation.VERTICAL: GAMECHANGER_PATTERN_STRIPES,
    StripeOrientation.HORIZONTAL: GAMECHANGER_PATTERN_HOOPS,
    StripeOrientation.DIAGONAL: GAMECHANGER_PATTERN_STRIPES,
    StripeOrientation.NONE: GAMECHANGER_DEFAULT_PATTERN_SOLID,
    StripeOrientation.UNKNOWN: GAMECHANGER_DEFAULT_PATTERN_SOLID,
}


def map_collar(detected: DetectedCollarStyle | None) -> str:
    if detected is None:
        return GAMECHANGER_VNECK_COLLAR_ID
    return COLLAR_MAPPING.get(detected, GAMECHANGER_VNECK_COLLAR_ID)


def map_sleeve(detected: DetectedSleeveConstruction | None) -> str:
    if detected is None:
        return GAMECHANGER_DEFAULT_SLEEVE_ID
    return SLEEVE_MAPPING.get(detected, GAMECHANGER_DEFAULT_SLEEVE_ID)


def map_pattern_family(detected: PatternFamily | None) -> str:
    if detected is None:
        return GAMECHANGER_DEFAULT_PATTERN_SOLID
    return PATTERN_FAMILY_MAPPING.get(detected, GAMECHANGER_DEFAULT_PATTERN_SOLID)


def map_stripe_orientation(orientation: StripeOrientation | None) -> str:
    if orientation is None:
        return GAMECHANGER_DEFAULT_PATTERN_SOLID
    return STRIPE_ORIENTATION_TO_PATTERN.get(orientation, GAMECHANGER_DEFAULT_PATTERN_SOLID)


def assert_collar_is_supported(collar_id: str) -> str:
    """Guard: Design Spec collar must always be in the approved V-neck family."""
    if collar_id not in GAMECHANGER_SUPPORTED_COLLAR_IDS:
        return GAMECHANGER_VNECK_COLLAR_ID
    return collar_id
