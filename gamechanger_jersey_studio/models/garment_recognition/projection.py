"""Project a reviewed Garment Recognition Contract into Design Specification.

This is the ONLY allowed path from recognition to rendering.

Hard rules:
  * Branding exclusions are never written to Design Specification.
  * Collar always maps to the approved Gamechanger V-neck family.
  * Recognition modules must not call the renderer.
"""

from __future__ import annotations

from typing import Any

from models.design_specification import DesignSpecification
from models.garment_recognition.contract import GarmentRecognitionContract
from models.garment_recognition.enums import PatternFamily, StripeOrientation
from models.garment_recognition.mapping import (
    GAMECHANGER_PRODUCTION_TEMPLATE_ID,
    assert_collar_is_supported,
    map_collar,
    map_pattern_family,
    map_sleeve,
    map_stripe_orientation,
)

# Fields that recognition may populate on Design Specification.
# Branding paths and enable_branding_graphics are intentionally absent.
RECOGNITION_PROJECTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "primary_colour",
        "secondary_colour",
        "third_colour",
        "sleeve_colour",
        "collar_colour",
        "trim_colour",
        "pattern",
        "pattern_scale",
        "pattern_rotation",
        "pattern_opacity",
        "sleeve_style",
        "collar_style",
        "stripe_orientation",
        "stripe_count",
        "stripe_width",
        "stripe_gap",
        "stripe_colour",
        "stripe_termination",
        "stripe_symmetry",
        "stripe_centre_aligned",
    }
)

BRANDING_SPEC_FIELDS: frozenset[str] = frozenset(
    {
        "player_name",
        "squad_number",
        "club_badge_path",
        "manufacturer_logo_path",
        "sponsor_logo_path",
        "custom_graphics_path",
        "enable_branding_graphics",
    }
)


def _hex_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _mapped_or_detected_hex(prop) -> str | None:
    return _hex_or_none(prop.mapped) or _hex_or_none(
        str(prop.detected) if prop.detected is not None else None
    )


def _float_mapped(prop, default: float | None = None) -> float | None:
    if prop.mapped is not None and prop.mapped != "":
        try:
            return float(prop.mapped)
        except ValueError:
            pass
    if prop.detected is not None:
        try:
            return float(prop.detected)
        except (TypeError, ValueError):
            pass
    return default


def _int_mapped(prop, default: int | None = None) -> int | None:
    if prop.mapped is not None and prop.mapped != "":
        try:
            return int(float(prop.mapped))
        except ValueError:
            pass
    if prop.detected is not None:
        try:
            return int(prop.detected)
        except (TypeError, ValueError):
            pass
    return default


def build_design_spec_updates(contract: GarmentRecognitionContract) -> dict[str, Any]:
    """Derive Design Spec field updates from a recognition contract.

    Returns only recognition-projectable fields. Never includes branding.
    """
    updates: dict[str, Any] = {}

    # --- Colours ---
    primary = _mapped_or_detected_hex(contract.colours.primary)
    secondary = _mapped_or_detected_hex(contract.colours.secondary)
    accent = _mapped_or_detected_hex(contract.colours.accent)
    trim = _mapped_or_detected_hex(contract.colours.trim)
    if primary:
        updates["primary_colour"] = primary
    if secondary:
        updates["secondary_colour"] = secondary
    if accent:
        updates["third_colour"] = accent
    if trim:
        updates["trim_colour"] = trim

    sleeve_colour = _mapped_or_detected_hex(contract.sleeves.colour) or primary
    if sleeve_colour:
        updates["sleeve_colour"] = sleeve_colour

    collar_colour = _mapped_or_detected_hex(contract.collar.colour) or primary
    if collar_colour:
        updates["collar_colour"] = collar_colour

    # --- Collar (always V-neck family) ---
    collar_id = contract.collar.mapped_collar_id.mapped
    if not collar_id and contract.collar.detected_style.detected is not None:
        collar_id = map_collar(contract.collar.detected_style.detected)
    if not collar_id:
        collar_id = map_collar(None)
    updates["collar_style"] = assert_collar_is_supported(collar_id)

    # --- Sleeves ---
    sleeve_id = contract.sleeves.mapped_sleeve_id.mapped
    if not sleeve_id and contract.sleeves.construction.detected is not None:
        sleeve_id = map_sleeve(contract.sleeves.construction.detected)
    if sleeve_id:
        updates["sleeve_style"] = sleeve_id

    # --- Pattern / stripes ---
    stripes_present = bool(contract.stripes.present.detected)
    pattern_id = contract.patterns.mapped_pattern_id.mapped
    if not pattern_id and contract.patterns.family.detected is not None:
        pattern_id = map_pattern_family(contract.patterns.family.detected)

    if stripes_present:
        orientation = contract.stripes.orientation.detected
        if orientation is None:
            orientation = StripeOrientation.VERTICAL
        stripe_pattern = map_stripe_orientation(orientation)
        # Stripe structure wins over generic pattern family when stripes are present.
        if (
            contract.patterns.family.detected in (None, PatternFamily.STRIPES, PatternFamily.HOOPS, PatternFamily.UNKNOWN)
            or not pattern_id
        ):
            pattern_id = stripe_pattern

        count = _int_mapped(contract.stripes.count)
        width = _float_mapped(contract.stripes.width)
        gap = _float_mapped(contract.stripes.gap)
        stripe_colour = _mapped_or_detected_hex(contract.stripes.colour)
        if orientation is not None:
            updates["stripe_orientation"] = orientation.value
        if count is not None:
            updates["stripe_count"] = count
        if width is not None:
            updates["stripe_width"] = width
        if gap is not None:
            updates["stripe_gap"] = gap
        if stripe_colour:
            updates["stripe_colour"] = stripe_colour
        if contract.stripes.termination.detected is not None:
            updates["stripe_termination"] = contract.stripes.termination.detected.value
        if contract.stripes.symmetry.detected is not None:
            updates["stripe_symmetry"] = contract.stripes.symmetry.detected.value
        if contract.stripes.centre_aligned.detected is not None:
            updates["stripe_centre_aligned"] = bool(contract.stripes.centre_aligned.detected)

        # Derive pattern_scale from stripe geometry when available (renderer already consumes scale).
        if width is not None and width > 0:
            updates["pattern_scale"] = max(0.1, min(5.0, float(width)))

    if pattern_id:
        updates["pattern"] = pattern_id

    scale = _float_mapped(contract.patterns.scale)
    if scale is not None and "pattern_scale" not in updates:
        updates["pattern_scale"] = max(0.1, min(5.0, scale))
    rotation = _float_mapped(contract.patterns.rotation)
    if rotation is not None:
        updates["pattern_rotation"] = max(-360.0, min(360.0, rotation))
    opacity = _float_mapped(contract.patterns.opacity)
    if opacity is not None:
        updates["pattern_opacity"] = max(0.0, min(1.0, opacity))

    # Template identity is recorded on the contract; Design Spec does not yet
    # carry template_id — garment template remains the single production default.
    _ = GAMECHANGER_PRODUCTION_TEMPLATE_ID

    # Absolute branding firewall.
    for banned in BRANDING_SPEC_FIELDS:
        updates.pop(banned, None)

    # Drop anything outside the allow-list.
    return {key: value for key, value in updates.items() if key in RECOGNITION_PROJECTABLE_FIELDS}


def apply_contract_to_design_spec(
    contract: GarmentRecognitionContract,
    spec: DesignSpecification | None = None,
    *,
    only_confident: bool = False,
) -> DesignSpecification:
    """Create or update a Design Specification from a recognition contract.

    Parameters
    ----------
    only_confident:
        When True, skip properties currently flagged ``needs_review``.
        Designer review remains responsible for accepting low-confidence values.
    """
    base = spec or DesignSpecification()
    updates = build_design_spec_updates(contract)

    if only_confident:
        review_keys = {item.property_key for item in contract.properties_needing_review()}
        # Map summary keys to spec fields conservatively — leave reviewed fields alone.
        guarded: dict[str, Any] = {}
        key_to_field = {
            "colours.primary": "primary_colour",
            "colours.secondary": "secondary_colour",
            "colours.accent": "third_colour",
            "colours.trim": "trim_colour",
            "sleeves.colour": "sleeve_colour",
            "collar.colour": "collar_colour",
            "collar.mapped": "collar_style",
            "sleeves.mapped": "sleeve_style",
            "patterns.mapped": "pattern",
            "patterns.scale": "pattern_scale",
            "patterns.rotation": "pattern_rotation",
            "stripes.count": "stripe_count",
            "stripes.width": "stripe_width",
            "stripes.gap": "stripe_gap",
            "stripes.colour": "stripe_colour",
            "stripes.orientation": "stripe_orientation",
            "stripes.termination": "stripe_termination",
            "stripes.symmetry": "stripe_symmetry",
        }
        blocked_fields = {
            key_to_field[key] for key in review_keys if key in key_to_field
        }
        for field, value in updates.items():
            if field not in blocked_fields:
                guarded[field] = value
        updates = guarded

    # Ensure branding stays cleared / untouched by recognition application.
    return base.model_copy(update=updates)


def assert_no_branding_leak(updates: dict[str, Any]) -> None:
    """Raise if any branding Design Spec field appears in a projection dict."""
    leaked = sorted(BRANDING_SPEC_FIELDS.intersection(updates))
    if leaked:
        raise ValueError(f"Branding must not project into Design Specification: {leaked}")
