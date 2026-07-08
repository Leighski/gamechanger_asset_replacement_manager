"""Independently testable recognition module protocol.

Architecture principles:
  1. Every recognition module populates ``GarmentRecognitionContract`` only.
  2. Modules never call the renderer or mutate Design Specification directly.
  3. Modules must be independently testable with fixture images / synthetic inputs.
  4. Detect and map are separate steps (see ``mapping.py``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from PIL import Image

from models.garment_recognition.contract import GarmentRecognitionContract
from models.garment_recognition.enums import RecognitionModuleId


@dataclass(frozen=True)
class RecognitionContext:
    """Inputs available to a recognition module.

    Modules receive the image and optional prior contract state. They must not
    receive renderer services, DesignSpecification writers, or UI handles.
    """

    image: Image.Image
    source_image_id: str = ""
    source_image_path: str = ""
    review_threshold: float = 85.0
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleResult:
    """Outcome of a single module run — always a contract delta or mutated contract."""

    module_id: RecognitionModuleId
    contract: GarmentRecognitionContract
    success: bool = True
    message: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class RecognitionModule(Protocol):
    """Protocol every recognition engine must implement.

    Implementations should be pure with respect to rendering: given a context
    and a contract, return an updated contract. No shared mutable renderer state.
    """

    @property
    def module_id(self) -> RecognitionModuleId: ...

    def analyze(
        self,
        context: RecognitionContext,
        contract: GarmentRecognitionContract,
    ) -> ModuleResult: ...


class RecognitionModuleBase(ABC):
    """Optional ABC helper for modules that prefer inheritance over duck typing."""

    @property
    @abstractmethod
    def module_id(self) -> RecognitionModuleId:
        raise NotImplementedError

    @abstractmethod
    def analyze(
        self,
        context: RecognitionContext,
        contract: GarmentRecognitionContract,
    ) -> ModuleResult:
        raise NotImplementedError

    def run(
        self,
        context: RecognitionContext,
        contract: GarmentRecognitionContract | None = None,
    ) -> ModuleResult:
        """Convenience entry point used by tests and future orchestration."""
        active = contract or GarmentRecognitionContract(
            source_image_id=context.source_image_id,
            source_image_path=context.source_image_path,
            review_threshold=context.review_threshold,
        )
        result = self.analyze(context, active)
        if result.success:
            result.contract.mark_module_complete(self.module_id)
            result.contract.refresh_review_flags(context.review_threshold)
        return result
