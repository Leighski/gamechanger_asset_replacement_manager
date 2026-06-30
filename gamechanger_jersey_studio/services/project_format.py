"""Read and write native .gjs project packages."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from models.design_specification import DesignSpecification
from models.project import GJS_EXTENSION, ProjectDocument, ProjectHistory, ProjectManifest
from models.interpretation import InterpretationArchive
from models.reference_image import ReferenceImageManifest
from models.renderer import RendererSettings
from models.vision_analysis import VisionAnalysisArchive
from services.interpretation_service import INTERPRETATION_RESULTS_NAME
from services.live_renderer_service import RENDERER_SETTINGS_NAME
from services.reference_image_service import REFERENCES_MANIFEST_NAME
from services.vision_analysis_service import VISION_ANALYSES_NAME

MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
DESIGN_SPEC_NAME = "design/specification.json"
REFERENCES_PREFIX = "references/images/"


class ProjectFormatError(ValueError):
    """Raised when a .gjs package cannot be read or written."""


def write_project_package(
    document: ProjectDocument,
    path: Path,
    *,
    reference_blobs: dict[str, bytes] | None = None,
) -> Path:
    """Write a portable .gjs ZIP package."""
    target = Path(path).expanduser().resolve()
    if target.suffix.lower() != GJS_EXTENSION:
        target = target.with_suffix(GJS_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)

    manifest_json = json.dumps(
        document.manifest.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")
    history_json = json.dumps(
        document.history.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")

    design_spec = document.design_spec
    if design_spec is None:
        design_spec = DesignSpecification.from_manifest(document.manifest)

    design_json = json.dumps(
        design_spec.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")

    reference_manifest = document.reference_manifest or ReferenceImageManifest()
    reference_json = json.dumps(
        reference_manifest.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")

    vision_archive = document.vision_analyses or VisionAnalysisArchive()
    vision_json = json.dumps(
        vision_archive.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")

    interpretation_archive = document.interpretation_results or InterpretationArchive()
    interpretation_json = json.dumps(
        interpretation_archive.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")

    renderer_settings = document.renderer_settings or RendererSettings()
    renderer_json = json.dumps(
        renderer_settings.model_dump(mode="json"),
        indent=2,
    ).encode("utf-8")

    with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, manifest_json)
        zf.writestr(HISTORY_NAME, history_json)
        zf.writestr(DESIGN_SPEC_NAME, design_json)
        zf.writestr(REFERENCES_MANIFEST_NAME, reference_json)
        zf.writestr(VISION_ANALYSES_NAME, vision_json)
        zf.writestr(INTERPRETATION_RESULTS_NAME, interpretation_json)
        zf.writestr(RENDERER_SETTINGS_NAME, renderer_json)
        blobs = reference_blobs or {}
        for record in reference_manifest.images:
            data = blobs.get(record.storage_path)
            if data is not None:
                zf.writestr(record.storage_path, data)

    document.file_path = str(target)
    document.mark_saved()
    return target


def read_project_package(path: Path) -> tuple[ProjectDocument, dict[str, bytes]]:
    """Load a .gjs ZIP package into memory."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ProjectFormatError(f"Project file not found: {source}")
    if source.suffix.lower() != GJS_EXTENSION:
        raise ProjectFormatError(f"Not a Gamechanger Jersey Studio project: {source}")

    try:
        with zipfile.ZipFile(source, mode="r") as zf:
            manifest = _read_json_member(zf, MANIFEST_NAME)
            history_raw = _read_optional_json_member(zf, HISTORY_NAME)
            design_raw = _read_optional_json_member(zf, DESIGN_SPEC_NAME)
            reference_raw = _read_optional_json_member(zf, REFERENCES_MANIFEST_NAME)
            vision_raw = _read_optional_json_member(zf, VISION_ANALYSES_NAME)
            interpretation_raw = _read_optional_json_member(zf, INTERPRETATION_RESULTS_NAME)
            renderer_raw = _read_optional_json_member(zf, RENDERER_SETTINGS_NAME)
            blobs = _read_reference_blobs(zf)
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ProjectFormatError(f"Invalid .gjs package: {source}") from exc

    history = ProjectHistory.model_validate(history_raw) if history_raw else ProjectHistory()
    manifest_model = ProjectManifest.model_validate(manifest)
    if design_raw:
        design_spec = DesignSpecification.model_validate(design_raw)
    else:
        design_spec = DesignSpecification.from_manifest(manifest_model)

    if reference_raw:
        reference_manifest = ReferenceImageManifest.model_validate(reference_raw)
    else:
        reference_manifest = ReferenceImageManifest()

    if vision_raw:
        vision_analyses = VisionAnalysisArchive.model_validate(vision_raw)
    else:
        vision_analyses = VisionAnalysisArchive()

    if interpretation_raw:
        interpretation_results = InterpretationArchive.model_validate(interpretation_raw)
    else:
        interpretation_results = InterpretationArchive()

    if renderer_raw:
        renderer_settings = RendererSettings.model_validate(renderer_raw)
    else:
        renderer_settings = RendererSettings()

    doc = ProjectDocument(
        manifest=manifest_model,
        history=history,
        design_spec=design_spec,
        reference_manifest=reference_manifest,
        vision_analyses=vision_analyses,
        interpretation_results=interpretation_results,
        renderer_settings=renderer_settings,
        file_path=str(source),
        dirty=False,
    )
    return doc, blobs


def package_info(path: Path) -> dict[str, Any]:
    """Read manifest summary without loading full document."""
    doc, _ = read_project_package(path)
    return doc.manifest.model_dump(mode="json")


def _read_reference_blobs(zf: zipfile.ZipFile) -> dict[str, bytes]:
    blobs: dict[str, bytes] = {}
    for name in zf.namelist():
        if name.startswith(REFERENCES_PREFIX) and not name.endswith("/"):
            blobs[name] = zf.read(name)
    return blobs


def _read_json_member(zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        raw = zf.read(name)
    except KeyError as exc:
        raise ProjectFormatError(f"Missing {name} in .gjs package") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ProjectFormatError(f"{name} must be a JSON object")
    return data


def _read_optional_json_member(zf: zipfile.ZipFile, name: str) -> dict[str, Any] | None:
    try:
        return _read_json_member(zf, name)
    except ProjectFormatError:
        return None
