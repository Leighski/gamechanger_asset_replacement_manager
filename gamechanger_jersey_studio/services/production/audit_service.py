"""Production audit trail — chain of custody for rendered artwork."""

from __future__ import annotations

import json
from pathlib import Path

from core.version import APP_VERSION
from models.interpretation import INTERPRETATION_ENGINE_VERSION
from models.learning import LEARNING_MODE_VERSION
from models.production import AuditChainLink, ProductionAuditRecord
from models.project import HistoryEventType, ProjectDocument
from models.psd_render import PSD_RENDERER_VERSION
from services.logging_manager import get_logger
from services.project_history_service import ProjectHistoryService

logger = get_logger()


class ProductionAuditService:
    """Build and record complete production audit chains."""

    def __init__(self, history: ProjectHistoryService | None = None) -> None:
        self._history = history or ProjectHistoryService()
        self._records: list[ProductionAuditRecord] = []

    @property
    def records(self) -> list[ProductionAuditRecord]:
        return list(self._records)

    def build_chain(
        self,
        document: ProjectDocument,
        *,
        render_psd_path: str,
        render_png_path: str,
        template_id: str,
        template_version: str,
        render_log_path: str = "",
    ) -> ProductionAuditRecord:
        chain: list[AuditChainLink] = []

        if document.reference_manifest:
            for image in document.reference_manifest.images:
                try:
                    chain.append(
                        AuditChainLink(
                            link_type="Reference Image",
                            identifier=image.image_id,
                            version=image.filename,
                            timestamp=image.import_timestamp(),
                            details=image.audit_details(),
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Audit: skipped reference image {} — {}",
                        getattr(image, "image_id", "?"),
                        exc,
                    )

        if document.vision_analyses:
            for analysis in document.vision_analyses.analyses:
                chain.append(
                    AuditChainLink(
                        link_type="Vision Analysis",
                        identifier=analysis.analysis_id,
                        version=analysis.engine_version,
                        timestamp=analysis.created_at,
                        details=f"image={analysis.image_id}",
                    )
                )

        if document.interpretation_results:
            for interpretation in document.interpretation_results.interpretations:
                chain.append(
                    AuditChainLink(
                        link_type="AI Interpretation",
                        identifier=interpretation.interpretation_id,
                        version=interpretation.engine_version or INTERPRETATION_ENGINE_VERSION,
                        timestamp=interpretation.created_at,
                        details=f"provider={interpretation.ai_provider}",
                    )
                )
            for feedback in document.interpretation_results.feedback:
                chain.append(
                    AuditChainLink(
                        link_type="Operator Decision",
                        identifier=feedback.suggestion_id,
                        version=feedback.decision.value,
                        timestamp=feedback.timestamp,
                        details=f"field={feedback.target_field}",
                    )
                )

        if document.learning_record:
            for rule_id in document.learning_record.rules_applied:
                chain.append(
                    AuditChainLink(
                        link_type="Learning Rule Applied",
                        identifier=rule_id,
                        version=LEARNING_MODE_VERSION,
                        details="advisory recommendation evaluated",
                    )
                )
            for rec_id in document.learning_record.recommendations_accepted:
                chain.append(
                    AuditChainLink(
                        link_type="Learning Recommendation Accepted",
                        identifier=rec_id,
                        version=LEARNING_MODE_VERSION,
                        details="operator accepted advisory",
                    )
                )
            for rec_id in document.learning_record.recommendations_ignored:
                chain.append(
                    AuditChainLink(
                        link_type="Learning Recommendation Ignored",
                        identifier=rec_id,
                        version=LEARNING_MODE_VERSION,
                        details="operator ignored advisory",
                    )
                )

        spec_version = document.manifest.modified_at
        chain.append(
            AuditChainLink(
                link_type="Design Specification",
                identifier=document.manifest.project_id,
                version=spec_version,
                timestamp=document.manifest.modified_at,
                details=document.manifest.project_name,
            )
        )

        chain.append(
            AuditChainLink(
                link_type="Template",
                identifier=template_id,
                version=template_version,
                details="Published template mappings",
            )
        )

        chain.append(
            AuditChainLink(
                link_type="Renderer",
                identifier="PSDRenderService",
                version=PSD_RENDERER_VERSION,
                details=render_log_path,
            )
        )

        chain.append(
            AuditChainLink(
                link_type="PSD Output",
                identifier=Path(render_psd_path).name,
                version=APP_VERSION,
                details=render_psd_path,
            )
        )

        chain.append(
            AuditChainLink(
                link_type="PNG Preview",
                identifier=Path(render_png_path).name,
                version=APP_VERSION,
                details=render_png_path,
            )
        )

        record = ProductionAuditRecord(
            project_path=document.file_path or "",
            project_name=document.manifest.project_name,
            render_psd_path=render_psd_path,
            render_png_path=render_png_path,
            chain=chain,
        )
        self._records.append(record)
        return record

    def record_audit(
        self,
        document: ProjectDocument,
        record: ProductionAuditRecord,
        *,
        user: str,
        application_version: str = APP_VERSION,
    ) -> None:
        self._history.record(
            document,
            HistoryEventType.PRODUCTION_AUDIT_RECORDED,
            application_version=application_version,
            user=user,
            details=json.dumps(
                {
                    "audit_id": record.audit_id,
                    "render_psd_path": record.render_psd_path,
                    "chain_length": len(record.chain),
                },
                ensure_ascii=False,
            ),
        )
        logger.info("Production audit recorded — {}", record.audit_id)

    def suggestion_decisions_from_history(self, document: ProjectDocument) -> list[dict[str, object]]:
        events = {
            HistoryEventType.SUGGESTION_ACCEPTED,
            HistoryEventType.SUGGESTION_REJECTED,
            HistoryEventType.SUGGESTION_MODIFIED,
        }
        decisions: list[dict[str, object]] = []
        for entry in document.history.entries:
            if entry.event not in events:
                continue
            try:
                payload = json.loads(entry.details) if entry.details else {}
            except json.JSONDecodeError:
                payload = {"raw": entry.details}
            decisions.append(
                {
                    "timestamp": entry.timestamp,
                    "event": entry.event.value,
                    "user": entry.user,
                    "application_version": entry.application_version,
                    **payload,
                }
            )
        return decisions
