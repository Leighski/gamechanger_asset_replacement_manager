"""Complete project lifecycle management."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from uuid import uuid4

from core.version import APP_VERSION
from models.design_specification import DesignSpecification
from models.project import (
    GJS_EXTENSION,
    HistoryEventType,
    NewProjectRequest,
    ProjectDocument,
    ProjectManifest,
    ProjectStatus,
)
from services.autosave_service import AutosaveService
from services.catalogue_manager_service import CatalogueManagerService
from services.design_specification_service import DesignSpecificationService
from models.interpretation import InterpretationArchive
from models.reference_image import ReferenceImageManifest
from models.vision_analysis import VisionAnalysisArchive
from services.interpretation_service import InterpretationService
from services.live_renderer_service import LiveRendererService
from services.reference_image_service import ReferenceImageService
from services.vision_analysis_service import VisionAnalysisService
from services.logging_manager import get_logger
from services.project_format import ProjectFormatError, read_project_package, write_project_package
from services.project_history_service import ProjectHistoryService
from services.project_validator import assert_valid_new_project, default_project_file_path
from services.recent_projects_manager import RecentProjectsManager
from services.workspace_service import WorkspaceService

logger = get_logger()


@dataclass(frozen=True)
class ProjectSession:
    loaded: bool
    document: ProjectDocument | None
    file_path: Path | None

    @property
    def display_name(self) -> str:
        if self.document is None:
            return ""
        return self.document.display_name


class ProjectsManager:
    """Production project subsystem — all application data belongs to a project."""

    def __init__(
        self,
        recent_projects: RecentProjectsManager,
        *,
        workspace: WorkspaceService | None = None,
        history_service: ProjectHistoryService | None = None,
        autosave: AutosaveService | None = None,
        application_version: str = APP_VERSION,
    ) -> None:
        self._recent = recent_projects
        self._workspace = workspace or WorkspaceService()
        self._history = history_service or ProjectHistoryService()
        self._autosave = autosave or AutosaveService(self._workspace)
        self._application_version = application_version
        self._catalogues = CatalogueManagerService()
        self._catalogues.load()
        self._document: ProjectDocument | None = None
        self._design_spec = DesignSpecificationService(
            self._history,
            catalogues=self._catalogues.design_catalogues,
            application_version=application_version,
        )
        self._reference_images = ReferenceImageService(
            self._workspace,
            self._history,
            application_version=application_version,
        )
        self._vision = VisionAnalysisService(
            self._reference_images,
            self._design_spec,
            self._history,
            application_version=application_version,
        )
        self._interpretation = InterpretationService(
            self._design_spec,
            self._history,
            catalogues=self._catalogues.design_catalogues,
            application_version=application_version,
        )
        self._live_renderer = LiveRendererService(self._catalogues)

    @property
    def catalogue_manager(self) -> CatalogueManagerService:
        return self._catalogues

    @property
    def session(self) -> ProjectSession:
        path = Path(self._document.file_path) if self._document and self._document.file_path else None
        return ProjectSession(
            loaded=self._document is not None,
            document=self._document,
            file_path=path,
        )

    @property
    def document(self) -> ProjectDocument | None:
        return self._document

    @property
    def live_renderer_service(self) -> LiveRendererService:
        return self._live_renderer

    @property
    def autosave_service(self) -> AutosaveService:
        return self._autosave

    @property
    def workspace_service(self) -> WorkspaceService:
        return self._workspace

    def new_project(self, request: NewProjectRequest) -> ProjectDocument:
        assert_valid_new_project(request)
        target = default_project_file_path(request)
        if target.exists():
            raise FileExistsError(f"A project already exists at: {target}")

        manifest = ProjectManifest(
            project_name=request.project_name.strip(),
            club_name=request.club_name.strip(),
            competition=request.competition.strip(),
            season=request.season.strip(),
            kit_type=request.kit_type,
            build_profile=request.build_profile.strip(),
            output_folder=str(Path(request.output_folder).expanduser().resolve()),
            project_notes=request.project_notes.strip(),
            author=request.author.strip(),
            application_version=self._application_version,
            status=ProjectStatus.ACTIVE,
        )
        document = ProjectDocument(manifest=manifest)
        document.design_spec = DesignSpecification.from_manifest(manifest)
        document.reference_manifest = ReferenceImageManifest()
        document.vision_analyses = VisionAnalysisArchive()
        document.interpretation_results = InterpretationArchive()
        self._history.record(
            document,
            HistoryEventType.PROJECT_CREATED,
            application_version=self._application_version,
            user=manifest.author,
            details=f"Created at {target}",
        )
        write_project_package(document, target, reference_blobs={})
        self._open_document(document, record_open=False)
        logger.info("Project created — {} at {}", manifest.project_name, target)
        return document

    def open_project(self, path: str | Path) -> ProjectDocument:
        source = Path(path).expanduser().resolve()
        document, blobs = read_project_package(source)
        self._open_document(document, blobs=blobs)
        logger.info("Project opened — {} from {}", document.manifest.project_name, source)
        return document

    def save_project(self) -> Path:
        document = self._require_document()
        self._history.record(
            document,
            HistoryEventType.SAVED,
            application_version=self._application_version,
            user=document.manifest.author,
        )
        target = write_project_package(
            document,
            Path(document.file_path),
            reference_blobs=self._reference_blobs(),
        )
        self._autosave.clear_recovery(document.manifest.project_id)
        logger.info("Project saved — {}", target)
        return target

    def save_project_as(self, path: str | Path) -> Path:
        document = self._require_document()
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() != GJS_EXTENSION:
            target = target.with_suffix(GJS_EXTENSION)
        write_project_package(document, target, reference_blobs=self._reference_blobs())
        self._history.record(
            document,
            HistoryEventType.SAVED,
            application_version=self._application_version,
            user=document.manifest.author,
            details=f"Save As → {target}",
        )
        write_project_package(document, target, reference_blobs=self._reference_blobs())
        self._register_recent(document)
        self._autosave.mark_session_open(document)
        logger.info("Project saved as — {}", target)
        return target

    def close_project(self, *, save_if_dirty: bool = True) -> None:
        if self._document is None:
            return
        doc = self._document
        self._history.record(
            doc,
            HistoryEventType.CLOSED,
            application_version=self._application_version,
            user=doc.manifest.author,
        )
        if doc.file_path and (save_if_dirty or doc.dirty):
            write_project_package(doc, Path(doc.file_path), reference_blobs=self._reference_blobs())
            self._autosave.clear_recovery(doc.manifest.project_id)
        name = doc.manifest.project_name
        self._document = None
        self._autosave.mark_session_closed()
        logger.info("Project closed — {}", name)

    def duplicate_project(self, path: str | Path | None = None) -> ProjectDocument:
        source_doc = self._require_document()
        source_path = Path(path) if path else Path(source_doc.file_path)
        if source_path.is_file():
            base_doc, blobs = read_project_package(source_path)
        else:
            base_doc = source_doc
            blobs = dict(self._reference_images.byte_store.items())

        stem = source_path.stem if source_path.suffix else base_doc.manifest.project_name
        copy_path = source_path.parent / f"{stem}_Copy{GJS_EXTENSION}"
        counter = 2
        while copy_path.exists():
            copy_path = source_path.parent / f"{stem}_Copy_{counter}{GJS_EXTENSION}"
            counter += 1

        manifest = base_doc.manifest.model_copy(
            update={
                "project_id": uuid4().hex[:12],
                "project_name": f"{base_doc.manifest.project_name} (Copy)",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "modified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        document = ProjectDocument(manifest=manifest, history=base_doc.history.model_copy(deep=True))
        if base_doc.design_spec is not None:
            document.design_spec = base_doc.design_spec.model_copy(deep=True)
        else:
            document.design_spec = DesignSpecification.from_manifest(manifest)
        if base_doc.reference_manifest is not None:
            document.reference_manifest = base_doc.reference_manifest.model_copy(deep=True)
        else:
            document.reference_manifest = ReferenceImageManifest()
        if base_doc.vision_analyses is not None:
            document.vision_analyses = base_doc.vision_analyses.model_copy(deep=True)
        else:
            document.vision_analyses = VisionAnalysisArchive()
        if base_doc.interpretation_results is not None:
            document.interpretation_results = base_doc.interpretation_results.model_copy(deep=True)
        else:
            document.interpretation_results = InterpretationArchive()
        self._history.record(
            document,
            HistoryEventType.DUPLICATED,
            application_version=self._application_version,
            user=manifest.author,
            details=f"Duplicated from {source_path}",
        )
        write_project_package(document, copy_path, reference_blobs=blobs)
        self._open_document(document, blobs=blobs, record_open=False)
        logger.info("Project duplicated — {}", copy_path)
        return document

    def archive_project(self) -> ProjectDocument:
        document = self._require_document()
        document.manifest.status = ProjectStatus.ARCHIVED
        document.manifest.touch_modified()
        document.mark_dirty()
        self._history.record(
            document,
            HistoryEventType.ARCHIVED,
            application_version=self._application_version,
            user=document.manifest.author,
        )
        self.save_project()
        logger.info("Project archived — {}", document.manifest.project_name)
        return document

    def delete_project_file(self, path: str | Path) -> None:
        target = Path(path).expanduser().resolve()
        if self._document and self._document.file_path == str(target):
            self.close_project(save_if_dirty=False)
        if target.is_file():
            target.unlink()
        self._recent.remove(target)
        logger.info("Project deleted — {}", target)

    def restore_recovery(self, recovery_path: Path, primary_path: str, project_name: str = "") -> ProjectDocument:
        doc, blobs = read_project_package(recovery_path)
        doc.file_path = primary_path
        doc.mark_dirty()
        self._history.record(
            doc,
            HistoryEventType.RECOVERY_RESTORED,
            application_version=self._application_version,
            user=doc.manifest.author,
            details=f"Restored from {recovery_path}",
        )
        self._open_document(doc, blobs=blobs, record_open=False)
        logger.info(
            "Recovery restored — {} from {}",
            project_name or doc.manifest.project_name,
            recovery_path,
        )
        return doc

    def run_autosave(self) -> Path | None:
        if self._document is None:
            return None
        return self._autosave.autosave(self._document, reference_blobs=self._reference_blobs())

    def default_project_folder(self) -> Path:
        folder = self._recent.settings_manager.settings.default_project_folder.strip()
        if folder:
            return Path(folder).expanduser()
        from core.paths import PROJECTS_DIR

        return PROJECTS_DIR

    def set_default_project_folder(self, folder: str | Path) -> Path:
        path = Path(folder).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        settings = self._recent.settings_manager.settings.model_copy(
            update={"default_project_folder": str(path)}
        )
        self._recent.settings_manager._settings = settings
        self._recent.settings_manager.save()
        return path

    @property
    def interpretation_service(self) -> InterpretationService:
        return self._interpretation

    @property
    def vision_analysis_service(self) -> VisionAnalysisService:
        return self._vision

    @property
    def reference_image_service(self) -> ReferenceImageService:
        return self._reference_images

    @property
    def design_specification_service(self) -> DesignSpecificationService:
        return self._design_spec

    @property
    def recent_projects(self) -> RecentProjectsManager:
        return self._recent

    def _open_document(
        self,
        document: ProjectDocument,
        *,
        blobs: dict[str, bytes] | None = None,
        record_open: bool = True,
    ) -> None:
        self._workspace.ensure_project_workspace(document.manifest.project_id)
        if record_open:
            self._history.record(
                document,
                HistoryEventType.OPENED,
                application_version=self._application_version,
                user=document.manifest.author,
            )
            if document.file_path:
                write_project_package(
                    document,
                    Path(document.file_path),
                    reference_blobs=blobs or {},
                )
        self._document = document
        self._design_spec.reset_undo()
        manifest = document.reference_manifest or ReferenceImageManifest()
        document.reference_manifest = manifest
        self._reference_images.load(manifest, blobs or {})
        vision_archive = document.vision_analyses or VisionAnalysisArchive()
        document.vision_analyses = vision_archive
        self._vision.load(vision_archive)
        interpretation_archive = document.interpretation_results or InterpretationArchive()
        document.interpretation_results = interpretation_archive
        self._interpretation.load(interpretation_archive)
        for image in manifest.images:
            data = self._reference_images.image_bytes(image.image_id)
            if data:
                self._reference_images._thumbnails.generate(
                    document.manifest.project_id,
                    image.image_id,
                    data,
                    orientation=image.orientation,
                )
        self._register_recent(document)
        self._autosave.mark_session_open(document)

    def _reference_blobs(self) -> dict[str, bytes]:
        return dict(self._reference_images.byte_store.items())

    def _register_recent(self, document: ProjectDocument) -> None:
        if not document.file_path:
            return
        self._recent.add(
            document.file_path,
            name=document.manifest.project_name,
            club=document.manifest.club_name,
            season=document.manifest.season,
        )

    def _require_document(self) -> ProjectDocument:
        if self._document is None:
            raise ProjectFormatError("No project is currently loaded.")
        return self._document
