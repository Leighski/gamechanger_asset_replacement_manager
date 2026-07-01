"""Template Preview Generator — generate preview images without editing PSD."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from models.psd_template import PSDTemplate
from services.logging_manager import get_logger

logger = get_logger()


class TemplatePreviewGenerator:
    """Generate template preview thumbnails from PSD composite or fallback art."""

    def generate_fallback(self, template: PSDTemplate, *, size: tuple[int, int] = (400, 500)) -> bytes:
        width, height = size
        image = Image.new("RGBA", size, (26, 31, 46, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=12, fill=(40, 48, 64, 255))
        draw.text((40, 40), template.name, fill=(237, 237, 237, 255))
        draw.text((40, 72), f"v{template.version}", fill=(154, 154, 154, 255))
        draw.text((40, height - 72), template.template_id, fill=(90, 139, 229, 255))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def generate_from_psd(self, psd_path: Path, *, max_size: tuple[int, int] = (400, 500)) -> bytes:
        try:
            from psd_tools import PSDImage
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psd-tools is required for PSD preview generation") from exc
        psd = PSDImage.open(psd_path)
        composite = psd.composite()
        composite.thumbnail(max_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        composite.convert("RGBA").save(buffer, format="PNG")
        return buffer.getvalue()

    def ensure_preview(
        self,
        template: PSDTemplate,
        templates_root: Path,
        *,
        force: bool = False,
    ) -> Path | None:
        if template.preview_image:
            target = templates_root / template.slug / template.preview_image
            if target.is_file() and not force:
                return target
        slug_dir = templates_root / template.slug
        slug_dir.mkdir(parents=True, exist_ok=True)
        target = slug_dir / "preview.png"
        psd = templates_root / template.slug / Path(template.psd_path).name if template.psd_path else None
        if psd and psd.is_file():
            data = self.generate_from_psd(psd)
        else:
            data = self.generate_fallback(template)
        target.write_bytes(data)
        logger.info("Template preview generated — {}", template.template_id)
        return target
