# Learning Rule Specification

## Rule model

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | string | Unique ID (e.g. `LR_COVENTRY_COLLAR`) |
| `title` | string | Human-readable name |
| `description` | string | Why this rule exists |
| `category` | enum | Club, Manufacturer, Competition, Template, Pattern, Collar, Sleeve, Trim, Colour, Output Profile |
| `triggers` | object | Conditions that must match |
| `action` | object | Advisory recommendation |
| `confidence` | float | Rule confidence 0–100 |
| `status` | enum | Draft, Approved, Disabled |
| `usage_count` | int | Times rule matched |
| `created_by` | string | Operator or "Learning Mode" |

## Trigger conditions

```json
{
  "field_name": "collar_style",
  "club": "Coventry City",
  "manufacturer": "",
  "competition": "",
  "season": "",
  "kit_type": "",
  "template_id": "",
  "pattern": "",
  "original_value": "crew"
}
```

Empty fields are wildcards.

## Recommended action

```json
{
  "target_field": "collar_style",
  "recommended_value": "v-neck",
  "catalogue_component": "COLLAR_0002",
  "advisory_note": "Based on 8 similar corrections",
  "confidence_boost": 5.0
}
```

`confidence_boost` adds to AI suggestion confidence (max 100) — advisory only.

## Learning Event

Recorded when operator modifies a suggestion before accepting:

- Project metadata (club, competition, season, manufacturer, kit type)
- `original_ai_value` / `final_operator_value`
- Confidence, vision measurements, template, operator, timestamp

## Rule lifecycle

1. **Draft** — created manually or from pattern detection
2. **Approved** — evaluated by Rule Engine
3. **Disabled** — retained but not evaluated
