# Organisational Knowledge Base Guide

## Gamechanger Knowledge Base

The Knowledge Base is a **separate, versioned repository** — not embedded only in projects.

**Path:** `config/learning/gamechanger_knowledge_base.json`

## Contents

```json
{
  "schema_version": "1.0",
  "version": "1.0.0",
  "updated_at": "2026-06-30T...",
  "rules": [],
  "events": [],
  "usage_history": [],
  "pending_prompts": []
}
```

## Import / Export

### From UI

**Learning → Rules → Export KB / Import KB**

### Programmatically

```python
learning_manager.export_knowledge_base(Path("backup.json"))
learning_manager.import_knowledge_base(Path("shared_rules.json"), merge=True)
```

## Sharing across installations

1. Export Knowledge Base from source machine
2. Import with `merge=True` on target machine
3. Approved rules immediately available to all operators

## Versioning

- `version` field tracks Knowledge Base release
- `updated_at` set on every save
- Example rules: `docs/examples/GJS013_LEARNING_RULES.json`

## Competitive advantage

The Knowledge Base captures years of Gamechanger production expertise — club preferences, manufacturer quirks, competition conventions — independent of AI inference quality.
