# Region Detection

## Detected regions

| Region | Purpose |
|--------|---------|
| Collar | Neckline band |
| Sleeves | Left and right sleeve areas |
| Body | Central torso |
| Shoulders | Upper shoulder band |
| Side Panels | Left and right vertical panels |
| Trim | Lower hem band |

## Representation

Each region is a `RegionPolygon`:

```json
{
  "name": "Collar",
  "points": [[224, 100], [416, 100], [416, 136], [224, 136]],
  "confidence": 83.5
}
```

Points are in **full image coordinates** (not crop-relative).

## Method (Phase 1)

Regions are estimated from shirt bounding-box geometry using fixed proportional rectangles. Confidence scales with shirt detection confidence.

Future builds will refine polygons using mask contours and pattern analysis.
