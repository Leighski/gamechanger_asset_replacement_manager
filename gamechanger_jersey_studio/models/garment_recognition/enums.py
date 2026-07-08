"""Enums for the Garment Recognition Contract — detected vocabulary only."""

from __future__ import annotations

from enum import Enum


class RecognitionModuleId(str, Enum):
    """Stable identifiers for independently testable recognition modules."""

    GARMENT = "garment"
    SEGMENTATION = "segmentation"
    COLOUR = "colour"
    STRIPE = "stripe"
    SLEEVE = "sleeve"
    COLLAR = "collar"
    PATTERN = "pattern"
    PANEL = "panel"
    BRANDING = "branding"


class SegmentationRegionId(str, Enum):
    """Physical construction regions on a front-view football shirt."""

    SHIRT_BOUNDARY = "shirt_boundary"
    BACKGROUND = "background"
    COLLAR = "collar"
    LEFT_SLEEVE = "left_sleeve"
    RIGHT_SLEEVE = "right_sleeve"
    MAIN_BODY = "main_body"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_CUFF = "left_cuff"
    RIGHT_CUFF = "right_cuff"
    LEFT_SIDE_PANEL = "left_side_panel"
    RIGHT_SIDE_PANEL = "right_side_panel"


class GarmentType(str, Enum):
    FOOTBALL_SHIRT = "football_shirt"
    UNKNOWN = "unknown"


class DetectedCollarStyle(str, Enum):
    """Collar styles observed on the uploaded shirt (not Gamechanger catalogue IDs)."""

    V_NECK = "v_neck"
    CREW = "crew"
    POLO = "polo"
    HYBRID = "hybrid"
    HENLEY = "henley"
    MANDARIN = "mandarin"
    UNKNOWN = "unknown"


class DetectedSleeveConstruction(str, Enum):
    SET_IN = "set_in"
    RAGLAN = "raglan"
    CAP = "cap"
    LONG = "long"
    TAPERED = "tapered"
    UNKNOWN = "unknown"


class StripeOrientation(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"
    NONE = "none"
    UNKNOWN = "unknown"


class StripeTermination(str, Enum):
    FULL_BODY = "full_body"
    CHEST_ONLY = "chest_only"
    FADE_OUT = "fade_out"
    PANEL_BOUNDED = "panel_bounded"
    UNKNOWN = "unknown"


class StripeSymmetry(str, Enum):
    CENTRE_ALIGNED = "centre_aligned"
    ASYMMETRIC = "asymmetric"
    UNKNOWN = "unknown"


class PatternFamily(str, Enum):
    """Detected pattern families — mapped later to Gamechanger procedural IDs."""

    SOLID = "solid"
    STRIPES = "stripes"
    HOOPS = "hoops"
    GRADIENT = "gradient"
    HALFTONE = "halftone"
    NOISE = "noise"
    HEXAGON = "hexagon"
    HONEYCOMB = "honeycomb"
    GEOMETRIC = "geometric"
    CARBON_WEAVE = "carbon_weave"
    BRUSH = "brush"
    WAVE = "wave"
    DIAGONAL_FADE = "diagonal_fade"
    CAMOUFLAGE = "camouflage"
    CHEVRON = "chevron"
    UNKNOWN = "unknown"


class PanelRole(str, Enum):
    BODY = "body"
    SLEEVES = "sleeves"
    COLLAR = "collar"
    CUFFS = "cuffs"
    SHOULDERS = "shoulders"
    SIDE_PANELS = "side_panels"


class BrandingRegionKind(str, Enum):
    """Branding is exclusion-only — never projected into Design Specification."""

    BADGE = "badge"
    MANUFACTURER = "manufacturer"
    SPONSOR = "sponsor"
    SLEEVE_SPONSOR = "sleeve_sponsor"
    COMPETITION_PATCH = "competition_patch"
    RETAIL_LABEL = "retail_label"
    PLAYER_NAME = "player_name"
    PLAYER_NUMBER = "player_number"
    WATERMARK = "watermark"
    PHOTOGRAPHER_OVERLAY = "photographer_overlay"
    OTHER = "other"


class RecognitionStatus(str, Enum):
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"
    REVIEWED = "reviewed"
    APPLIED = "applied"
