# Vision Engine Architecture

**Build:** 1.0.0-alpha.6 (GJS-006)  
**Subsystem version:** `1.0.0-alpha.6`

## Purpose

The Vision Engine is a **measurement system**, not an AI interpretation system. It answers:

> What can be measured with confidence from a reference image?

It never modifies reference images or the Design Specification directly. Results are stored as `VisionAnalysisResult` objects for operator review.

## Module layout

```
services/vision/
├── image_loader.py          # Load bytes → numpy array, EXIF correction
├── image_normalisation.py   # sRGB working copy
├── shirt_detection.py       # Bounding box + outline + confidence
├── background_removal.py      # Temporary segmentation mask
├── colour_analysis.py         # Primary/secondary/accent/trim/collar/sleeve
├── region_detection.py        # Collar, sleeves, body, shoulders, panels, trim
├── shape_analysis.py          # Proportional measurements (no classification)
├── pattern_analysis.py        # Coverage, density, orientation, frequency
├── confidence.py              # Shared confidence utilities
└── pipeline.py                # VisionEngine orchestrator

models/vision_analysis.py      # Analysis result models (separate from Design Spec)
services/vision_analysis_service.py  # Project integration + operator approval
ui/widgets/vision_analysis_review.py # Analysis Review screen
```

## Separation of concerns

| Layer | Responsibility |
|-------|----------------|
| Vision services | Measure pixels; return values + confidence |
| `VisionAnalysisResult` | Immutable analysis output per run |
| `VisionAnalysisService` | Run pipeline, persist archive, history, approval flow |
| Analysis Review UI | Display results; Accept / Reject / Reanalyse |
| `DesignSpecificationService` | Updated **only** when operator accepts mappings |

## Persistence

Analyses are stored at `vision/analyses.json` inside the `.gjs` package. Multiple analyses per reference image are retained; previous runs are never overwritten.

## Workspace

Temporary processing data may use `vision_cache/` under the per-project workspace. Processed images are not permanently saved.
