# Rule Engine Workflow

## When rules are evaluated

After AI suggestions are generated and before display to the operator:

```
interpret_analysis()
  → DesignSuggestionService.from_provider_payload()
  → ConfidenceEvaluationService.evaluate_all()
  → LearningRuleEngine.evaluate()          ← approved rules only
  → LearningRuleEngine.apply_confidence_boost()
  → InterpretationResult.learning_recommendations
```

## What rules can do

| Capability | Automatic? |
|------------|------------|
| Increase suggestion confidence | Advisory boost only |
| Recommend catalogue component | Shown in recommendation |
| Add advisory note | Shown alongside AI suggestion |

Rules **cannot** overwrite AI `proposed_value` or apply changes to Design Specification.

## Display

Learning Recommendations appear as:

> **Learning Recommendation:** Coventry City v-neck collar preference  
> Advisory: Based on 8 similar corrections

## Usage tracking

When a rule matches:
- `usage_count` incremented
- `last_used` updated
- `RuleUsageRecord` appended to Knowledge Base

When operator accepts a recommendation-influenced suggestion, record via project `learning_record`.

## Pattern detection

After each Learning Event, `LearningRuleService.detect_rule_suggestions()` checks for ≥3 identical corrections (club + field + value change). Prompts operator: Create Rule / Ignore / Remind Later.
