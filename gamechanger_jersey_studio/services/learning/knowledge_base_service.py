"""Knowledge Base persistence — versioned organisational rule repository."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from core.paths import KNOWLEDGE_BASE_EXAMPLE_PATH, KNOWLEDGE_BASE_PATH, LEARNING_DIR
from models.learning import KNOWLEDGE_BASE_VERSION, KnowledgeBase, LearningRule
from services.logging_manager import get_logger

logger = get_logger()


class KnowledgeBaseService:
    """Load, save, import, and export the Gamechanger Knowledge Base."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or KNOWLEDGE_BASE_PATH
        self._knowledge = KnowledgeBase()
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def knowledge(self) -> KnowledgeBase:
        return self._knowledge

    def load(self) -> KnowledgeBase:
        if not self._path.is_file():
            self._ensure_example()
            self._knowledge = KnowledgeBase()
            self.save()
            logger.info("Knowledge Base initialised — {}", self._path.name)
            return self._knowledge
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._knowledge = KnowledgeBase.model_validate(raw)
        logger.info(
            "Knowledge Base loaded — {} rules, {} events",
            len(self._knowledge.rules),
            len(self._knowledge.events),
        )
        return self._knowledge

    def save(self) -> None:
        self._knowledge.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._knowledge.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        logger.info("Knowledge Base saved — {}", self._path.name)

    def export_to(self, target: Path) -> Path:
        target = Path(target).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._path, target)
        return target

    def import_from(self, source: Path, *, merge: bool = True) -> KnowledgeBase:
        source = Path(source).expanduser().resolve()
        incoming = KnowledgeBase.model_validate(json.loads(source.read_text(encoding="utf-8")))
        if not merge:
            self._knowledge = incoming
        else:
            existing_ids = {r.rule_id for r in self._knowledge.rules}
            for rule in incoming.rules:
                if rule.rule_id not in existing_ids:
                    self._knowledge.rules.append(rule)
            self._knowledge.events.extend(incoming.events)
        self.save()
        logger.info("Knowledge Base imported — {} rules from {}", len(incoming.rules), source.name)
        return self._knowledge

    def replace_rules(self, rules: list[LearningRule]) -> None:
        self._knowledge.rules = rules
        self.save()

    def _ensure_example(self) -> None:
        if KNOWLEDGE_BASE_EXAMPLE_PATH.is_file():
            return
        example = KnowledgeBase(version=KNOWLEDGE_BASE_VERSION).model_dump(mode="json")
        KNOWLEDGE_BASE_EXAMPLE_PATH.write_text(json.dumps(example, indent=2), encoding="utf-8")
