# Learning Mode Architecture

## Purpose

Learning Mode is an **organisational knowledge system** — not machine learning. It observes operator corrections, identifies recurring patterns, and suggests reusable rules. The operator always decides whether to create or apply a rule.

## Position in the stack

```
Operator Review → Learning Events → Knowledge Base → Rule Engine → Advisory Recommendations
                         ↑                                    ↓
                  Interpretation Engine              (never auto-applies)
```

## Subsystem layout

```
models/learning.py                    Events, rules, knowledge base models
config/learning/
  gamechanger_knowledge_base.json     Versioned organisational repository
services/learning/
  knowledge_base_service.py           Load/save/import/export
  event_service.py                    Capture corrections
  rule_service.py                     CRUD + pattern detection
  rule_engine.py                      Evaluate approved rules (advisory)
  analytics_service.py                Dashboard + rule statistics
services/learning_manager_service.py  Central coordinator
```

## Core principles

1. Never change Design Specification automatically
2. Never retrain AI models or modify Vision Engine
3. Rules are advisory — shown as "Learning Recommendation"
4. Metrics improve process, not AI behaviour

## UI

**Learning** nav (Ctrl+7): Dashboard + Rules (Browser + Inspector)

## Related documents

- [Learning Rule Specification](LEARNING_RULE_SPECIFICATION.md)
- [Rule Engine Workflow](RULE_ENGINE_WORKFLOW.md)
- [Learning Analytics Guide](LEARNING_ANALYTICS_GUIDE.md)
- [Organisational Knowledge Base Guide](ORGANISATIONAL_KNOWLEDGE_BASE_GUIDE.md)
