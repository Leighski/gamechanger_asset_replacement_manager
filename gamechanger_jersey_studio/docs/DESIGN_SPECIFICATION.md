# Design Specification — Gamechanger Jersey Studio

**Version:** 1.0.0-alpha.4 · Build 004  
**Schema version:** 1.0

The Design Specification is the **canonical data model** for every football jersey in Jersey Studio. All future subsystems — AI analysis, PSD rendering, exports, and validation — must read from and write to this model. Nothing should read directly from images or PSD layers.

---

## Storage

Design specifications are stored inside every `.gjs` project package at:

```
design/specification.json
```

Projects created before Build 004 do not include this file. On open, a specification is created automatically from `manifest.json` and written on next save.

---

## Schema

### Project Information

| Field | Type | Description |
|-------|------|-------------|
| `club` | string | Club name |
| `competition` | string | Competition |
| `season` | string | Season |
| `kit_type` | enum | Home, Away, Third, Goalkeeper, Women's |
| `manufacturer` | string | Kit manufacturer |

### Colours

| Field | Type |
|-------|------|
| `primary_colour` | string (hex) |
| `secondary_colour` | string (hex) |
| `third_colour` | string (hex) |
| `sleeve_colour` | string (hex) |
| `collar_colour` | string (hex) |
| `trim_colour` | string (hex) |

### Pattern

| Field | Type | Constraints |
|-------|------|-------------|
| `pattern` | catalogue id | Must exist in patterns catalogue |
| `pattern_scale` | float | 0.1 – 5.0 |
| `pattern_rotation` | float | -360 – 360 |
| `pattern_opacity` | float | 0.0 – 1.0 |

### Construction

| Field | Type |
|-------|------|
| `sleeve_style` | catalogue id (sleeves) |
| `collar_style` | catalogue id (collars) |
| `trim_style` | string |
| `material_style` | catalogue id (materials) |

### Effects

| Field | Type |
|-------|------|
| `shadow_style` | catalogue id (shadows) |
| `lighting_style` | catalogue id (lighting) |
| `texture_style` | catalogue id (textures) |

### Output

| Field | Type |
|-------|------|
| `output_profile` | Gamechanger Broadcast, Authentic, Editorial, Fantasy |

### Meta

| Field | Type |
|-------|------|
| `validation_status` | Not started, Pending, Passed, Failed |
| `operator_notes` | string |

---

## Behaviour

- **Immediate persistence intent:** every field change marks the project dirty; autosave and manual save write to `.gjs`.
- **Manifest sync:** changes to club, competition, season, kit type, and output profile update `manifest.json`.
- **Undo/redo:** every modification is a reversible command (Edit → Undo/Redo).
- **History:** every change records timestamp, property, old value, new value, and user.

---

## Example

See `examples/Coventry_City_Home_2026.gjs` for a completed specification.

---

## Implementation

| Component | Path |
|-----------|------|
| Model | `models/design_specification.py` |
| Service | `services/design_specification_service.py` |
| Validation | `services/design_spec_validation.py` |
| Completion | `services/design_spec_completion.py` |
| Undo/redo | `services/design_spec_undo.py` |
| Catalogues | `services/design_catalogue_service.py` |
| Editor UI | `ui/widgets/design_specification_editor.py` |
