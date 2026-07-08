# Operator Review Workflow

## Screen

**Analysis & Interpretation Review** (sidebar: Validation, Ctrl+5)

## Display

1. **Reference image** with shirt outline and detected regions (Vision Engine)
2. **Colour palette** and measurement tables (Vision Engine)
3. **Current Design Specification** — read-only field summary
4. **AI Interpretation Suggestions** — proposed changes with reasoning

Each suggestion shows:
- Target field and confidence band (colour-coded)
- Current vs proposed value (editable before acceptance)
- Reasoning and source measurements
- Status (Pending / Accepted / Rejected / Modified)

## Operator actions

| Action | Effect |
|--------|--------|
| Generate AI Interpretation | Run Interpretation Engine on latest vision analysis |
| Accept All AI | Apply all pending suggestions (with edited values) |
| Accept Selected AI | Apply checked suggestions only |
| Reject Selected AI | Mark checked suggestions rejected; record feedback |
| Reject All AI | Reject all pending suggestions |
| Edit proposed value | Operator can modify before acceptance → recorded as Modified |

Vision Engine mapping actions (Accept All / Selected / Reject Analysis / Reanalyse) remain available for direct measurement mappings.

## Validation

Before any accepted suggestion is applied, the Rule Engine validates against Design Specification rules and catalogue IDs. Invalid values are blocked with an error message.

## Offline mode

When no AI provider is configured, **Generate AI Interpretation** uses the offline rule engine. All review actions work identically.
