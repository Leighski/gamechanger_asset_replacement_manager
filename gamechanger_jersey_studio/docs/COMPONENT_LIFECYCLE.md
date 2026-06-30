# Component Lifecycle

## Status flow

```
Draft → Review → Approved → Certified
                              ↓
                         Deprecated
```

| Status | Meaning |
|--------|---------|
| Draft | Work in progress — not for production |
| Review | Awaiting operator approval |
| Approved | Approved for use |
| Certified | Production-ready Gamechanger standard |
| Deprecated | Superseded — warning on use |

## History events

Recorded in `catalogue_history.json`:

- Component Created
- Component Modified
- Component Approved
- Component Deprecated
- Component Imported
- Component Exported
- Catalogue Loaded

## Production warnings

Using Draft or Review components in a Design Specification emits a validation **warning**. Deprecated components emit a deprecation warning.
