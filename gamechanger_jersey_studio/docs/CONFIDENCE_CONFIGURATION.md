# Confidence Configuration

## Settings location

Confidence thresholds are stored in `config/settings.json` under `confidence_thresholds`:

```json
{
  "confidence_thresholds": {
    "trusted_min": 95.0,
    "review_min": 85.0
  }
}
```

## Defaults

| Setting | Default | Band |
|---------|---------|------|
| `trusted_min` | 95.0 | Trusted (High) |
| `review_min` | 85.0 | Review (Medium) |
| Below `review_min` | — | Manual Review Required (Low) |

## Customisation

1. Open **Production → Settings** tab
2. Adjust Trusted minimum and Review minimum percentages
3. Click **Save Thresholds**

Changes apply immediately to new interpretation evaluations and bulk review eligibility.

## Band labels

| Internal band | Display label |
|---------------|---------------|
| High | Trusted |
| Medium | Review |
| Low | Manual Review Required |

## Bulk review rules

- **Accept All Trusted** — applies only suggestions at or above `trusted_min`
- **Reject All Low Confidence** — rejects suggestions below `review_min`
- Auto-select checkboxes in Validation review use the same thresholds
