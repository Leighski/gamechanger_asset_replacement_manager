# Analysis Results Format

**Schema version:** `1.0`  
**Storage path:** `vision/analyses.json`

## Archive structure

```json
{
  "schema_version": "1.0",
  "analyses": [ /* VisionAnalysisResult[] */ ]
}
```

Multiple entries may share the same `image_id`. Analyses are append-only.

## VisionAnalysisResult

| Field | Type | Description |
|-------|------|-------------|
| `analysis_id` | string | Unique run identifier |
| `image_id` | string | Reference image ID |
| `image_filename` | string | Original filename |
| `created_at` | ISO datetime | UTC timestamp |
| `engine_version` | string | Vision Engine build |
| `status` | enum | Complete / Failed / Pending |
| `review_status` | enum | Pending Review / Accepted / Rejected / Partially Accepted |
| `shirt_detection` | object | Bounding box, outline, confidence |
| `colours` | array | Six colour measurements |
| `regions` | array | Named polygons |
| `shapes` | object | Proportional measurements |
| `patterns` | object | Coverage, density, orientation, frequency |
| `warnings` | string[] | Operator alerts |
| `suggested_mappings` | array | Design Spec field suggestions |
| `performance` | object | Timing and resource metrics |
| `confidence_summary` | object | Named confidence scores |

## Suggested mapping

```json
{
  "mapping_id": "a1b2c3d4e5f6",
  "design_spec_field": "primary_colour",
  "suggested_value": "#69B3E7",
  "confidence": 96.4,
  "source_measurement": "Primary Colour",
  "accepted": false
}
```

Mappings are applied to the Design Specification only when the operator accepts them via the Analysis Review screen.
