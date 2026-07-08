# Garment Recognition Contract

**Phase:** 1A  
**Schema version:** 1.0  
**Package:** `models/garment_recognition/`

## Product mission

Gamechanger Jersey Studio recreates an uploaded football shirt as a clean, editable, production-quality Gamechanger jersey. Recognition is the primary workflow. Rendering is a downstream consumer of Design Specification only.

## Pipeline

```
Upload Image
    ↓
Garment Recognition (independently testable modules)
    ↓
Garment Recognition Contract
    ↓
Designer Review (confidence-gated)
    ↓
Design Specification   ← single source of truth for rendering
    ↓
Renderer
    ↓
Production Artwork
```

## Architectural rules

1. **Design Specification is the only interface between recognition and rendering.**
2. Recognition modules **populate the Contract** — they never call the renderer.
3. **Detect ≠ Map.** Detection describes the upload; mapping translates to supported Gamechanger equivalents.
4. **Branding is exclusion-only.** Badge, sponsor, manufacturer, and patch regions never enter Design Specification.
5. **Collar authority** is the approved Gamechanger V-neck family (`COLLAR_0002`). Unsupported collars are remapped, never reproduced.
6. **One production garment template** (`GARMENT_ENGLISH_FOOTBALL_BASE_0001`).
7. **Every recognition module must be independently testable** (no renderer, no UI, no Design Spec writer required).

## Downstream systems (unchanged)

Renderer · Production Template · Production Validation · Production Output · Visual QA · Fidelity Framework

These consume Design Specification. They do not read the Recognition Contract.

## Contract sections

| Section | Purpose |
|---------|---------|
| `garment` | Type, front view, template id |
| `segmentation` | Physical construction regions + masks (Phase 1B) |
| `collar` | Detected style → mapped V-neck |
| `sleeves` | Construction, colours → mapped sleeve id |
| `colours` | Primary, secondary, accent, trim |
| `panels` | Body, sleeves, collar, cuffs, shoulders, side panels |
| `patterns` | Family, scale, rotation → mapped pattern id |
| `stripes` | Structural geometry for procedural rebuild |
| `branding` | Exclusion regions only |

See also: [GARMENT_SEGMENTATION.md](GARMENT_SEGMENTATION.md).

## Confidence model

Every `DetectedProperty` carries:

| Field | Meaning |
|-------|---------|
| `detected` | What exists on the uploaded shirt |
| `mapped` | Supported Gamechanger equivalent |
| `confidence` | 0–100 |
| `needs_review` | True when below configurable threshold (default **85**) |

`GarmentRecognitionContract.detection_summary()` feeds the Design Detection Summary UI. Designers only review properties below the threshold.

## Projection

`build_design_spec_updates()` / `apply_contract_to_design_spec()` convert a reviewed contract into Design Specification fields.

Hard firewalls:

- `BRANDING_SPEC_FIELDS` are never projected
- Collar is forced through `assert_collar_is_supported()`
- Only `RECOGNITION_PROJECTABLE_FIELDS` may be written

## Module protocol

```python
class RecognitionModule(Protocol):
    module_id: RecognitionModuleId
    def analyze(self, context: RecognitionContext, contract: GarmentRecognitionContract) -> ModuleResult: ...
```

Modules receive `RecognitionContext` (image + metadata). They must not receive renderer services.

## Implementation order

1. ~~Garment Recognition Contract~~ (Phase 1A)  
2. ~~Garment Segmentation~~ (Phase 1B)  
3. Colour Recognition  
4. Stripe Recognition  
5. Sleeve Recognition  
6. Collar Recognition  
7. Pattern Recognition  
8. Branding Exclusion (refine priors → detectors)  

## Feature gate

Every new feature must answer: **Does this improve automatic recreation of a football shirt from an uploaded image?** If no, do not build it.
