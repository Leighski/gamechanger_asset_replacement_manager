# Architecture — Gamechanger Jersey Studio Build 001

## Design intent

Build 001 is the **permanent production foundation**, not a prototype. Every future subsystem (design tools, libraries, validation, rendering) will plug into this structure rather than replacing it.

## Layering

| Layer | Responsibility |
|-------|----------------|
| `app/` | Entry point, lifecycle controller, startup/shutdown |
| `core/` | Cross-cutting utilities with no business logic |
| `models/` | Pydantic schemas for persisted and exchanged data |
| `services/` | Generic desktop application managers |
| `ui/` | PySide6 views only — no jersey logic |

## Core managers

- **SettingsManager** — JSON persistence via Pydantic validation
- **LoggingManager** — Loguru console + rotating file log
- **RecentProjectsManager** — bounded recent list stored in settings
- **ProjectsManager** — generic loaded/unloaded project state
- **VersionManager** — centralised version and platform metadata

None of these managers contain jersey-specific logic.

## UI shell

The main window is a three-column layout:

1. **Sidebar** — workspace navigation (Projects, Design, Libraries, etc.)
2. **Project Explorer** — centre panel (Build 001: empty state only)
3. **Preview Panel** — right panel (Build 001: unavailable state)

Navigation changes the status bar context label only. Feature pages will be added in later work packages as stacked views or dedicated controllers.

## Settings persistence

All settings are stored in `config/settings.json`:

- Theme
- Window size, position, maximised state
- Autosave interval
- Default project folder
- Recent projects

Window geometry is saved automatically on application close.

## Logging

Loguru writes to `logs/application.log` with rotation. Required lifecycle events are logged explicitly. `sys.excepthook` routes uncaught exceptions to the log.

## Error handling philosophy

The application should not terminate unexpectedly. Startup and main-window display are wrapped in try/except blocks. Fatal errors display a dialog and are logged.

## Technology choices

| Choice | Rationale |
|--------|-----------|
| Python 3.12 | Specified development version |
| PySide6 | Commercial-grade Qt desktop UI |
| Pydantic v2 | Validated settings and future domain models |
| Loguru | Simple, production-ready structured logging |
| pytest | Standard test runner for services layer |

## Extension points for GJS-002+

- Replace centre/right placeholder panels with view controllers per nav item
- Add `libraries/` content loaders without changing settings/logging
- Add project file format under `projects/` with `ProjectsManager` extensions
- Add report writers under `services/` writing to `reports/`
