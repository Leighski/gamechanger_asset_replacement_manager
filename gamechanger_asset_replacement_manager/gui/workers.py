"""Background workers for long-running operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from models.catalogue import CatalogueDefinition
from models.discovery import DiscoveryResult, PreflightRow, SanitisationOptions
from models.upload import AuditRecord, UploadProgress
from models.validation import ValidationResult
from services.asset_resolution_service import AssetResolutionResult
from services.bulk_governance_service import (
    apply_governance_results,
    build_governed_summary,
    build_governed_upload_jobs,
    resolve_governance_for_preflight,
)
from services.file_discovery import FileDiscoveryService
from services.preflight_validator import PreflightValidator
from services.dual_replacement_service import DualReplacementService
from services.upload_engine import UploadEngine
from services.iconik_verification import IconikVerificationService


class ScanWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        source: Path,
        options: SanitisationOptions,
    ) -> None:
        super().__init__()
        self._source = source
        self._options = options

    @Slot()
    def run(self) -> None:
        try:
            result = FileDiscoveryService().scan(self._source, self._options)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class PreflightWorker(QObject):
    """Emits a single ValidationResult object for reliable cross-thread delivery."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        validator: PreflightValidator,
        discovery: DiscoveryResult,
        catalogue: CatalogueDefinition,
        *,
        replace_existing_only: bool,
    ) -> None:
        super().__init__()
        self._validator = validator
        self._discovery = discovery
        self._catalogue = catalogue
        self._replace_existing_only = replace_existing_only

    @Slot()
    def run(self) -> None:
        try:
            rows, summary = self._validator.validate(
                self._discovery,
                self._catalogue,
                replace_existing_only=self._replace_existing_only,
            )
            payload = self._validator.build_validation_result(rows, summary)
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))


class GovernanceWorker(QObject):
    """Iconik governance pass for Source Files S3 REPLACE candidates."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        rows: list[PreflightRow],
        discovery: DiscoveryResult,
        catalogue: CatalogueDefinition,
        iconik: IconikVerificationService,
        preflight_payload: ValidationResult,
    ) -> None:
        super().__init__()
        self._rows = rows
        self._discovery = discovery
        self._catalogue = catalogue
        self._iconik = iconik
        self._preflight_payload = preflight_payload

    @Slot()
    def run(self) -> None:
        try:
            from models.validation import build_validated_files, build_validation_result

            rows = list(self._rows)
            resolutions = resolve_governance_for_preflight(
                rows,
                catalogue=self._catalogue,
                iconik=self._iconik,
            )
            apply_governance_results(rows, resolutions)
            summary = build_governed_summary(rows, self._discovery)
            upload_jobs = build_governed_upload_jobs(rows)
            payload = build_validation_result(rows, summary, upload_jobs)
            payload.resolution_results = resolutions
            payload.governance_complete = True
            payload.validated_files = build_validated_files(rows)
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))


class UploadWorker(QObject):
    progress = Signal(object)
    record = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        engine: UploadEngine,
        jobs: list,
        catalogue: CatalogueDefinition,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._jobs = jobs
        self._catalogue = catalogue

    @Slot()
    def run(self) -> None:
        try:
            records = self._engine.run(
                self._jobs,
                self._catalogue,
                on_progress=lambda p: self.progress.emit(p),
                on_record=lambda r: self.record.emit(r),
            )
            self.finished.emit(records)
        except Exception as exc:
            self.failed.emit(str(exc))


class DualReplacementWorker(QObject):
    log_line = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: DualReplacementService,
        *,
        engp_path: str,
        cfx_path: str,
        catalogue: CatalogueDefinition,
        resolutions: list[AssetResolutionResult],
        preserve_asset_ids: bool = True,
    ) -> None:
        super().__init__()
        self._service = service
        self._engp_path = engp_path
        self._cfx_path = cfx_path
        self._catalogue = catalogue
        self._resolutions = resolutions
        self._preserve_asset_ids = preserve_asset_ids

    @Slot()
    def run(self) -> None:
        try:
            targets = self._service.build_targets(
                engp_path=self._engp_path,
                cfx_path=self._cfx_path,
                catalogue=self._catalogue,
            )
            outcome = self._service.run(
                targets,
                self._resolutions,
                self._catalogue,
                preserve_asset_ids=self._preserve_asset_ids,
                log=lambda msg: self.log_line.emit(msg),
            )
            self.finished.emit(outcome)
        except Exception as exc:
            self.failed.emit(str(exc))


def run_in_thread(worker: QObject, parent: QObject | None = None) -> QThread:
    thread = QThread(parent)
    worker.setParent(thread)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    return thread
