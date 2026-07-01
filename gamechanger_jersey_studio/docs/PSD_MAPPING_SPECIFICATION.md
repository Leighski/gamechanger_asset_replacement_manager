# PSD Mapping Specification

## Purpose

Define how Design Specification fields map to PSD layers via configuration — no hard-coded mappings in code.

## Mapping rule schema

```json
{
  "mapping_id": "MAP_COLLAR",
  "design_spec_field": "collar_style",
  "component_category": "collars",
  "psd_layer_name": "Collar Smart Object",
  "psd_layer_id": "L0005",
  "smart_object_id": "SO0001",
  "layer_group": "Construction",
  "render_layer": "collar",
  "notes": "Collar component Smart Object"
}
```

## Field reference

| Field | Description |
|-------|-------------|
| `design_spec_field` | Design Specification property name |
| `component_category` | Component Library category (optional) |
| `psd_layer_name` | PSD layer name for validation |
| `psd_layer_id` | Stable ID from analysis |
| `smart_object_id` | Smart Object index ID |
| `render_layer` | Live Renderer layer ID for cross-reference |

## Example mappings (Broadcast v1)

| Design Spec | PSD Target |
|-------------|------------|
| `primary_colour` | Base Shirt |
| `collar_style` | Collar Smart Object |
| `sleeve_style` | Sleeves |
| `trim_style` | Trim |
| `pattern` | Pattern Smart Object |
| `texture_style` | Texture Overlay |
| `lighting_style` | Lighting group |
| `shadow_style` | Shadows group |

Configuration file: `config/templates/broadcast_v1/layer_mappings.json`
