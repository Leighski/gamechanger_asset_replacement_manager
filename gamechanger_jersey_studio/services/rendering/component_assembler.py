"""Component Assembler — resolve and load certified catalogue components."""

from __future__ import annotations

from PIL import Image

from models.component_catalogue import CatalogueComponent, DESIGN_SPEC_CATALOGUE_FIELDS
from models.design_specification import DesignSpecification
from services.catalogue_manager_service import CatalogueManagerService
from services.rendering.errors import RenderingError


class ComponentAssembler:
    """Load catalogue component previews for live rendering."""

    def __init__(self, catalogue: CatalogueManagerService) -> None:
        self._catalogue = catalogue

    def resolve_field(self, field_name: str, reference: str) -> CatalogueComponent | None:
        if not reference or not reference.strip():
            return None
        return self._catalogue.resolver.resolve_spec_field(
            self._catalogue.library,
            field_name,
            reference.strip(),
        )

    def canonical_id(self, field_name: str, reference: str) -> str:
        category = DESIGN_SPEC_CATALOGUE_FIELDS.get(field_name)
        if category is None or not reference:
            return reference
        return self._catalogue.canonical_id(category, reference)

    def load_component_image(
        self,
        component: CatalogueComponent,
        size: tuple[int, int],
        *,
        resampling: int = Image.Resampling.BILINEAR,
    ) -> Image.Image:
        path = self._catalogue.preview_path(component)
        if path is None or not path.is_file():
            raise RenderingError(f"Missing preview asset for {component.id}")
        image = Image.open(path).convert("RGBA")
        if image.size != size:
            image = image.resize(size, resampling)
        return image

    def load_field_image(
        self,
        field_name: str,
        reference: str,
        size: tuple[int, int],
        *,
        resampling: int = Image.Resampling.BILINEAR,
    ) -> tuple[Image.Image, CatalogueComponent]:
        if not reference or not reference.strip():
            label = field_name.replace("_", " ").title()
            raise RenderingError(
                f"Missing {label} ({field_name}) — assign a certified catalogue component "
                "in Design Specification"
            )
        component = self.resolve_field(field_name, reference)
        if component is None:
            raise RenderingError(
                f"No certified component for {field_name}={reference!r} — verify the catalogue "
                "entry exists or update Design Specification"
            )
        return self.load_component_image(component, size, resampling=resampling), component

    def spec_references(self, spec: DesignSpecification) -> dict[str, str]:
        refs: dict[str, str] = {}
        for field_name in DESIGN_SPEC_CATALOGUE_FIELDS:
            value = str(spec.get_field(field_name) or "")
            if value:
                refs[field_name] = self.canonical_id(field_name, value)
        return refs
