# Project Architecture — GJS-002

## Principle

**Every piece of application data belongs to a project.** Build 002 introduces the project subsystem that all future modules must use.

## Components

| Component | Location | Role |
|-----------|----------|------|
| Project models | `models/project.py` | Pydantic schemas for manifest, history, requests |
| Project validator | `services/project_validator.py` | Mandatory field validation |
| Project format | `services/project_format.py` | `.gjs` ZIP read/write |
| Projects manager | `services/projects_manager.py` | Full project lifecycle |
| Project history | `services/project_history_service.py` | Automatic event logging |
| Workspace service | `services/workspace_service.py` | Runtime-only temp files |
| Autosave service | `services/autosave_service.py` | Recovery copies + session state |
| Recent projects | `services/recent_projects_manager.py` | Extended recent list metadata |

## UI integration

| UI | Role |
|----|------|
| `NewProjectWizard` | Collect and validate new project fields |
| `ProjectTree` | Explorer sections (initially empty placeholders) |
| `ProjectDashboard` | Centre summary when project loaded |
| `RecentProjectsPanel` | Recent list when no project loaded |
| `RecoveryDialog` | Unclean shutdown recovery |
| `MainWindow` | File menu, stacked workspace, status bar binding |

## Lifecycle flows

### New project
1. Wizard validates `NewProjectRequest`
2. `ProjectsManager.new_project()` creates manifest + history
3. Writes `.gjs` to output folder
4. Opens project in memory, registers recent entry
5. UI switches to tree + dashboard view

### Autosave
1. Timer fires every `autosave_interval_minutes`
2. `AutosaveService.autosave()` writes `recovery/autosave.gjs`
3. Primary `.gjs` is untouched

### Recovery
1. On startup, `session_state.json` checked
2. If `clean_shutdown` is false, recovery files listed
3. Operator may restore or discard

## Extension guidance for GJS-003+

- Add new manifest counters or nested paths in `.gjs` ZIP
- Populate tree sections from real data modules
- Never store workspace temp files in `.gjs`
- Use `ProjectsManager.document` as the single source of truth for loaded state

See also: `docs/GJS_FILE_FORMAT.md`
