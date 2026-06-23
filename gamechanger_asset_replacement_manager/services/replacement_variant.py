"""ENGP / CFX filename typing and stem association."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

_ENGP_NAME_RE = re.compile(r"^.+_ENGP\.mp4$", re.IGNORECASE)
_CFX_NAME_RE = re.compile(r"^.+_CFX\.mp4$", re.IGNORECASE)


class ReplacementAssetType(str, Enum):
    ENGP = "ENGP"
    CFX = "CFX"


def detect_replacement_type(filename: str) -> ReplacementAssetType | None:
    name = Path(filename).name
    if _ENGP_NAME_RE.match(name):
        return ReplacementAssetType.ENGP
    if _CFX_NAME_RE.match(name):
        return ReplacementAssetType.CFX
    return None


def engp_association_stem(filename: str) -> str:
    """ARS_CHE_19980308_G_03_ENGP.mp4 → ARS_CHE_19980308_G_03"""
    stem = Path(filename).stem
    if stem.upper().endswith("_ENGP"):
        return stem[: -len("_ENGP")]
    return stem


def cfx_association_stem(filename: str) -> str:

    stem = Path(filename).stem

    upper = stem.upper()

    if upper.endswith("_ENGP_CFX"):

        return stem[: -len("_ENGP_CFX")]

    if upper.endswith("_CFX"):

        return stem[: -len("_CFX")]

    return stem


def stems_associated(engp_filename: str, cfx_filename: str) -> bool:
    return engp_association_stem(engp_filename).lower() == cfx_association_stem(cfx_filename).lower()


def expected_cfx_filename(engp_filename: str) -> str:
    return f"{engp_association_stem(engp_filename)}_CFX.mp4"


def expected_engp_filename(cfx_filename: str) -> str:
    return f"{cfx_association_stem(cfx_filename)}_ENGP.mp4"
