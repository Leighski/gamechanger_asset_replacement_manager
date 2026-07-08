# Regression Repair Report — New Project Crash (GJS-014-R1)

**Date:** 2026-06-30  
**Version:** 1.0.0-rc.1  
**Scope:** Regression repair only — no architectural changes

## Why NewProjectWizard Became Undefined

`NewProjectWizard` was **not deleted or renamed**. The class remains at `ui/dialogs/new_project_wizard.py` and is fully functional.

The regression was caused by a **missing import** in `ui/main_window.py`. During the GJS-014 Validation panel work, `main_window.py` was updated to use `ValidationPanel` and other imports were added, but the existing import line for `NewProjectWizard` was dropped:

```python
from ui.dialogs.new_project_wizard import NewProjectWizard  # was missing
```

`_new_project()` continued to reference `NewProjectWizard` at runtime, producing:

```
NameError: name 'NewProjectWizard' is not defined
```

This is a classic **import regression** — the implementation survived; the wiring did not.

## What Was Repaired

| Item | Fix |
|------|-----|
| **New Project crash** | Restored `from ui.dialogs.new_project_wizard import NewProjectWizard` |
| **Tools → Validate Project** | Was connected to no callback. Wired to `_validate_project()` (navigates to Validation tab) |
| **Tools → Generate Reports** | Replaced inline lambda with `_open_production_reports()` for explicit callback validation |
| **Startup validation** | Added `ui/action_validation.py` and `MainWindow._validate_menu_actions()` — verifies 18 menu callbacks exist before the window is shown; logs errors and disables broken actions |
| **Regression tests** | Added `tests/test_ui_navigation.py` (15 tests) covering File, Tools, Help, and sidebar navigation |

No changes were made to `NewProjectWizard` itself, the project system, or `.gjs` format.

## Other Broken Menu Actions Discovered

| Action | Status before fix | Resolution |
|--------|-------------------|------------|
| **Tools → Validate Project** | No `triggered` connection | Connected to `_validate_project` |
| **Tools → Generate Reports** | Lambda only (not auditable) | Named method `_open_production_reports` |
| **Edit → Cut/Copy/Paste/Preferences** | Intentionally disabled, no handlers | No change (disabled placeholders) |
| **Project → Information/Settings/Export** | Intentionally disabled | No change |
| **Window → Zoom** | Intentionally disabled | No change |

All other connected actions (`New`, `Open`, `Save`, `Save As`, `Close`, `Duplicate`, `Archive`, `Delete`, `Quit`, `Minimize`, `Documentation`, `Release Notes`, `About`, `Render PSD`, `Batch Processing`, `Undo`, `Redo`) reference existing methods.

## Preventative Measures

1. **`ui/action_validation.py`** — reusable validator that checks `getattr(owner, method_name)` is callable; disables the QAction and logs to `application.log` if not.

2. **`MainWindow._validate_menu_actions()`** — called during `__init__` before the window is displayed. The application continues running even if an action is disabled.

3. **`tests/test_ui_navigation.py`** — automated regression suite exercising:
   - File → New Project, Open, Save, Save As
   - Sidebar → Libraries, Learning, Production, Settings
   - Help → About
   - Tools → Validate Project, Generate Reports

4. **`test_main_window_instantiates`** (existing) — confirms MainWindow builds without error.

## Test Results

Run: `pytest tests/test_ui_navigation.py -q`

All navigation regression tests should pass alongside the full suite (218+ tests).

## Recommendation

Before RC1 validation, run the full test suite after any UI import changes. The startup validator will catch missing method names at launch; the navigation test suite catches missing imports like `NewProjectWizard`.

---

## ReferenceImageRecord Compatibility (2026-06-30)

### Root cause

`ReferenceImageRecord` was refactored in GJS-005 to use `tags` (list of `ImageCategory` values) instead of the legacy `view_type` field, and `import_date` instead of `imported_at`. Two production services still referenced the old field names:

| File | Legacy fields used |
|------|-------------------|
| `services/production/replay_service.py` | `view_type` |
| `services/production/audit_service.py` | `view_type`, `imported_at` |

### Repairs

- Added `ReferenceImageRecord` model API: `category_labels()`, `primary_category_label()`, `import_timestamp()`, `replay_entry()`, `audit_details()`
- Added `@model_validator` to migrate legacy JSON: `view_type`, `image_category`, `reference_type`, `category` → `tags`; `imported_at` → `import_date`
- Refactored `ReplayService` to use model API with per-step try/except — never raises
- Fixed `ProductionAuditService` to use model API with per-image error handling
- `ValidationPanel.refresh()` now called after vision analysis completes
- Added `tests/test_replay_compatibility.py` (14 tests)

### Audit of `.view_type` / `ReferenceImageRecord` consumers

| Location | Status |
|----------|--------|
| `replay_service.py` | **Fixed** — uses `replay_entry()` |
| `audit_service.py` | **Fixed** — uses `import_timestamp()`, `audit_details()` |
| `reference_image_card.py` | OK — uses `tags`, `import_date` |
| `reference_image_service.py` | OK — uses current schema |
| `reference_image_validation.py` | OK — uses `tags` |
| Docs (`PROJECT_ARCHITECTURE.md`) | Historical reference only |

---

## TemplateProjectSettings Compatibility (2026-06-30)

### Root cause

`TemplateProjectSettings` uses **`active_template_id`** (GJS-010), not `template_id`. `ReplayService._append_template()` accessed `template_settings.template_id` in its guard condition — outside any try/except — causing `AttributeError` when `validation.refresh()` ran after Vision Analysis.

### Repairs

- Added optional `template_version` field to `TemplateProjectSettings`
- Added model API: `template_identifier()`, `template_version_label()`, `replay_details()`, `audit_details()`
- Legacy JSON migration: `template_id` → `active_template_id`; `version` → `template_version`
- `ReplayService` always emits a Template Selection step via model API; uses `Unknown Template` when settings are absent
- No warnings for missing optional template metadata
- Extended `tests/test_replay_compatibility.py` (+7 template tests)

### Audit of `TemplateProjectSettings` consumers

| Location | Status |
|----------|--------|
| `replay_service.py` | **Fixed** — uses `template_identifier()`, `replay_details()` |
| `interpretation_service.py` | OK — `active_template_id` |
| `template_manager_service.py` | OK — `active_template_id` |
| `audit_service.py` | OK — template ID passed from render pipeline |
| `production/queue_service.py` | OK — via `template_manager.active_template_id()` |

