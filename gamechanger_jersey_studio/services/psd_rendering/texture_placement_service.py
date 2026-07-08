"""Texture Placement Service — place material textures on mapped layers."""

from __future__ import annotations

from PIL import Image

from services.rendering.texture_mapper import TextureMapper


class TexturePlacementService:
    """Apply catalogue texture assets non-destructively."""

    def __init__(self) -> None:
        self._texture = TextureMapper()

    def apply_texture(self, base: Image.Image, texture_image: Image.Image, *, strength: float = 0.35) -> Image.Image:
        return self._texture.apply_texture(base, texture_image, strength=strength)
