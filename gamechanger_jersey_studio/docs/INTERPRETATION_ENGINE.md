# Interpretation Engine

**Version:** 1.0.0-alpha.7

## Purpose

Convert authoritative vision measurements into proposed Design Specification updates for operator review.

## Inputs (only)

- `VisionAnalysisResult`
- Project metadata (`ProjectManifest`)
- Current `DesignSpecification`
- `DesignCatalogues` (JSON)
- Validation rules

**Never** analyses image pixels.

## Services

```
services/interpretation/
├── confidence_evaluation.py
├── design_suggestion.py
├── prompt_builder.py
├── rule_engine.py
├── suggestion_history.py
└── providers/
    ├── base.py          # AIProvider interface
    ├── offline.py       # Rule-based offline mode
    └── registry.py      # Provider selection

services/interpretation_service.py   # Project integration
```

## Workflow

1. Operator runs Vision Engine analysis (unchanged from alpha.6).
2. Operator clicks **Generate AI Interpretation** on the Review screen.
3. `PromptBuilder` constructs a JSON prompt from measurements.
4. Configured `AIProvider` returns suggestions (offline rules by default).
5. `DesignSuggestionService` normalises suggestions with confidence bands.
6. Operator reviews, edits, accepts, or rejects each suggestion.
7. Accepted suggestions pass validation, then `DesignSpecificationService.apply_change()`.

## Confidence bands

| Range | Band | Auto-select |
|-------|------|-------------|
| 95–100% | High | Yes |
| 80–94% | Medium | Yes |
| Below 80% | Low | Never |
