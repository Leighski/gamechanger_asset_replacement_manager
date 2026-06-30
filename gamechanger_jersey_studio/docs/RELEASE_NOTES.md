# Release Notes — Gamechanger Jersey Studio

## v1.0.0-alpha.9 — Live Renderer & Component Assembly Engine (Build 009)

**Release date:** 2026-06-30  
**Work package:** GJS-009

### Highlights

- **Live Renderer** — assembles jersey previews from certified catalogue components
- **Nine rendering services** — RenderingEngine, ComponentAssembler, LayerManager, ColourMapper, PatternMapper, TextureMapper, LightingEngine, PreviewCache, RenderQueue
- **Live Preview panel** — auto-regenerates on Design Specification change (&lt; 150 ms target, Standard quality)
- **Layer system** — 10 toggleable layers (body, sleeves, collar, trim, pattern, texture, shadows, lighting, highlights, background)
- **Colour mapping** — primary, secondary, accent, trim, sleeve, collar
- **Pattern mapping** — scale, rotation, opacity from Design Specification
- **Quality modes** — Draft, Standard, High
- **Per-layer cache** — partial invalidation on single-property changes
- **Renderer Inspector** — layers, timings, cache hits/misses, memory
- **Project integration** — `renderer/settings.json` in `.gjs` (no preview pixels stored)

### Not included

Vision Engine changes, Interpretation Engine changes, Component Library architecture changes, PSD production rendering.

---

## v1.0.0-alpha.8 — Component Library & Asset Catalogue (Build 008)

**Release date:** 2026-06-30  
**Work package:** GJS-008

### Highlights

- **Component Library** — permanent catalogue source for all reusable design assets
- **12 independent catalogues** — collars, sleeves, patterns, trims, materials, textures, lighting, shadows, effects, build profiles, validation profiles, colour palettes
- **Full component model** — ID, version, status, preview, assets, tags, lifecycle
- **Catalogue Browser** — search, filter, sort, tag filtering, category browsing
- **Component Viewer** — preview, metadata, version history, PSD placeholders
- **Design Specification integration** — canonical IDs (`COLLAR_0004`) with legacy slug compatibility
- **Validation** — missing, deprecated, and draft component warnings
- **Import / export** — JSON component manifests
- **39 certified components** seeded with PNG previews

### Not included

Vision Engine changes, Interpretation Engine changes, PSD rendering.

---

## v1.0.0-alpha.7 — AI Interpretation & Operator Review (Build 007)

**Release date:** 2026-06-30  
**Work package:** GJS-007

### Highlights

- **Interpretation Engine** — consumes `VisionAnalysisResult` only; never analyses raw images
- **Six interpretation services** — PromptBuilder, RuleEngine, DesignSuggestionService, ConfidenceEvaluationService, SuggestionHistoryService, InterpretationService
- **AI provider abstraction** — OpenAI, Anthropic, Gemini, Ollama stubs; offline rule engine as default
- **Suggestion model** — target field, current/proposed values, confidence band, reasoning, source measurements
- **Enhanced Review screen** — current Design Spec, AI suggestions, editable values, accept/reject workflows
- **Operator control** — Accept All / Individual / Reject / Modify before acceptance
- **Validation** — suggestions validated against Design Specification rules before apply
- **Learning support** — operator decisions recorded for future analytics (no auto-retraining)
- **Offline mode** — fully functional without AI provider configuration
- **Persistence** — `interpretation/results.json` in `.gjs`

### Not included

Vision Engine changes, PSD rendering, live vendor API calls, auto-retraining.

---

## v1.0.0-alpha.6 — Vision Engine Phase 1 (Build 006)

**Release date:** 2026-06-30  
**Work package:** GJS-006

### Highlights

- **Vision Engine** — permanent image analysis subsystem (measurement, not AI guessing)
- **Nine analysis services** — Image Loader, Normalisation, Shirt Detection, Background Removal, Colour Analysis, Shape Analysis, Pattern Analysis, Region Detection, Confidence Calculator
- **Analysis Results model** — separate from Design Specification; operator review required
- **Analysis Review screen** — original image, shirt outline, regions, colour palette, measurements, confidence, suggested mappings
- **Operator actions** — Accept All, Accept Individual, Reject, Reanalyse
- **Project persistence** — `vision/analyses.json` with full history; multiple analyses per image
- **Performance metrics** — processing time, image size, memory, CPU (GPU placeholder)
- **Comprehensive unit tests** — loader, normalisation, colour, regions, confidence, persistence, integration

### Not included

Photoshop integration, PSD generation, jersey artwork generation, pattern identification, Design Specification auto-update without approval.

---

## v1.0.0-alpha.5 — Reference Image Management (Build 005)

**Release date:** 2026-06-30  
**Work package:** GJS-005

### Highlights

- Reference Image Management subsystem — immutable project evidence
- Import PNG, JPEG, TIFF, WEBP, PSD (flattened preview)
- Image manifest at `references/manifest.json` inside `.gjs`
- Card-based gallery with drag-and-drop import
- Full-screen viewer with zoom, fit, and navigation
- Workspace thumbnail generation
- Multi-tag categories (Front View, Rear View, Detail, etc.)
- Dashboard and Explorer integration with validation
- History events for import, delete, replace, retag, rename, viewed

### Not included

AI analysis, Photoshop integration, PSD rendering.

---

## v1.0.0-alpha.4 — Design Specification Engine (Build 004)

**Release date:** 2026-06-30  
**Work package:** GJS-004

### Highlights

- **Design Specification** — canonical Pydantic model for every jersey project
- **Design Specification editor** — grouped panels (Project, Colours, Construction, Pattern, Effects, Output, Validation, Notes)
- **Immediate updates** — no Save button; changes mark project dirty and sync to manifest
- **Undo/redo** — full reversible command stack for all specification edits
- **Live validation** — colour, catalogue, and opacity rules with status in editor and explorer
- **Placeholder catalogues** — collars, patterns, sleeves, materials, effects, output profiles (JSON)
- **Dashboard completeness score** — per-section and overall completion percentages
- **Project Explorer** — Design Specification node with section validation icons
- **Persistence** — `design/specification.json` inside `.gjs` with backward compatibility
- **History & logging** — every change recorded with property, old/new values, and user

### Not included

Reference image import, AI analysis, Photoshop integration, PSD generation.

---

## v1.0.0-alpha.3 — User Experience Polish (Build 003)

**Release date:** 2026-06-29  
**Work package:** GJS-003

### Highlights

- Commercial-grade desktop polish across the entire application shell
- Semantic versioning introduced (`1.0.0-alpha.3`)
- Typography system with platform-native fonts
- Consistent SVG icon set for sidebar, toolbar, and status bar
- Professional welcome screen when no project is open
- Complete production menu bar (File, Edit, View, Project, Tools, Window, Help)
- Application toolbar with New, Open, Save, Settings, and Help
- Expanded About dialog with paths and platform details
- Subtle UI animations (splash fade-in, main window fade-in, page transitions)
- Professional empty states throughout explorer, preview, and dashboard
- Enhanced status bar with icons for project, autosave, Python, version, and memory

### No functional changes

This build does not add jersey-generation, reference image import, design specification editing, or AI features.

---

## v1.0.0-alpha.2 — Project Management (Build 002)

- `.gjs` portable project format
- Full project lifecycle (New, Open, Save, Save As, Close, Duplicate, Archive, Delete)
- Project Explorer, Dashboard, Recent Projects
- Autosave recovery and session recovery

---

## v1.0.0-alpha.1 — Application Foundation (Build 001)

- PySide6 desktop shell
- Dark theme, splash screen, settings persistence, logging, About dialog
