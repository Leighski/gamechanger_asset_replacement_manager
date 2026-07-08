# AI Architecture

**Build:** 1.0.0-alpha.7 (GJS-007)

## Principle

The AI is an **assistant**, not an operator. The Design Specification remains the single source of truth. AI may recommend; only the operator may decide.

## Layer separation

```
Vision Engine (alpha.6)          Interpretation Engine (alpha.7)
─────────────────────           ────────────────────────────────
Measures pixels                  Consumes VisionAnalysisResult only
VisionAnalysisResult             InterpretationResult + Suggestions
Never writes Design Spec         Never writes Design Spec directly
                                 Operator approval → DesignSpecificationService
```

The Vision Engine measurement pipeline is **not modified** in this build. Its outputs are treated as authoritative.

## Components

| Component | Responsibility |
|-----------|----------------|
| `PromptBuilder` | Structured measurement-only prompts |
| `RuleEngine` | Deterministic catalogue mapping rules |
| `DesignSuggestionService` | Parse provider output into suggestions |
| `ConfidenceEvaluationService` | High / Medium / Low bands |
| `SuggestionHistoryService` | Record accepted / rejected / modified |
| `InterpretationService` | Orchestration, persistence, history |
| `ProviderRegistry` | Vendor-independent AI abstraction |

## Offline mode

When no AI provider is configured, the offline rule engine produces fully explainable suggestions. The Review screen remains fully functional.

## Persistence

Interpretation results are stored at `interpretation/results.json` inside the `.gjs` package, separate from `vision/analyses.json`.
