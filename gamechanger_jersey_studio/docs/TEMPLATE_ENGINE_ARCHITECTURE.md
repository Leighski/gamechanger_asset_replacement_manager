# Template Engine Architecture

## Overview

The PSD Template Engine is the permanent bridge between Jersey Studio and Gamechanger Photoshop templates. It does **not** edit PSD files — it indexes, maps, and validates template structure so the Render Engine can resolve catalogue components to PSD targets.

## Subsystem layout

```
services/template_engine/
├── manager.py              TemplateManager — registration & publishing
├── psd_loader.py           PSDTemplateLoader — read-only PSD analysis
├── layer_mapping.py        LayerMappingService — spec field → PSD layer rules
├── anchor_points.py        AnchorPointService — named placement anchors
├── smart_objects.py        SmartObjectService — Smart Object index
├── validator.py            TemplateValidator — mapping & structure validation
└── preview_generator.py    TemplatePreviewGenerator — preview thumbnails

services/template_manager_service.py   Project integration
config/templates/                        Template registry & mappings
```

## Multi-template design

Multiple templates coexist (Broadcast, Editorial, Social, Print, Women's, Goalkeeper). Projects reference **Template IDs** (`TEMPLATE_BROADCAST_0001`), never PSD filenames.

The Render Engine requests `PublishedTemplateMappings` from `TemplateManagerService` and does not know which PSD file is active.

## Data separation

| Asset | Storage | PSD modified? |
|-------|---------|---------------|
| Source PSD | `config/templates/{slug}/*.psd` | Never |
| Analysis | `analysis.json` | — |
| Layer mappings | `layer_mappings.json` | — |
| Anchor points | `anchor_points.json` | — |
| Project selection | `template/settings.json` in `.gjs` | — |

## Logging

- Template loaded
- PSD analysed
- Layer mapping created
- Validation complete
- Template selected
