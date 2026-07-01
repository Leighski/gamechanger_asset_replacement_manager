# Smart Object Workflow

## Principle

Smart Objects are replaced **in place** — contents are updated from catalogue assets without rasterising the parent PSD layer. Editability is preserved wherever `psd-tools` supports embedded Smart Object data.

## Data sources

1. **Template analysis** (`analysis.json`) — Smart Object IDs, layer names, dimensions
2. **Layer mappings** (`layer_mappings.json`) — `design_spec_field` → `psd_layer_name` + optional `smart_object_id`
3. **Component Library** — PNG assets for collar, sleeve, trim, material, pattern

## Replacement paths

`SmartObjectRenderService.replace_layer_content()` attempts:

1. **Native Smart Object** — `layer.smart_object.data = png_bytes` when the layer exposes embedded data
2. **Pixel layer fallback** — `layer.numpy = np.array(rgba_image)` for template layers that behave as editable pixel targets

The renderer never flattens Smart Object layers into static pixels at the PSD root.

## Mapped Smart Object fields

| Design Spec field | Typical target |
|-------------------|----------------|
| `collar_style` | Collar Smart Object |
| `sleeve_style` | Sleeve group layers |
| `trim_style` | Trim layer |
| `material_style` | Base material reference |
| `pattern` | Pattern Smart Object |

Component images may be colour-tinted before placement (e.g. collar uses `collar_colour`).

## Validation

Before export, the validator checks:

- Mapped layer names exist in the working PSD
- Smart Object IDs referenced in mappings appear in template analysis (warnings if not)
- Catalogue components resolve for `DESIGN_SPEC_CATALOGUE_FIELDS` only

Colour fields (`*_colour`) are validated separately and never treated as catalogue references.

## Operator workflow

1. Operator finalises Design Specification
2. Template Engine publishes mappings for the active template ID
3. Renderer loads catalogue assets and writes Smart Object contents
4. Layered PSD is saved with Smart Objects still editable in Photoshop
