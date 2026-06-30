"""Pattern Mapper — apply catalogue pattern assets with spec scale, rotation, opacity."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image


class PatternMapper:
    """Apply pattern component to body region non-destructively."""

    def apply_pattern(
        self,
        base: Image.Image,
        pattern_image: Image.Image,
        *,
        scale: float,
        rotation_degrees: float,
        opacity: float,
    ) -> Image.Image:
        if opacity <= 0.01:
            return base
        width, height = base.size
        pattern = pattern_image.convert("RGBA")
        target_w = max(8, int(width * min(2.0, max(0.2, scale))))
        target_h = max(8, int(height * min(2.0, max(0.2, scale))))
        pattern = pattern.resize((target_w, target_h), Image.Resampling.BILINEAR)
        if rotation_degrees:
            pattern = pattern.rotate(-rotation_degrees, expand=True, resample=Image.Resampling.BILINEAR)
        tile = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for y in range(0, height, pattern.height):
            for x in range(0, width, pattern.width):
                tile.paste(pattern, (x, y), pattern)
        data = np.array(tile, dtype=np.float32)
        data[..., 3] *= opacity
        tile = Image.fromarray(data.astype(np.uint8), mode="RGBA")
        return Image.alpha_composite(base.convert("RGBA"), tile)
