# History Format — Design Specification Changes

Design Specification edits are recorded in `history.json` inside every `.gjs` package.

---

## Event type

```
Design Specification Changed
```

Enum: `HistoryEventType.DESIGN_SPEC_CHANGED`

---

## Entry structure

```json
{
  "timestamp": "2026-06-30T09:15:00+00:00",
  "event": "Design Specification Changed",
  "application_version": "1.0.0-alpha.4",
  "user": "Leigh",
  "details": "{\"property\": \"primary_colour\", \"old_value\": \"\", \"new_value\": \"#69B3E7\"}"
}
```

### Details JSON

| Field | Type | Description |
|-------|------|-------------|
| `property` | string | Field name that changed |
| `old_value` | any | Previous value (serialised) |
| `new_value` | any | New value (serialised) |

Enum values are stored as their string value (e.g. `"Home"`, `"Gamechanger Broadcast"`).

---

## Undo/redo

Undo and redo replay the same `apply_change` path with history recording enabled. The in-memory undo stack is cleared when a different project is opened.

---

## Logging

Every change is also written to `logs/application.log`:

```
Design Specification changed — primary_colour:  → #69B3E7 (user=Leigh)
```
