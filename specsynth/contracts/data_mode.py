"""
specsynth.contracts.data_mode
=============================
Canonical DataMode Enumeration and Provenance Specifications (v1.0.0).

Defines canonical data provenance modes across Specsynth and PerandamΨ:
- simulation_derived: Genuine empirical simulation particles/properties (e.g. authentic TNG cutout).
- cached_reference: Calibrated reference tables, precomputed benchmark catalogs, and published empirical sets.
- live_computation: In-flight forward-modeled outputs synthesized in real time via live Python engine (:8000).
- analytical_mock: Procedural or analytical benchmark models (e.g. Hernquist/exponential disk mock specimen).
- illustrative_demo: Synthetic visual tracks, mockups, or demonstration fallbacks.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class DataMode(str, Enum):
    """Canonical data provenance modes."""
    SIMULATION_DERIVED = "simulation_derived"
    CACHED_REFERENCE = "cached_reference"
    LIVE_COMPUTATION = "live_computation"
    ANALYTICAL_MOCK = "analytical_mock"
    ILLUSTRATIVE_DEMO = "illustrative_demo"

    @classmethod
    def from_str(cls, val: str | DataMode) -> DataMode:
        """Parse string or return existing DataMode fail-closed."""
        if isinstance(val, cls):
            return val
        s = str(val).strip().lower()
        for member in cls:
            if member.value == s:
                return member
        # Fallback aliases
        if s in ("real", "simulation", "tng", "snapshot", "tng100"):
            return cls.SIMULATION_DERIVED
        if s in ("cached", "reference", "goods-s", "calibration", "goods_s_mock"):
            return cls.CACHED_REFERENCE
        if s in ("live", "computed", "gemm", "engine"):
            return cls.LIVE_COMPUTATION
        if s in ("mock", "procedural", "procedural_illustrative", "analytical"):
            return cls.ANALYTICAL_MOCK
        if s in ("demo", "illustrative", "fallback"):
            return cls.ILLUSTRATIVE_DEMO
        raise ValueError(
            f"Invalid data_mode '{val}'. Must be one of: {[m.value for m in cls]}"
        )

    def is_empirical_science(self) -> bool:
        """True if this mode represents genuine empirical simulation or live scientific synthesis."""
        return self in (DataMode.SIMULATION_DERIVED, DataMode.LIVE_COMPUTATION)

    def is_mock_or_demo(self) -> bool:
        """True if this data represents an analytical mock or illustrative demo."""
        return self in (DataMode.ANALYTICAL_MOCK, DataMode.ILLUSTRATIVE_DEMO)


def propagate_mode(source_mode: DataMode | str, requested_mode: Optional[DataMode | str] = None) -> DataMode:
    """
    Propagate data mode from source to derived product fail-closed.
    Non-promotion invariant: A derived product cannot have higher scientific authority
    than its source. Specifically:
    - If source is ANALYTICAL_MOCK or ILLUSTRATIVE_DEMO, the derived product CANNOT be promoted
      to SIMULATION_DERIVED or LIVE_COMPUTATION.
    """
    src = DataMode.from_str(source_mode)
    if requested_mode is None:
        return src
    req = DataMode.from_str(requested_mode)
    if src.is_mock_or_demo() and req.is_empirical_science():
        raise ValueError(
            f"Non-promotion invariant violation: Cannot promote mock/demo source ({src.value}) "
            f"to empirical scientific mode ({req.value})."
        )
    return req


def classify_source_data_mode(
    is_simulation: bool = False,
    is_live_backend: bool = False,
    is_cached_catalog: bool = False,
    is_procedural_mock: bool = False,
) -> DataMode:
    """Classify data mode based on provenance flags."""
    if is_simulation:
        return DataMode.SIMULATION_DERIVED
    if is_live_backend:
        return DataMode.LIVE_COMPUTATION
    if is_cached_catalog:
        return DataMode.CACHED_REFERENCE
    if is_procedural_mock:
        return DataMode.ANALYTICAL_MOCK
    return DataMode.ILLUSTRATIVE_DEMO
