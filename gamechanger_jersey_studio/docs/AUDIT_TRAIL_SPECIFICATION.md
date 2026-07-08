# Audit Trail Specification

## Purpose

Every rendered PSD must be traceable back through the complete chain of custody for production artwork compliance.

## History events

| Event | When recorded |
|-------|---------------|
| Suggestion Accepted / Rejected / Modified | Operator review decision |
| Render Started / Completed / Failed | PSD render pipeline |
| PSD Saved / PNG Generated | Export complete |
| Production Audit Recorded | Chain of custody built |
| Batch Render Started / Paused / Resumed / Cancelled / Completed | Batch session |

## Chain of custody links

`ProductionAuditService.build_chain()` records:

1. **Reference Images** — image ID, filename, view type
2. **Vision Analysis** — analysis ID, engine version
3. **AI Interpretation** — interpretation ID, provider
4. **Operator Decision** — per-suggestion feedback records
5. **Design Specification** — project ID, modified timestamp
6. **Template** — template ID and version
7. **Renderer** — PSD renderer version, render log path
8. **PSD Output** — rendered file path
9. **PNG Preview** — preview file path

## Storage

- Per-project: `history.json` inside `.gjs` package
- Per-render: `render_log.json` in export `renders/` folder
- Interpretation feedback: `interpretation/results.json` in `.gjs`
- In-memory audit records: `ProductionAuditService.records`

## Querying decisions

`ProductionAuditService.suggestion_decisions_from_history(document)` returns all accept/reject/modify events with timestamps, user, confidence, and field names.

## Export

Production reports and queue export include audit summaries. Full chain available in `ProductionAuditRecord.chain`.
