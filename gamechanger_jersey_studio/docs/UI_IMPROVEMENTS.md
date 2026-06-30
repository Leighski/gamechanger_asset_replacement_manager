# UI Improvements — GJS-003 (v1.0.0-alpha.3)

**Build 003 · User Experience Polish · 2026-06-29**

This document records all UI improvements delivered in Build 003. The application shell is now considered **visually complete** — future work packages should add capability without revisiting the foundation.

---

## Before / After

| Area | Build 001–002 (Before) | Build 003 (After) |
|------|------------------------|-------------------|
| Typography | Single font size, platform warnings | Typography system with 5 hierarchy levels |
| Icons | None / text-only navigation | Consistent SVG stroke icons throughout |
| Sidebar | Plain text buttons | Icons, keyboard shortcuts, accent selection |
| Centre panel | Placeholder text | Welcome screen or Dashboard + Explorer |
| Menus | Help only | Full File/Edit/View/Project/Tools/Window/Help |
| Toolbar | None | New, Open, Save, Settings, Help |
| Status bar | Plain text labels | Icon-labelled project, autosave, Python, version, memory |
| Empty states | Generic “No project loaded” | Guided messages per section |
| Animations | Instant transitions | Splash fade, window fade, page crossfade |
| About | Basic version line | Full paths, release date, branding |
| Versioning | `0.1.0` / `0.2.0` | Semantic `1.0.0-alpha.3` |

### Screenshot comparison

| Build | Screenshot |
|-------|------------|
| 001 (before) | `docs/BUILD_001_SCREENSHOT.png` |
| 003 Welcome | `docs/GJS003_SCREENSHOT_WELCOME.png` |
| 003 Main window | `docs/GJS003_SCREENSHOT_MAIN.png` |
| 003 Dashboard | `docs/GJS003_SCREENSHOT_DASHBOARD.png` |
| 003 Explorer | `docs/GJS003_SCREENSHOT_EXPLORER.png` |
| 003 About | `docs/GJS003_SCREENSHOT_ABOUT.png` |

---

## Typography (`ui/typography.py`)

| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| Display | 26px | Bold | Welcome hero, splash title |
| Heading | 20px | Semibold | Dashboard title, dialog titles |
| Subheading | 15px | Medium | Section headers, card values |
| Body | 13px | Regular | Default UI text |
| Caption | 11px | Regular/Medium | Status bar, labels, hints |
| Mono | 11px | Regular | About dialog paths |

Platform fonts: `.AppleSystemUIFont` (macOS), `Segoe UI` (Windows), `Inter` (Linux).

---

## Icons (`ui/icons.py`)

- Inline SVG stroke icons rendered at 2× for Retina
- Shared visual style (1.75px stroke, rounded caps)
- Used in: sidebar, toolbar, status bar, dashboard cards, empty states, splash, About

---

## Theme (`ui/theme.py`)

- Dark charcoal palette (`#141414` background)
- Restrained blue accent (`#3A7BD5`)
- Spacing tokens: 4 / 8 / 12 / 16 / 24px
- Border radius: 4 / 8 / 12px
- Hover, pressed, disabled, and focus states on all interactive controls
- No gradients

---

## Navigation

- Sidebar width 232px with icon + label buttons
- Ctrl+1 through Ctrl+7 keyboard shortcuts
- Active item: accent icon, subtle accent background, accent border
- Tooltip shows shortcut hint

---

## Menus

All production menus present. Future functionality disabled rather than hidden:

- **File** — full project lifecycle + Quit
- **Edit** — Undo/Redo/Cut/Copy/Paste/Preferences (disabled)
- **View** — toggle sidebar, preview, status bar
- **Project** — information, settings, export (disabled)
- **Tools** — validate, reports, batch (disabled)
- **Window** — minimize, zoom (disabled)
- **Help** — documentation, release notes, about

---

## Toolbar (`ui/widgets/toolbar.py`)

| Button | Action |
|--------|--------|
| New Project | File → New |
| Open | File → Open |
| Save | File → Save (disabled when no project) |
| Settings | Select Settings in sidebar |
| Help | About dialog |

Reserved separator position for future tools.

---

## Welcome screen (`ui/widgets/welcome_screen.py`)

Displayed when no project is loaded:

- Branding with icon, title, version, build
- Create New Project / Open Existing / Documentation
- Embedded recent projects table with full actions

---

## Empty states (`ui/widgets/empty_state.py`)

Reusable component with icon, title, and guidance message. Used in:

- Preview panel (no project / project loaded)
- Project Explorer tree sections
- Future views should use this component

Example messages:
- “No reference images have been imported.”
- “Create a Design Specification to begin.”
- “No validation reports available.”

---

## Animations (`ui/animations.py`)

| Animation | Duration | Trigger |
|-----------|----------|---------|
| Splash fade-in | 180ms | Application start |
| Main window fade-in | 240ms | After splash |
| Page crossfade | 160ms | Welcome ↔ Project workspace |

All use `OutCubic` easing. Fast and unobtrusive.

---

## Status bar (`ui/widgets/status_bar.py`)

| Item | Icon | Content |
|------|------|---------|
| Ready | — | Context message |
| Project | folder | Name + status |
| Autosave | status_ok / status_idle | Autosave state |
| Python | python | Python version |
| Version | doc | Version 1.0 Alpha · Build 003 |
| Memory | memory | Live MB usage (2s refresh) |

---

## Performance

Startup measured offscreen (controller init → main window visible, excluding splash):

- **~107 ms** — main window construction and first paint (offscreen, macOS)
- **~2.0 s** — splash screen duration in production launch
- Heavy work deferred until after splash
- Icons rendered on demand, not preloaded

---

## Shell freeze policy

From Build 003 onward:

1. Do not modify `ui/theme.py`, `ui/typography.py`, or shell layout without strong justification.
2. New features integrate into existing navigation slots and explorer sections.
3. Use `EmptyState` for all new empty views.
4. Use `ui/icons.py` for all new icons.

---

## Recommendations before EPIC 3

1. **Reference Image Management** — first capability build; populate Explorer “Reference Images” and dashboard counter.
2. **Design Specification editor** — second capability; populate “Design Specification” section.
3. **Settings page** — wire sidebar Settings + Edit → Preferences to a real panel.
4. **Do not revisit the shell** until v1.0.0 Stable release candidate.
