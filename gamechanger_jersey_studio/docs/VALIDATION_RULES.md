# Validation Rules — Design Specification

Live validation runs on every field change. Results appear in the editor Validation panel and drive Project Explorer status icons.

---

## Rules

### Project Information

| Field | Rule |
|-------|------|
| `club` | Cannot be empty |
| `competition` | Cannot be empty |
| `season` | Cannot be empty |
| `manufacturer` | Cannot be empty |

### Colours

All six colour fields (`primary_colour`, `secondary_colour`, `third_colour`, `sleeve_colour`, `collar_colour`, `trim_colour`) **cannot be empty**.

### Pattern

| Field | Rule |
|-------|------|
| `pattern` | Must be selected; must exist in patterns catalogue |
| `pattern_opacity` | Must be between 0.0 and 1.0 inclusive |

### Construction

| Field | Rule |
|-------|------|
| `collar_style` | If set, must exist in collars catalogue |
| `sleeve_style` | If set, must exist in sleeves catalogue |
| `material_style` | If set, must exist in materials catalogue |

### Effects

| Field | Rule |
|-------|------|
| `shadow_style` | If set, must exist in effects/shadows catalogue |
| `lighting_style` | If set, must exist in effects/lighting catalogue |
| `texture_style` | If set, must exist in effects/textures catalogue |

---

## Status

| Condition | `validation_status` |
|-----------|---------------------|
| No issues | Passed |
| Errors present | Failed |
| Warnings only | Pending |

Validation status is written to both the design specification and project manifest.

---

## Configuration

Opacity limits are defined in `services/design_spec_validation.py`:

```python
PATTERN_OPACITY_MIN = 0.0
PATTERN_OPACITY_MAX = 1.0
```

Future builds may externalise limits to `config/validation_rules.json`.
