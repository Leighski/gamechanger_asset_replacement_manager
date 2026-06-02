# Team registry migration guide

## Canonical source of truth

| Asset | Location |
|-------|----------|
| Registry JSON | `kiron_export_pipeline/config/team_registry.json` |
| Shared Python package | `Inspired_Delivery_Generator/team_registry/` |
| Service API | `team_registry.service.TeamRegistryService` |
| Normalization | `team_registry.normalize` |

## Legacy `TEAM_MAP` (staged — do not remove yet)

| Location | Status |
|----------|--------|
| `kiron_export_pipeline/config/mappings.py` → `TEAM_MAP` | **LEGACY** fallback (26 English PL clubs) |
| `team_registry/legacy_team_map.py` → `LEGACY_TEAM_MAP` | Mirror for shared package (keep in sync) |
| `Kiron_inspire_export_pipeline_v4i.py` (and v4f–v4h) | **LEGACY** inline duplicate — standalone scripts |
| `workflows/metadata/templating.py` | Uses shared `resolve_team_abbreviation_with_bridge(..., legacy_team_map=TEAM_MAP)` |

### Resolution order (Kiron + Inspired)

1. Known 3-letter registry abbreviation (passthrough)
2. `team_registry.json` lookup (alias enrichment when enabled)
3. `TEAM_MAP` / `LEGACY_TEAM_MAP` fallback
4. Preserve original value + `unknown_teams.csv` (Inspired) or unresolved report (Kiron)

## Consumers

| Tool | Integration |
|------|-------------|
| Kiron metadata pipeline | `services/team_registry_service.py` re-exports shared service; templating uses shared normalize |
| Inspired Delivery Generator | `normalize_inspired_cell` → 3-letter team columns; filename QC |
| Replacement analysis | Filename matching; see `replacement_service.py` module doc |
| Frame alignment QC | Unrelated to team names |

## Staged migration checklist

- [x] Extract shared `team_registry` package
- [x] Kiron shim re-export
- [x] Inspired metadata exports 3-letter codes
- [ ] Generate `TEAM_MAP` from registry at build time (optional)
- [ ] Retire inline `TEAM_MAP` in `Kiron_inspire_export_pipeline_v4*.py`
- [ ] Remove duplicate `LEGACY_TEAM_MAP` once Kiron `mappings.py` imports from shared module only

## Settings (Kiron)

`config/user_settings.json`:

```json
"team_registry": {
  "registry_path": "",
  "preflight_enabled": true,
  "enrichment_enabled": false
}
```

Inspired standalone always uses **alias enrichment** for export normalization (`allow_alias_enrichment=True`).
Kiron preflight keeps safe-mode unless `enrichment_enabled` is set to `true`.
