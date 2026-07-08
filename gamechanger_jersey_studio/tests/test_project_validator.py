"""Project validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.project import KitType, NewProjectRequest
from services.project_validator import (
    ProjectValidationError,
    assert_valid_new_project,
    default_project_file_path,
    validate_new_project_request,
)


def test_validate_new_project_request_success(tmp_path: Path) -> None:
    request = NewProjectRequest(
        project_name="A",
        club_name="B",
        competition="C",
        season="2025/26",
        kit_type=KitType.AWAY,
        output_folder=str(tmp_path),
        author="Author",
    )
    assert validate_new_project_request(request) == []


def test_validate_new_project_request_missing_fields() -> None:
    request = NewProjectRequest(
        project_name="",
        club_name="",
        competition="",
        season="",
        kit_type=KitType.HOME,
        output_folder="",
        author="",
    )
    errors = validate_new_project_request(request)
    assert len(errors) >= 5


def test_assert_valid_new_project_raises() -> None:
    request = NewProjectRequest(
        project_name="",
        club_name="Club",
        competition="Comp",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Author",
    )
    with pytest.raises(ProjectValidationError):
        assert_valid_new_project(request)


def test_default_project_file_path(tmp_path: Path) -> None:
    request = NewProjectRequest(
        project_name="My Team Kit",
        club_name="Club",
        competition="Comp",
        season="2025/26",
        kit_type=KitType.THIRD,
        output_folder=str(tmp_path),
        author="Author",
    )
    path = default_project_file_path(request)
    assert path.parent == tmp_path.resolve()
    assert path.suffix == ".gjs"
