# Catalogue Format — Design Specification

Catalogues provide controlled vocabularies for construction, pattern, effects, and output fields. They are loaded from JSON at startup — never hard-coded in application logic.

**Location:** `config/catalogues/`

---

## Standard catalogue file

```json
{
  "catalogue_version": "1.0",
  "category": "collars",
  "items": [
    {
      "id": "crew",
      "label": "Crew Neck",
      "description": "Classic round crew collar"
    }
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `catalogue_version` | yes | Schema version |
| `category` | yes | Category identifier |
| `items` | yes | Array of catalogue entries |

### Item fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Stable identifier stored in design specification |
| `label` | yes | Human-readable display name |
| `description` | no | Tooltip / documentation text |

---

## Effects catalogue

Effects use a grouped structure in `effects.json`:

```json
{
  "catalogue_version": "1.0",
  "category": "effects",
  "shadows": [ { "id": "...", "label": "...", "description": "..." } ],
  "lighting": [ ... ],
  "textures": [ ... ]
}
```

---

## Available catalogues (Build 004)

| File | Category |
|------|----------|
| `collars.json` | Collar styles |
| `patterns.json` | Pattern types |
| `sleeves.json` | Sleeve styles |
| `materials.json` | Material styles |
| `effects.json` | Shadow, lighting, texture |
| `output_profiles.json` | Output profiles |

---

## Loading

```python
from services.design_catalogue_service import load_catalogues

catalogues = load_catalogues()
```

Future work packages will expand catalogue entries without code changes.
