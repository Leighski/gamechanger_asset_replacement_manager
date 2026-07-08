# Suggestion Format

**Schema:** part of `interpretation/results.json`

## InterpretationSuggestion

| Field | Type | Description |
|-------|------|-------------|
| `suggestion_id` | string | Unique identifier |
| `target_field` | string | Design Specification field name |
| `current_value` | string | Value before acceptance |
| `proposed_value` | string | AI / rule recommended value |
| `confidence` | float | 0–100% |
| `confidence_band` | enum | High / Medium / Low |
| `reasoning` | string | Human-readable explanation |
| `source_measurements` | string[] | Vision measurements used |
| `ai_provider` | string | Provider that generated suggestion |
| `created_at` | ISO datetime | UTC timestamp |
| `status` | enum | Pending / Accepted / Rejected / Modified |
| `operator_value` | string | Edited value if modified before acceptance |

## Example

```json
{
  "suggestion_id": "a1b2c3d4e5f6",
  "target_field": "collar_style",
  "current_value": "",
  "proposed_value": "v-neck",
  "confidence": 88.5,
  "confidence_band": "Medium",
  "reasoning": "Measured neck opening width ratio (0.245) and collar depth most closely match the Gamechanger V-Neck catalogue entry.",
  "source_measurements": ["neck_opening_width_ratio", "collar_position_y"],
  "ai_provider": "offline",
  "status": "Pending"
}
```

## Operator feedback

Decisions are recorded in `InterpretationArchive.feedback` for future analytics (no auto-retraining in this build).
