# Learning Analytics Guide

## Dashboard metrics

| Metric | Source |
|--------|--------|
| Total Learning Events | `KnowledgeBase.events` |
| Active Rules | Approved status count |
| Draft Rules | Draft status count |
| Most Used Rule | Highest `usage_count` |
| Most Frequent Correction | Event pattern ranking |
| Most Improved Field | Field with most events |

## Per-rule analytics

| Metric | Calculation |
|--------|-------------|
| Usage Count | `rule.usage_count` |
| Acceptance Rate | `accepted / (accepted + rejected + modified)` |
| Ignored Count | `rule.ignored_count` |
| Modification Rate | `modified / total decisions` |
| Confidence Improvement | `action.confidence_boost` |

## Reports

Generate from **Production → Reports** or programmatically:

- Learning Summary
- Top Rules
- Rule Effectiveness
- Learning Growth

## Operator metrics boundary

Learning analytics are for **process improvement only**. They do not feed back into AI training or Vision Engine parameters.
