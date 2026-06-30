"""Reference image lifecycle — import, replace, delete, history, validation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from models.project import HistoryEventType, ProjectDocument, ValidationStatus
from models.reference_image import (
    ReferenceImageManifest,
    ReferenceImageRecord,
)
from services.logging_manager import get_logger
from services.project_history_service import ProjectHistoryService
from services.reference_image_io import (
    ReferenceImageImportError,
    checksum_sha256,
    extract_metadata,
    media_type_for_extension,
    read_source_bytes,
)
from services.reference_image_store import ReferenceImageByteStore, storage_path_for
from services.reference_image_validation import (
    ReferenceValidationResult,
    missing_categories,
    validate_reference_manifest,
)
from services.reference_thumbnail_service import ReferenceThumbnailService
from services.workspace_service import WorkspaceService

logger = get_logger()

REFERENCES_MANIFEST_NAME = "references/manifest.json"


class ReferenceImageService:
    """Manage immutable reference images for the active project."""

    def __init__(
        self,
        workspace: WorkspaceService,
        history_service: ProjectHistoryService | None = None,
        *,
        application_version: str = "",
    ) -> None:
        self._workspace = workspace
        self._history = history_service or ProjectHistoryService()
        self._application_version = application_version
        self._thumbnails = ReferenceThumbnailService(workspace)
        self._bytes = ReferenceImageByteStore()
        self._manifest = ReferenceImageManifest()

    @property
    def manifest(self) -> ReferenceImageManifest:
        return self._manifest

    @property
    def byte_store(self) -> ReferenceImageByteStore:
        return self._bytes

    def reset(self) -> None:
        self._bytes.clear()
        self._manifest = ReferenceImageManifest()

    def load(self, manifest: ReferenceImageManifest, blobs: dict[str, bytes]) -> None:
        self._manifest = manifest
        self._bytes.clear()
        for path, data in blobs.items():
            self._bytes.put(path, data)

    def ensure_manifest(self, document: ProjectDocument) -> ReferenceImageManifest:
        if document.reference_manifest is None:
            document.reference_manifest = ReferenceImageManifest()
        self._manifest = document.reference_manifest
        return self._manifest

    def validate(self, manifest: ReferenceImageManifest | None = None) -> ReferenceValidationResult:
        return validate_reference_manifest(manifest or self._manifest)

    def missing_categories(self) -> list[str]:
        return missing_categories(self._manifest)

    def import_files(
        self,
        document: ProjectDocument,
        paths: list[str | Path],
        *,
        user: str,
        tags: list[str] | None = None,
    ) -> list[ReferenceImageRecord]:
        manifest = self.ensure_manifest(document)
        imported: list[ReferenceImageRecord] = []
        for path in paths:
            record = self._import_single(document, Path(path), user=user, tags=tags or [])
            imported.append(record)
            manifest.images.append(record)
        self._sync_document(document)
        return imported

    def _import_single(
        self,
        document: ProjectDocument,
        source: Path,
        *,
        user: str,
        tags: list[str],
    ) -> ReferenceImageRecord:
        data, ext = read_source_bytes(source)
        meta = extract_metadata(data, ext=ext)
        image_id = uuid4().hex[:16]
        storage = storage_path_for(image_id, ext)
        checksum = checksum_sha256(data)

        record = ReferenceImageRecord(
            image_id=image_id,
            filename=source.name,
            width=int(meta["width"]),
            height=int(meta["height"]),
            file_size=len(data),
            colour_profile=str(meta.get("colour_profile", "")),
            orientation=int(meta.get("orientation", 0)),
            checksum=checksum,
            tags=list(tags),
            storage_path=storage,
            media_type=media_type_for_extension(ext),
            sort_order=len(self._manifest.images),
        )
        validation = validate_reference_manifest(
            ReferenceImageManifest(images=[*self._manifest.images, record])
        )
        record.validation_status = validation.status

        self._bytes.put(storage, data)
        self._thumbnails.generate(
            document.manifest.project_id,
            image_id,
            data,
            orientation=record.orientation,
        )
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_IMPORTED,
            user,
            {"image_id": image_id, "filename": record.filename},
        )
        logger.info("Reference image imported — {} ({})", record.filename, image_id)
        return record

    def delete_image(self, document: ProjectDocument, image_id: str, *, user: str) -> None:
        manifest = self.ensure_manifest(document)
        index = manifest.index_of(image_id)
        if index < 0:
            return
        record = manifest.images.pop(index)
        self._bytes.remove(record.storage_path)
        self._thumbnails.remove(document.manifest.project_id, image_id)
        self._sync_document(document)
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_DELETED,
            user,
            {"image_id": image_id, "filename": record.filename},
        )
        logger.info("Reference image deleted — {} ({})", record.filename, image_id)

    def replace_image(
        self,
        document: ProjectDocument,
        image_id: str,
        source: str | Path,
        *,
        user: str,
    ) -> ReferenceImageRecord:
        manifest = self.ensure_manifest(document)
        index = manifest.index_of(image_id)
        if index < 0:
            raise ReferenceImageImportError(f"Image not found: {image_id}")
        old = manifest.images[index]
        data, ext = read_source_bytes(Path(source))
        meta = extract_metadata(data, ext=ext)
        storage = storage_path_for(image_id, ext)
        self._bytes.remove(old.storage_path)
        self._bytes.put(storage, data)
        record = old.model_copy(
            update={
                "filename": Path(source).name,
                "width": int(meta["width"]),
                "height": int(meta["height"]),
                "file_size": len(data),
                "colour_profile": str(meta.get("colour_profile", "")),
                "checksum": checksum_sha256(data),
                "storage_path": storage,
                "media_type": media_type_for_extension(ext),
                "orientation": 0,
            }
        )
        manifest.images[index] = record
        self._thumbnails.generate(document.manifest.project_id, image_id, data)
        self._sync_document(document)
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_REPLACED,
            user,
            {"image_id": image_id, "filename": record.filename},
        )
        logger.info("Reference image replaced — {} ({})", record.filename, image_id)
        return record

    def duplicate_image(self, document: ProjectDocument, image_id: str, *, user: str) -> ReferenceImageRecord:
        manifest = self.ensure_manifest(document)
        source = manifest.get(image_id)
        if source is None:
            raise ReferenceImageImportError(f"Image not found: {image_id}")
        data = self._bytes.get(source.storage_path)
        if data is None:
            raise ReferenceImageImportError("Image bytes not available")
        new_id = uuid4().hex[:16]
        ext = Path(source.storage_path).suffix
        storage = storage_path_for(new_id, ext)
        record = source.model_copy(
            update={
                "image_id": new_id,
                "filename": f"Copy of {source.filename}",
                "checksum": checksum_sha256(data),
                "storage_path": storage,
                "sort_order": len(manifest.images),
            }
        )
        self._bytes.put(storage, data)
        manifest.images.append(record)
        self._thumbnails.generate(document.manifest.project_id, new_id, data, orientation=record.orientation)
        self._sync_document(document)
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_IMPORTED,
            user,
            {"image_id": new_id, "filename": record.filename, "duplicated_from": image_id},
        )
        return record

    def rename_image(self, document: ProjectDocument, image_id: str, filename: str, *, user: str) -> None:
        manifest = self.ensure_manifest(document)
        record = manifest.get(image_id)
        if record is None:
            return
        old_name = record.filename
        record.filename = filename.strip()
        self._sync_document(document)
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_RENAMED,
            user,
            {"image_id": image_id, "old_filename": old_name, "new_filename": record.filename},
        )
        logger.info("Reference image renamed — {} → {}", old_name, record.filename)

    def retag_image(self, document: ProjectDocument, image_id: str, tags: list[str], *, user: str) -> None:
        manifest = self.ensure_manifest(document)
        record = manifest.get(image_id)
        if record is None:
            return
        old_tags = list(record.tags)
        record.tags = list(tags)
        validation = self.validate(manifest)
        record.validation_status = validation.status
        self._sync_document(document)
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_RETAGGED,
            user,
            {"image_id": image_id, "old_tags": old_tags, "new_tags": tags},
        )
        logger.info("Reference image retagged — {} ({})", record.filename, image_id)

    def rotate_image(self, document: ProjectDocument, image_id: str, *, user: str) -> None:
        manifest = self.ensure_manifest(document)
        record = manifest.get(image_id)
        if record is None:
            return
        data = self._bytes.get(record.storage_path)
        if data is None:
            return
        record.orientation = (record.orientation + 90) % 360
        self._thumbnails.generate(
            document.manifest.project_id,
            image_id,
            data,
            orientation=record.orientation,
        )
        self._sync_document(document)
        logger.info("Reference image rotated — {} to {}°", record.filename, record.orientation)

    def reorder_images(self, document: ProjectDocument, image_ids: list[str], *, user: str) -> None:
        manifest = self.ensure_manifest(document)
        lookup = {image.image_id: image for image in manifest.images}
        manifest.images = [lookup[image_id] for image_id in image_ids if image_id in lookup]
        for index, image in enumerate(manifest.images):
            image.sort_order = index
        self._sync_document(document)

    def record_viewed(self, document: ProjectDocument, image_id: str, *, user: str) -> None:
        record = self._manifest.get(image_id)
        if record is None:
            return
        self._record(
            document,
            HistoryEventType.REFERENCE_IMAGE_VIEWED,
            user,
            {"image_id": image_id, "filename": record.filename},
        )

    def image_bytes(self, image_id: str) -> bytes | None:
        record = self._manifest.get(image_id)
        if record is None:
            return None
        return self._bytes.get(record.storage_path)

    def thumbnail_path(self, project_id: str, image_id: str) -> Path:
        return self._thumbnails.thumbnail_path(project_id, image_id)

    def resolution_summary(self) -> str:
        if not self._manifest.images:
            return "No images"
        widths = [image.width for image in self._manifest.images]
        heights = [image.height for image in self._manifest.images]
        return f"{min(widths)}–{max(widths)} × {min(heights)}–{max(heights)} px"

    def _sync_document(self, document: ProjectDocument) -> None:
        document.reference_manifest = self._manifest
        document.manifest.reference_image_count = len(self._manifest.images)
        validation = self.validate(self._manifest)
        document.manifest.validation_status = validation.status
        document.manifest.touch_modified()
        document.mark_dirty()

    def _record(
        self,
        document: ProjectDocument,
        event: HistoryEventType,
        user: str,
        payload: dict[str, object],
    ) -> None:
        self._history.record(
            document,
            event,
            application_version=self._application_version,
            user=user,
            details=json.dumps(payload, ensure_ascii=False),
        )
