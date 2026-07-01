# Production Workflow Guide

## Overview

GJS-012 introduces confidence-driven assisted production. The operator remains in full control of every Design Specification change — metrics and automation assist workflow speed, never override decisions.

## Workflow

1. **Import reference images** and run Vision Analysis (Validation nav)
2. **Generate AI suggestions** — Interpretation Engine proposes field changes with confidence scores
3. **Review in Production Queue** — cross-project view of pending interpretations
4. **Bulk review** — Accept All Trusted, Reject All Low Confidence, or review selected items
5. **Visual diff** — only changed fields shown with before/after values
6. **Approve for render** — accepted items move to Ready to Render
7. **Batch render** — sequential PSD output with pause/resume/cancel
8. **Audit trail** — every output traceable through chain of custody

## Navigation

- **Production** (Ctrl+6) — Queue, Dashboard, Reports, Settings tabs
- **Tools → Batch Processing** — open Production Queue
- **Tools → Generate Reports** — open Production Reports tab

## Confidence bands

| Band | Default range | Operator action |
|------|---------------|-----------------|
| Trusted | 95–100% | Eligible for Accept All Trusted |
| Review | 85–94% | Verify before accepting |
| Manual Review Required | Below 85% | Never auto-selected; reject or edit manually |

Thresholds are configurable in **Production → Settings**.

## Operator control

- No suggestion is applied without explicit accept
- Low-confidence suggestions are never auto-selected
- Metrics are for process improvement only — they do not alter AI behaviour
