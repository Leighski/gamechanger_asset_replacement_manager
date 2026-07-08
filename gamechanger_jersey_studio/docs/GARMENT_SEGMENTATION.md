# Garment Segmentation — Phase 1B

**Package:** `services/garment_recognition/`  
**Contract section:** `GarmentRecognitionContract.segmentation`

## Objective

Given a single uploaded front-view football shirt image, identify the **physical construction** of the shirt.

This phase does **not** recognise colours, stripes, or patterns.

## Pipeline position

```
Upload Image
    ↓
Garment Segmentation   ← Phase 1B
    ↓
Garment Recognition Contract
    ↓
(Designer inspects overlay)
    ↓
Colour / Stripe / … recognition (later — consumes segmented regions)
```

## Detected regions

| Region ID | Meaning |
|-----------|---------|
| `shirt_boundary` | Garment silhouette |
| `background` | Non-garment pixels |
| `collar` | Neck opening band |
| `left_sleeve` / `right_sleeve` | Sleeve construction |
| `main_body` | Central torso |
| `left_shoulder` / `right_shoulder` | Shoulder bands |
| `left_cuff` / `right_cuff` | Cuff bands (when present) |
| `left_side_panel` / `right_side_panel` | Side panels (optional) |

Each `SegmentedRegion` carries:

- `present` (DetectedProperty)
- `confidence` / `needs_review`
- `bounding_box` (normalised)
- `polygon` (normalised)
- optional `mask_rle` absolute spans

## Exclusions

Branding and overlays are stored only on `contract.branding.exclusions`:

- Badge, manufacturer, sponsor, sleeve sponsor, competition patches
- Player name / number, watermark, photographer overlay

**Never projected into Design Specification.**

Phase 1B uses geometric **priors** inside the shirt bbox (typical kit placement). Later builds can refine with feature detectors; the contract shape stays the same.

## Future consumers

Later modules must analyse **segmented regions**, not the whole image:

```python
from services.garment_recognition import analysis_mask_for_region, SegmentationRegionId

mask = analysis_mask_for_region(contract, SegmentationRegionId.MAIN_BODY, exclude_branding=True)
```

## Visual review

```python
from services.garment_recognition import segment_shirt, render_segmentation_overlay

result = segment_shirt(image)
overlay = render_segmentation_overlay(image, result.contract)
```

Overlay shows garment outline, collar/sleeves/panels, and exclusion regions.

## Architectural rules

1. Populates the Recognition Contract only.
2. Never calls the renderer.
3. Independently testable (`tests/test_garment_segmentation.py`).
4. Branding remains exclusion-only.
