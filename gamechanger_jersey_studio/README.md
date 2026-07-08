# Gamechanger Jersey Studio

**GJS-008 — Build 008: Component Library & Asset Catalogue**

Professional desktop application for jersey design. Build 008 introduces the **Component Library** — the permanent catalogue source for all reusable Gamechanger design assets.

| Field | Value |
|-------|-------|
| Version | 1.0.0-alpha.8 |
| Label | Version 1.0 Alpha |
| Build | 008 |
| Python | 3.12+ |
| UI | PySide6 (Qt) |

---

## Run

```bash
cd gamechanger_jersey_studio
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

---

## Project structure

```
app/            Application entry point and controller
core/           Paths, version, memory utilities
ui/             PySide6 interface (theme, typography, icons, animations, widgets)
models/         Pydantic data models (project, design spec, reference images, vision analysis)
services/       Settings, logging, projects, vision engine, reference images
libraries/      Future design libraries (empty)
templates/      Future jersey templates (empty)
projects/       User project workspace folder
resources/      Static assets
reports/        Generated reports (future)
logs/           application.log
docs/           Architecture, release notes, screenshots
tests/          pytest unit tests
work_packages/  Work package specifications
config/         settings.json (created on first run)
```

---

## Build 008 scope (Component Library)

- Catalogue Manager with 12 versioned catalogues
- Component model with status lifecycle and asset references
- Catalogue Browser and Component Viewer UI
- Design Specification canonical IDs with legacy compatibility
- Import/export JSON manifests, validation, history, logging
- Example catalogues in `docs/examples/`

**Not included:** PSD rendering, Vision/Interpretation Engine changes.

## Build 007 scope (AI Interpretation)

- Interpretation Engine consuming VisionAnalysisResult only (no pixel analysis)
- AI provider abstraction with offline rule engine default
- Suggestion model with reasoning, confidence bands, operator feedback
- Enhanced Analysis & Interpretation Review screen
- Accept / reject / modify workflows with validation
- Persistence at `interpretation/results.json`
- Coventry examples in `docs/examples/`

**Not included:** Vision Engine changes, PSD rendering, live vendor APIs, auto-retraining.

## Build 006 scope (Vision Engine)

- Vision Engine with nine analysis services (loader, normalisation, shirt detection, background removal, colour, shape, pattern, region, confidence)
- `VisionAnalysisResult` model separate from Design Specification
- Analysis Review screen — Accept All / Individual / Reject / Reanalyse
- Persistence at `vision/analyses.json` with multiple analyses per image
- Performance metrics and confidence on every measurement
- Coventry example analysis in `docs/examples/`

**Not included:** Photoshop, PSD generation, jersey artwork, pattern identification, auto Design Spec updates.

## Build 005 scope (Reference Images)

- Reference image manifest and portable storage in `.gjs`
- Import PNG, JPEG, TIFF, WEBP, PSD (flattened)
- Card gallery, full-screen viewer, drag-and-drop import
- Multi-tag categories, validation, history, logging
- Dashboard and Explorer integration
- Workspace thumbnail generation

**Not included:** AI analysis, Photoshop, PSD rendering.

## Build 004 scope (Design Specification)

- Canonical Design Specification Pydantic model
- Grouped editor UI (Project, Colours, Construction, Pattern, Effects, Output, Validation, Notes)
- Immediate field updates with undo/redo and project history
- Live validation against JSON catalogues
- Dashboard completeness scoring
- Explorer Design Specification sections with validation icons
- Persistence in `.gjs` at `design/specification.json`

**Not included:** reference image import, AI, Photoshop, PSD generation.

## Build 003 scope (UX polish)

- Typography system with platform-native fonts
- Consistent SVG icon set (sidebar, toolbar, status bar)
- Enhanced dark theme — spacing, radius, hover, focus, disabled states
- Complete menu bar and application toolbar
- Welcome screen with recent projects
- Professional empty states
- Subtle animations (splash, main window, page transitions)
- Expanded About dialog and status bar
- Semantic versioning (`1.0.0-alpha.3`)

**Not included:** reference image import, design specification editing, AI, jersey generation.

## Build 002 scope (project management)

- **New Project wizard** — validated project creation
- **`.gjs` project format** — portable ZIP-based project packages
- **Project lifecycle** — New, Open, Save, Save As, Close, Duplicate, Archive, Delete
- **Project Explorer**, **Dashboard**, **Recent Projects**
- **Autosave recovery** and session recovery

## Build 001 scope (foundation)

- Professional dark theme and commercial application shell
- Splash screen, settings persistence, logging, About dialog

## Version history

| Version | Build | Milestone |
|---------|-------|-----------|
| 1.0.0-alpha.1 | 001 | Application Foundation |
| 1.0.0-alpha.2 | 002 | Project Management |
| 1.0.0-alpha.3 | 003 | User Experience Polish |
| 1.0.0-alpha.4 | 004 | Design Specification Engine |
| 1.0.0-alpha.5 | 005 | Reference Image Management |
| 1.0.0-alpha.6 | 006 | Vision Engine Phase 1 |
| 1.0.0-alpha.7 | 007 | AI Interpretation & Operator Review |
| 1.0.0-alpha.8 | 008 | Component Library & Asset Catalogue |

See `docs/CATALOGUE_ARCHITECTURE.md`, `docs/AI_ARCHITECTURE.md`, and `docs/RELEASE_NOTES.md`.

---

## Tests

```bash
pytest -q
```

---

## Screenshots

| Build | File |
|-------|------|
| 001 | `docs/BUILD_001_SCREENSHOT.png` |
| 002 | `docs/GJS002_SCREENSHOT_*.png` |
| 003 | `docs/GJS003_SCREENSHOT_*.png` |
| 004 | `docs/GJS004_SCREENSHOT_*.png` |
| 005 | `docs/GJS005_SCREENSHOT_*.png` |
