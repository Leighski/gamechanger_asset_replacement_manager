# RC1 Validation Guide

**Version:** 1.0.0-rc.1 · **Build:** 014 · **Work Package:** GJS-014

## Purpose

Prepare Gamechanger Jersey Studio for Release Candidate 1 through production validation, accuracy measurement, and operational hardening — without changing the frozen application architecture.

## Validation Workspace

**Navigation:** Validation (Ctrl+5) → **Workspace** tab

Load and compare:

| Asset | Purpose |
|-------|---------|
| Reference images | Original production references |
| Original PSD | Ground-truth production artwork |
| Studio PSD | Jersey Studio render output |
| PNG preview | Generated preview for pixel comparison |

### Visual Comparison

- **Side-by-side** — Before / After / Difference overlay panels
- **Pixel difference overlay** — Red highlight on changed pixels (saved to `cache/validation_diff.png`)
- **Before/after slider** — Horizontal slider for blend position
- **Layer visibility** — PSD layer comparison when both PSD paths are loaded
- **Zoom/pan** — Use preview panel alongside workspace for synchronised inspection

### Accuracy Scoring

Click **Calculate Accuracy** to score the current project design specification:

| Category | Fields compared |
|----------|-----------------|
| Overall | Weighted average of all categories |
| Colour | Primary, secondary, third, sleeve, collar, trim |
| Pattern | Pattern, scale, rotation, opacity |
| Collar | Style, colour |
| Trim | Style, colour |
| Sleeve | Style, colour |
| Template | Output profile |

Every score displays an accompanying **confidence** value.

## Benchmark Dataset

**Navigation:** Validation → **Benchmarks** tab

Benchmark projects store:

- Expected vs generated PSD paths
- Expected vs generated Design Specification
- Operator notes
- Accuracy metrics (after batch validation)

Library path: `config/benchmarks/rc1_benchmark_library.json`

## Batch Validation

From the Benchmarks tab:

1. **Load Library** — refresh benchmark table
2. **Add Current Project** — append open project
3. **Batch Validate** — score all benchmarks, save report to `reports/validation/`
4. **Release Readiness** — generate full RC1 readiness report
5. **Run Stress Tests** — lightweight stability suite

## Knowledge Base Analytics

Analyses rules without modifying them:

- Most / least effective rules
- Never triggered rules
- Frequently overridden rules
- Suggested merges and retirements (advisory only)

Access via Production → Reports → **Knowledge Base Validation**, or Benchmarks → Release Readiness.

## Architecture

All validation logic extends existing `services/production/`:

- `accuracy_service` — design spec field scoring
- `comparison_service` — pixel diff and PSD layers
- `replay_service` — production chain replay
- `benchmark_service` — benchmark library I/O
- `batch_validation_service` — aggregate reports
- `kb_validation_service` — learning rule analytics
- `stress_test_service` — stability scenarios
- `readiness_service` — RC1 release recommendation

Coordinated through `ProductionManagerService` — no new manager layer.

## RC1 Recommendation

Run **50–100 real Gamechanger jerseys** through the full workflow. Record per jersey:

- Manual time vs Studio time
- Fields correct vs needing adjustment
- Missing catalogue components
- Unreliable Vision measurements

Use batch validation reports to identify refinement priorities before final RC1 sign-off.
