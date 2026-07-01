"""Pattern Placement Service — place catalogue patterns into mapped Smart Objects."""

from __future__ import annotations

from PIL import Image

from services.rendering.colour_mapper import ColourMapper
from services.rendering.pattern_mapper import PatternMapper


class PatternPlacementService:
    """Insert pattern catalogue assets with spec scale, rotation, opacity."""

    def __init__(self) -> None:
        self._colour = ColourMapper()
        self._pattern = PatternMapper()

    def build_pattern_image(
        self,
        pattern_image: Image.Image,
        *,
        hex_colour: str,
        scale: float,
        rotation_degrees: float,
        opacity: float,
        canvas_size: tuple[int, int],
    ) -> Image.Image:
        base = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        tinted = self._colour.tint_rgba(pattern_image, hex_colour or "#FFFFFF")
        return self._pattern.apply_pattern(
            base,
            tinted,
            scale=scale,
            rotation_degrees=rotation_degrees,
            opacity=opacity,
        )
