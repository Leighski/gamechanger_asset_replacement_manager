# Production Replay Guide

**Version:** 1.0.0-rc.1

## Overview

Production Replay lets operators step forwards and backwards through the complete production chain for any open project.

**Navigation:** Validation (Ctrl+5) → **Replay** tab

## Replay Chain

The replay viewer reconstructs these stages in order:

1. **Reference Images** — imported images and view types
2. **Vision Analysis** — per-analysis engine version and measurements
3. **AI Interpretation** — suggestions and provider
4. **Learning Recommendations** — advisory rules (never auto-applied)
5. **Operator Decisions** — accept / reject / modify per field
6. **Design Specification** — current spec state and validation status
7. **Template Selection** — template ID and version
8. **PSD Rendering** — render history events
9. **Final Export** — PNG generation events

## Controls

| Control | Action |
|---------|--------|
| **◀ Previous** | Step backward one stage |
| **Next ▶** | Step forward one stage |
| **Rebuild Chain** | Reconstruct from current project data |
| Step list | Click any stage to jump directly |

## Detail Panel

The JSON detail panel shows:

- Stage type and title
- Timestamp (when available)
- Summary text
- Full payload (measurements, suggestions, operator values, render paths)

## Data Sources

Replay is built from:

- `reference_manifest` — reference images
- `vision_analyses` — vision engine results
- `interpretation_results` — AI suggestions, learning recommendations, operator feedback
- `design_spec` — canonical specification
- `template_settings` — selected template
- `history` — render and export events
- `learning_record` — rules applied per project

## Service

`ReplayService.build_replay(document)` → `ProductionReplay`

Methods: `step_forward()`, `step_backward()`, `current_step()`

No data is modified during replay — read-only inspection.
