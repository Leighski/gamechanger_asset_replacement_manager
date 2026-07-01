"""Visual comparison — pixel diff and layer visibility."""

from __future__ import annotations

from pathlib import Path

from models.validation import LayerVisibilityState, PixelComparisonResult, VisualComparisonResult
from services.logging_manager import get_logger

logger = get_logger()


class ComparisonService:
    """Side-by-side and pixel-difference comparison for validation workspace."""

    def compare_images(
        self,
        before_path: str | Path,
        after_path: str | Path,
        *,
        diff_output_path: str | Path | None = None,
    ) -> PixelComparisonResult:
        before = Path(before_path)
        after = Path(after_path)
        if not before.is_file() or not after.is_file():
            return PixelComparisonResult()

        try:
            from PIL import Image, ImageChops
        except ImportError:
            logger.warning("Pillow not available for pixel comparison")
            return PixelComparisonResult()

        img_a = Image.open(before).convert("RGBA")
        img_b = Image.open(after).convert("RGBA")
        width = min(img_a.width, img_b.width)
        height = min(img_a.height, img_b.height)
        img_a = img_a.resize((width, height))
        img_b = img_b.resize((width, height))

        diff = ImageChops.difference(img_a, img_b)
        diff_pixels = list(diff.get_flattened_data())
        total = width * height
        matching = sum(1 for px in diff_pixels if px[:3] == (0, 0, 0) and px[3] == 0)
        diff_pct = round((total - matching) / total * 100.0, 2) if total else 0.0
        accuracy = round(100.0 - diff_pct, 2)

        overlay_path = ""
        if diff_output_path:
            out = Path(diff_output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            highlight = Image.new("RGBA", (width, height), (255, 0, 0, 0))
            highlight_data = []
            for px in diff_pixels:
                if px[:3] == (0, 0, 0) and px[3] == 0:
                    highlight_data.append((0, 0, 0, 0))
                else:
                    highlight_data.append((255, 0, 0, 128))
            highlight.putdata(highlight_data)
            composite = Image.alpha_composite(img_a, highlight)
            composite.save(out)
            overlay_path = str(out)

        return PixelComparisonResult(
            width=width,
            height=height,
            matching_pixels=matching,
            total_pixels=total,
            difference_percent=diff_pct,
            accuracy_percent=accuracy,
            diff_overlay_path=overlay_path,
        )

    def build_visual_comparison(
        self,
        before_path: str,
        after_path: str,
        *,
        diff_output_path: str | Path | None = None,
        layer_states: list[LayerVisibilityState] | None = None,
    ) -> VisualComparisonResult:
        pixel = self.compare_images(before_path, after_path, diff_output_path=diff_output_path)
        return VisualComparisonResult(
            before_path=before_path,
            after_path=after_path,
            pixel=pixel,
            layer_states=layer_states or [],
        )

    def compare_psd_layers(
        self,
        before_psd_path: str | Path,
        after_psd_path: str | Path,
    ) -> list[LayerVisibilityState]:
        """Compare layer visibility between two PSD files."""
        states: list[LayerVisibilityState] = []
        try:
            from psd_tools import PSDImage
        except ImportError:
            return states

        before = Path(before_psd_path)
        after = Path(after_psd_path)
        if not before.is_file() or not after.is_file():
            return states

        try:
            psd_a = PSDImage.open(before)
            psd_b = PSDImage.open(after)
            names_a = {layer.name: layer.visible for layer in psd_a}
            names_b = {layer.name: layer.visible for layer in psd_b}
            all_names = sorted(set(names_a) | set(names_b))
            for name in all_names:
                states.append(
                    LayerVisibilityState(
                        layer_name=name,
                        visible_before=names_a.get(name, False),
                        visible_after=names_b.get(name, False),
                    )
                )
        except Exception as exc:
            logger.warning("PSD layer comparison failed — {}", exc)
        return states
