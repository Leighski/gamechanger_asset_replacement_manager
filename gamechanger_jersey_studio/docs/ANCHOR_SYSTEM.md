# Anchor System

## Purpose

Named anchor points inside PSD templates for future artwork positioning (badges, sponsors, numbers, names).

## Anchor schema

```json
{
  "anchor_id": "ANCHOR_BADGE",
  "name": "Badge Anchor",
  "role": "badge",
  "x": 0.5,
  "y": 0.22,
  "width": 0.08,
  "height": 0.08,
  "rotation_degrees": 0.0,
  "notes": "Chest badge centre"
}
```

Coordinates are **normalised** (0.0–1.0) relative to the jersey canvas.

## Standard roles

| Role | Purpose |
|------|---------|
| `collar` | Neck opening |
| `sleeve` | Sleeve placement |
| `badge` | Club crest |
| `sponsor` | Front sponsor block |
| `manufacturer_logo` | Manufacturer mark |
| `number` | Back number |
| `name` | Name bar |

## Broadcast v1 anchors

Eight anchors seeded in `config/templates/broadcast_v1/anchor_points.json`.

Validation warns when recommended roles are missing.
