"""Autosave and recovery management."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.paths import SESSION_STATE_PATH
from models.project import ProjectDocument
from services.logging_manager import get_logger
from services.project_format import read_project_package, write_project_package
from services.workspace_service import WorkspaceService

logger = get_logger()


@dataclass(frozen=True)
class RecoveryCandidate:
    recovery_path: Path
    project_id: str
    primary_path: str
    saved_at: str
    project_name: str


@dataclass(frozen=True)
class SessionState:
    project_path: str = ""
    project_id: str = ""
    clean_shutdown: bool = True

    @classmethod
    def from_dict(cls, raw: dict) -> SessionState:
        return cls(
            project_path=str(raw.get("project_path", "")),
            project_id=str(raw.get("project_id", "")),
            clean_shutdown=bool(raw.get("clean_shutdown", True)),
        )

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "project_id": self.project_id,
            "clean_shutdown": self.clean_shutdown,
        }


class AutosaveService:
    """Write recovery copies without touching the primary .gjs file."""

    def __init__(self, workspace: WorkspaceService | None = None) -> None:
        self._workspace = workspace or WorkspaceService()
        self._last_autosave_at: str = ""
        SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    @property
    def last_autosave_at(self) -> str:
        return self._last_autosave_at

    def autosave(self, document: ProjectDocument, *, reference_blobs: dict[str, bytes] | None = None) -> Path | None:
        if not document.file_path:
            return None
        project_id = document.manifest.project_id
        self._workspace.ensure_project_workspace(project_id)
        recovery_path = self._workspace.recovery_path(project_id)
        write_project_package(document, recovery_path, reference_blobs=reference_blobs or {})
        self._last_autosave_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        logger.info(
            "Autosave recovery written — project={} path={}",
            document.manifest.project_name,
            recovery_path,
        )
        return recovery_path

    def clear_recovery(self, project_id: str) -> None:
        self._workspace.clear_recovery(project_id)

    def mark_session_open(self, document: ProjectDocument) -> None:
        self._write_session(
            SessionState(
                project_path=document.file_path,
                project_id=document.manifest.project_id,
                clean_shutdown=False,
            )
        )

    def mark_session_closed(self) -> None:
        self._write_session(SessionState(clean_shutdown=True))

    def load_session_state(self) -> SessionState:
        if not SESSION_STATE_PATH.is_file():
            return SessionState()
        try:
            raw = json.loads(SESSION_STATE_PATH.read_text(encoding="utf-8"))
            return SessionState.from_dict(raw)
        except (OSError, json.JSONDecodeError, TypeError):
            return SessionState()

    def discover_recovery_candidates(self) -> list[RecoveryCandidate]:
        session = self.load_session_state()
        candidates: list[RecoveryCandidate] = []
        if session.clean_shutdown:
            return candidates

        for recovery_path in self._workspace.list_recovery_files():
            try:
                doc, _ = read_project_package(recovery_path)
            except Exception as exc:
                logger.warning("Skipping invalid recovery file {}: {}", recovery_path, exc)
                continue
            candidates.append(
                RecoveryCandidate(
                    recovery_path=recovery_path,
                    project_id=doc.manifest.project_id,
                    primary_path=session.project_path or doc.file_path,
                    saved_at=doc.manifest.modified_at,
                    project_name=doc.manifest.project_name,
                )
            )
        return candidates

    def restore_from_recovery(self, candidate: RecoveryCandidate) -> ProjectDocument:
        doc, _ = read_project_package(candidate.recovery_path)
        doc.file_path = candidate.primary_path
        doc.mark_dirty()
        return doc

    def _write_session(self, state: SessionState) -> None:
        SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SESSION_STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
