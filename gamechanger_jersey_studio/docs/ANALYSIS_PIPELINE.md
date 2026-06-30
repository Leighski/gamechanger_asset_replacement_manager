# Analysis Pipeline

## Stages

1. **Image Loader** — Read reference bytes; apply EXIF orientation; produce RGB array. Original file is never modified.
2. **Image Normalisation** — Clip to sRGB working copy (`uint8` numpy array).
3. **Shirt Detection** — Foreground mass heuristic; bounding box, outline polygon, confidence. Low confidence sets `requires_review`.
4. **Background Removal** — Internal boolean mask separating shirt pixels from background. Not persisted.
5. **Colour Analysis** — Six named colours with RGB, HSV, LAB, hex, catalogue match, confidence.
6. **Region Detection** — Collar, sleeves, body, shoulders, side panels, trim as polygons in image coordinates.
7. **Shape Analysis** — Collar position, sleeve length, neck opening, shoulder width, body proportions (ratios only).
8. **Pattern Analysis** — Coverage %, density, orientation°, frequency (no pattern identification).
9. **Confidence Summary** — Aggregated per-measurement scores for operator review.
10. **Suggested Mappings** — Optional Design Specification field suggestions (applied only after approval).

## Performance metrics

Each run records:

- Processing time (ms)
- Image dimensions
- Peak memory (MB)
- CPU time (ms)
- GPU usage (placeholder: "Not available")

## Failure handling

Failures raise `VisionEngineError`. The reference image `analysis_status` is set to `Failed` and a history event is recorded.
