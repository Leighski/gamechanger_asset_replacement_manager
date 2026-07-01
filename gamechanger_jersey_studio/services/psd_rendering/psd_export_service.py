"""PSD Export Service — save layered PSD, preview PNG, and render log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models.psd_render import PSDRenderLog


class PSDExportService:
    """Write production render outputs to the project export folder."""

    def build_output_dir(self, output_folder: str, project_name: str) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in project_name).strip("_")
        target = Path(output_folder).expanduser().resolve() / "renders" / f"{safe}_{stamp}"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def save_psd(self, psd, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        psd.save(path)
        return path

    def save_png_preview(self, psd, path: Path) -> Path:
        composite = psd.composite()
        composite.save(path, format="PNG")
        return path

    def save_render_log(self, log: PSDRenderLog, path: Path) -> Path:
        if not log.completed_at:
            log.completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path.write_text(json.dumps(log.model_dump(mode="json"), indent=2), encoding="utf-8")
        return path
