"""Layer Manager — ordering, visibility, and compositing."""

from __future__ import annotations

import io

from PIL import Image

from models.renderer import DEFAULT_LAYER_ORDER, RenderLayerId, RendererSettings


class LayerManager:
    """Manage render layer order, visibility, and final composite."""

    def ordered_layers(self, settings: RendererSettings) -> list[RenderLayerId]:
        return [layer for layer in DEFAULT_LAYER_ORDER if settings.is_layer_visible(layer)]

    def composite(self, layers: dict[RenderLayerId, Image.Image], settings: RendererSettings) -> Image.Image:
        visible = self.ordered_layers(settings)
        if not visible:
            return Image.new("RGBA", (400, 500), (26, 31, 46, 255))
        canvas: Image.Image | None = None
        for layer_id in visible:
            image = layers.get(layer_id)
            if image is None:
                continue
            if canvas is None:
                canvas = image.convert("RGBA")
            else:
                canvas = Image.alpha_composite(canvas, image.convert("RGBA"))
        return canvas or Image.new("RGBA", (400, 500), (26, 31, 46, 255))

    def to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
        return buffer.getvalue()
