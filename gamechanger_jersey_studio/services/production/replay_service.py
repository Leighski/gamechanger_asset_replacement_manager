"""Production Replay — step through the complete production chain."""

from __future__ import annotations

import json

from models.project import HistoryEventType, ProjectDocument
from models.psd_template import UNKNOWN_TEMPLATE_LABEL, TemplateProjectSettings
from models.reference_image import ReferenceImageRecord
from models.validation import ProductionReplay, ProductionReplayStep, ReplayStageType
from services.logging_manager import get_logger

logger = get_logger()

_RENDER_EVENTS = {
    HistoryEventType.RENDER_STARTED,
    HistoryEventType.RENDER_COMPLETED,
    HistoryEventType.RENDER_FAILED,
    HistoryEventType.PSD_SAVED,
    HistoryEventType.PNG_GENERATED,
}


class ReplayService:
    """Build a forward/backward replay chain from project data."""

    def build_replay(self, document: ProjectDocument) -> ProductionReplay:
        steps: list[ProductionReplayStep] = []
        idx = 0

        idx = self._append_reference_images(document, steps, idx)
        idx = self._append_vision_analyses(document, steps, idx)
        idx = self._append_interpretation(document, steps, idx)
        idx = self._append_design_spec(document, steps, idx)
        idx = self._append_template(document, steps, idx)
        idx = self._append_render_history(document, steps, idx)

        return ProductionReplay(
            project_name=document.manifest.project_name,
            project_path=document.file_path,
            steps=steps,
            current_step=0,
        )

    def _append_reference_images(
        self,
        document: ProjectDocument,
        steps: list[ProductionReplayStep],
        idx: int,
    ) -> int:
        if not document.reference_manifest or not document.reference_manifest.images:
            return idx
        try:
            images = self._reference_image_entries(document.reference_manifest.images)
            steps.append(
                ProductionReplayStep(
                    step_index=idx,
                    stage=ReplayStageType.REFERENCE_IMAGES,
                    title=f"{len(document.reference_manifest.images)} reference image(s)",
                    summary="Imported reference images for vision analysis",
                    details={"images": images},
                )
            )
            return idx + 1
        except Exception as exc:
            logger.warning("Replay: skipped reference images — {}", exc)
            return idx

    def _reference_image_entries(self, images: list[ReferenceImageRecord]) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for image in images:
            try:
                entries.append(image.replay_entry())
            except Exception as exc:
                logger.warning(
                    "Replay: skipped reference image {} — {}",
                    getattr(image, "image_id", "?"),
                    exc,
                )
        return entries

    def _append_vision_analyses(
        self,
        document: ProjectDocument,
        steps: list[ProductionReplayStep],
        idx: int,
    ) -> int:
        if not document.vision_analyses:
            return idx
        for analysis in document.vision_analyses.analyses:
            try:
                colour_count = len(getattr(analysis, "colours", []) or [])
                steps.append(
                    ProductionReplayStep(
                        step_index=idx,
                        stage=ReplayStageType.VISION_ANALYSIS,
                        title=f"Vision — {analysis.analysis_id[:8]}",
                        timestamp=getattr(analysis, "created_at", "") or "",
                        summary=f"Engine {getattr(analysis, 'engine_version', '')}",
                        details={
                            "image_id": getattr(analysis, "image_id", ""),
                            "measurements": colour_count,
                        },
                    )
                )
                idx += 1
            except Exception as exc:
                logger.warning("Replay: skipped vision analysis step — {}", exc)
        return idx

    def _append_interpretation(
        self,
        document: ProjectDocument,
        steps: list[ProductionReplayStep],
        idx: int,
    ) -> int:
        if not document.interpretation_results:
            return idx
        try:
            for interpretation in document.interpretation_results.interpretations:
                steps.append(
                    ProductionReplayStep(
                        step_index=idx,
                        stage=ReplayStageType.AI_INTERPRETATION,
                        title=f"AI — {interpretation.interpretation_id[:8]}",
                        timestamp=interpretation.created_at,
                        summary=f"{len(interpretation.suggestions)} suggestions",
                        details={
                            "provider": interpretation.ai_provider,
                            "suggestion_count": len(interpretation.suggestions),
                        },
                    )
                )
                idx += 1

            recs = []
            for interpretation in document.interpretation_results.interpretations:
                for rec in interpretation.learning_recommendations:
                    recs.append(rec.model_dump(mode="json"))
            if recs:
                steps.append(
                    ProductionReplayStep(
                        step_index=idx,
                        stage=ReplayStageType.LEARNING_RECOMMENDATIONS,
                        title=f"{len(recs)} learning recommendation(s)",
                        summary="Advisory rules evaluated — never auto-applied",
                        details={"recommendations": recs},
                    )
                )
                idx += 1

            for feedback in document.interpretation_results.feedback:
                steps.append(
                    ProductionReplayStep(
                        step_index=idx,
                        stage=ReplayStageType.OPERATOR_DECISIONS,
                        title=f"{feedback.decision.value} — {feedback.target_field}",
                        timestamp=feedback.timestamp,
                        summary=feedback.final_value or feedback.proposed_value,
                        details=feedback.model_dump(mode="json"),
                    )
                )
                idx += 1
        except Exception as exc:
            logger.warning("Replay: skipped interpretation steps — {}", exc)
        return idx

    def _append_design_spec(
        self,
        document: ProjectDocument,
        steps: list[ProductionReplayStep],
        idx: int,
    ) -> int:
        if not document.design_spec:
            return idx
        try:
            steps.append(
                ProductionReplayStep(
                    step_index=idx,
                    stage=ReplayStageType.DESIGN_SPECIFICATION,
                    title=document.design_spec.club or document.manifest.project_name,
                    summary=f"Validation: {document.design_spec.validation_status.value}",
                    details={
                        "club": document.design_spec.club,
                        "pattern": document.design_spec.pattern,
                        "collar_style": document.design_spec.collar_style,
                    },
                )
            )
            return idx + 1
        except Exception as exc:
            logger.warning("Replay: skipped design specification step — {}", exc)
            return idx

    def _append_template(
        self,
        document: ProjectDocument,
        steps: list[ProductionReplayStep],
        idx: int,
    ) -> int:
        settings = document.template_settings
        if settings is not None:
            identifier = settings.template_identifier()
            version = settings.template_version_label()
            details = settings.replay_details()
        else:
            identifier = UNKNOWN_TEMPLATE_LABEL
            version = ""
            details = {"active_template_id": identifier}
        steps.append(
            ProductionReplayStep(
                step_index=idx,
                stage=ReplayStageType.TEMPLATE_SELECTION,
                title=identifier,
                summary=version,
                details=details,
            )
        )
        return idx + 1

    def _append_render_history(
        self,
        document: ProjectDocument,
        steps: list[ProductionReplayStep],
        idx: int,
    ) -> int:
        for entry in document.history.entries:
            if entry.event not in _RENDER_EVENTS:
                continue
            try:
                payload = json.loads(entry.details) if entry.details else {}
            except json.JSONDecodeError:
                payload = {"raw": entry.details}
            stage = ReplayStageType.PSD_RENDERING
            if entry.event == HistoryEventType.PNG_GENERATED:
                stage = ReplayStageType.FINAL_EXPORT
            steps.append(
                ProductionReplayStep(
                    step_index=idx,
                    stage=stage,
                    title=entry.event.value,
                    timestamp=entry.timestamp,
                    summary=entry.user,
                    details=payload,
                )
            )
            idx += 1
        return idx

    def step_forward(self, replay: ProductionReplay) -> ProductionReplay:
        if replay.current_step < len(replay.steps) - 1:
            replay.current_step += 1
        return replay

    def step_backward(self, replay: ProductionReplay) -> ProductionReplay:
        if replay.current_step > 0:
            replay.current_step -= 1
        return replay

    def current_step(self, replay: ProductionReplay) -> ProductionReplayStep | None:
        if not replay.steps:
            return None
        index = max(0, min(replay.current_step, len(replay.steps) - 1))
        return replay.steps[index]
