# Confidence Model

Every Vision Engine measurement includes a confidence score from **0.0 to 100.0**. No value is emitted without confidence.

## Principles

- Confidence reflects **measurement certainty**, not creative interpretation.
- Low confidence triggers operator review (e.g. shirt detection &lt; 70%).
- The engine does not guess — low confidence means "cannot measure reliably".

## Calculation sources

| Signal | Function | Use |
|--------|----------|-----|
| Sample size | `confidence_from_sample_size` | Colour clusters, mask pixels |
| Variance | `confidence_from_variance` | Colour cluster spread |
| Area ratio | `confidence_from_area_ratio` | Shirt bounding box vs image |
| Edge strength | `confidence_from_edge_strength` | Pattern edge detection |
| Combination | `combine_confidences` | Multi-signal aggregation |

## Summary object

`VisionAnalysisResult.confidence_summary` is a flat dictionary, e.g.:

```json
{
  "Shirt Detection": 87.2,
  "Primary Colour": 96.4,
  "Collar Region": 83.5,
  "Pattern Density": 81.0
}
```

`overall_confidence()` returns the arithmetic mean of summary values.
