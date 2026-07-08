# Release Notes — Gamechanger Jersey Studio

## v1.0.0-rc.1 — RC1 Production Validation (Build 014)

**Release date:** 2026-06-30  
**Work package:** GJS-014

### Highlights

- **Validation Workspace** — load reference images, original PSD, Studio PSD, PNG preview; side-by-side comparison with pixel diff overlay and layer visibility
- **Accuracy scoring** — overall, colour, pattern, collar, trim, sleeve, template with confidence per category
- **Production Replay** — step through Reference Images → Vision → AI → Learning → Operator → Spec → Template → Render → Export
- **Benchmark dataset** — `config/benchmarks/rc1_benchmark_library.json` with expected/generated specs and accuracy metrics
- **Batch validation** — mean/median accuracy, AI acceptance rate, learning rule effectiveness, review/render times, corrected fields, missing components
- **Knowledge Base analytics** — most/least effective rules, never triggered, overrides, suggested merges/retirements (advisory only)
- **Stress testing** — 100 consecutive renders, large catalogues, template switches, large knowledge bases
- **Release Readiness Report** — test, performance, accuracy, stability summaries with RC1 recommendation
- **203 automated tests** (+47 new in `test_rc1_validation.py`)

### Architecture

Frozen — all validation extends existing `services/production/` via `ProductionManagerService`. No new manager layer.

### RC1 sign-off

Populate benchmark library with 50–100 real jerseys before final RC1 release.

---

## v1.0.0-alpha.13 — Learning Mode & Organisational Knowledge Base (Build 013)

**Release date:** 2026-06-30  
**Work package:** GJS-013

### Highlights

- **Learning Mode** — organisational knowledge system (not machine learning)
- **Learning Events** — captures manual corrections with full project context
- **Gamechanger Knowledge Base** — versioned rule repository at `config/learning/gamechanger_knowledge_base.json`
- **Learning Rules** — club, manufacturer, competition, template, pattern, collar, sleeve, trim, colour, output profile categories
- **Rule Engine** — advisory Learning Recommendations alongside AI suggestions; never auto-applies
- **Pattern detection** — suggests reusable rules after recurring corrections
- **Learning Dashboard** — events, active/draft rules, frequent corrections, improved fields
- **Rule Browser** — search, filter, enable, disable, edit, duplicate, export, import
- **Rule Inspector** — triggers, actions, usage history, performance statistics
- **Project audit** — learning rules applied, recommendations accepted/ignored in `learning/record.json`
- **Extended reports** — Learning Summary, Top Rules, Rule Effectiveness, Learning Growth

### Not included

AI model retraining, Vision Engine modification, automatic Design Specification changes.

---

## v1.0.0-alpha.12 — Assisted Production & Confidence Workflow (Build 012)

**Release date:** 2026-06-30  
**Work package:** GJS-012

### Highlights

- **Confidence workflow** — configurable Trusted (95%), Review (85%), Manual Review Required thresholds in Settings
- **Production Queue** — cross-project pending interpretation view with filters (confidence, season, competition, status, template)
- **Bulk review** — Accept All Trusted, Reject All Low Confidence, Accept/Reject Selected, Export Queue
- **Visual Difference Viewer** — highlights only fields that would change with before/after values
- **Batch rendering** — sequential multi-project PSD render with pause, resume, cancel, retry failed
- **Production Dashboard** — awaiting review, ready to render, rendering, completed, failed, average confidence and render time
- **Operator metrics** — projects reviewed, acceptance/modification rates, review and render times (process improvement only)
- **Audit trail** — chain of custody from reference images through vision, AI, operator decisions, spec, template, renderer, output
- **Production reports** — Daily Production, Confidence Summary, Operator Activity, Render Performance, Failure Report

### Not included

Parallel PSD rendering, queue persistence across restarts, automatic AI behaviour changes from metrics.

---

## v1.0.0-alpha.11 — Production PSD Renderer (Build 011)

**Release date:** 2026-06-30  
**Work package:** GJS-011

### Highlights

- **Production PSD Renderer** — data-driven layered Photoshop output from Design Specification
- **Seven rendering services** — PSDRenderService, SmartObjectRenderService, LayerColourService, PatternPlacementService, TexturePlacementService, LayerVisibilityService, PSDExportService
- **10-stage pipeline** — open PSD, resolve mappings/components, apply colours/patterns/textures, update Smart Objects, toggle layers, validate, export
- **Template Engine PSD gate** — `open_template_psd()` is the sole application entry point for source templates
- **Smart Object editing** — catalogue assets replace Smart Object contents without rasterisation
- **Validation** — abort render on missing layers, colours, or catalogue components
- **Export** — layered PSD, preview PNG, and `render_log.json` in project `renders/` folder
- **Render queue** — sequential multi-project rendering
- **PSD Render Progress dialog** — stage, elapsed time, layer, warnings, errors
- **Renderer Inspector** — PSD render timings, colours, patterns, textures, Smart Objects
- **Project history** — Render Started, Completed, Failed, PSD Saved, PNG Generated

### Not included

Parallel PSD rendering, Photoshop automation, additional certified templates beyond Broadcast v1.

---

## v1.0.0-alpha.10 — PSD Template Engine (Build 010)

**Release date:** 2026-06-30  
**Work package:** GJS-010

### Highlights

- **PSD Template Engine** — permanent bridge between Jersey Studio and Gamechanger Photoshop templates
- **Seven template services** — TemplateManager, PSDTemplateLoader, LayerMappingService, AnchorPointService, SmartObjectService, TemplateValidator, TemplatePreviewGenerator
- **Gamechanger Broadcast v1** — first certified template with analysis, mappings, and anchors
- **Read-only PSD analysis** — layer hierarchy, Smart Objects, blend modes, masks, canvas metadata stored separately
- **Configurable layer mappings** — Design Specification fields → PSD layers via JSON configuration
- **Anchor system** — collar, sleeve, badge, sponsor, manufacturer, number, name anchors
- **Libraries panel** — Components and PSD Templates tabs with Template Browser and Inspector
- **Project integration** — `template/settings.json` stores active Template ID (not PSD path)
- **Render Engine bridge** — live renderer requests published mappings without knowing PSD filename

### Not included

PSD editing, production PSD output, Vision/Interpretation/Component Library architecture changes.

---

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
