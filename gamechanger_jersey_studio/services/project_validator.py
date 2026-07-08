"""Validation for project creation and packaging."""

from __future__ import annotations

from pathlib import Path

from models.project import GJS_EXTENSION, NewProjectRequest


class ProjectValidationError(ValueError):
    """Raised when project fields fail validation."""


def validate_new_project_request(request: NewProjectRequest) -> list[str]:
    """Return list of validation error messages (empty if valid)."""
    errors: list[str] = []
    if not request.project_name.strip():
        errors.append("Project Name is required.")
    if not request.club_name.strip():
        errors.append("Club Name is required.")
    if not request.competition.strip():
        errors.append("Competition is required.")
    if not request.season.strip():
        errors.append("Season is required.")
    if not request.author.strip():
        errors.append("Author is required.")
    if not request.output_folder.strip():
        errors.append("Output Folder is required.")
    else:
        folder = Path(request.output_folder).expanduser()
        if not folder.is_absolute() and not str(folder).startswith("~"):
            try:
                folder = folder.resolve()
            except OSError:
                errors.append("Output Folder path is invalid.")
    if not request.build_profile.strip():
        errors.append("Build Profile is required.")
    return errors


def assert_valid_new_project(request: NewProjectRequest) -> None:
    errors = validate_new_project_request(request)
    if errors:
        raise ProjectValidationError("; ".join(errors))


def default_project_file_path(request: NewProjectRequest) -> Path:
    folder = Path(request.output_folder).expanduser().resolve()
    safe_name = _safe_filename(request.project_name)
    return folder / f"{safe_name}{GJS_EXTENSION}"


def _safe_filename(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name.strip())
    return cleaned.replace(" ", "_") or "Untitled_Project"
