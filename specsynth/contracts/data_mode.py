"""
specsynth.contracts.data_mode
=============================
Canonical DataMode, ExecutionMode, and Structured Provenance Specifications (v1.1.0).

Strictly decouples two orthogonal dimensions:
1. Source / Data Provenance: Where input data originated and what it physically represents
   (simulation_derived, cached_reference, analytical_mock, illustrative_demo, unknown_unverified).
2. Execution Provenance: Where and how the active result was computed
   (live_backend, client_browser, precomputed_cached).

Enforces non-promotion and truth-in-labeling invariants fail-closed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Union


class DataMode(str, Enum):
    """Canonical data provenance modes."""
    SIMULATION_DERIVED = "simulation_derived"
    CACHED_REFERENCE = "cached_reference"
    LIVE_COMPUTATION = "live_computation"
    ANALYTICAL_MOCK = "analytical_mock"
    ILLUSTRATIVE_DEMO = "illustrative_demo"
    UNKNOWN_UNVERIFIED = "unknown_unverified"

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
        if s in ("real", "simulation", "tng", "snapshot", "tng100", "tng100-1"):
            return cls.SIMULATION_DERIVED
        if s in ("cached", "reference", "goods-s", "calibration", "goods_s_mock"):
            return cls.CACHED_REFERENCE
        if s in ("live", "computed", "gemm", "engine"):
            return cls.LIVE_COMPUTATION
        if s in ("mock", "procedural", "procedural_illustrative", "analytical"):
            return cls.ANALYTICAL_MOCK
        if s in ("demo", "illustrative", "fallback"):
            return cls.ILLUSTRATIVE_DEMO
        if s in ("unknown", "unverified", "none", ""):
            return cls.UNKNOWN_UNVERIFIED
        raise ValueError(
            f"Invalid data_mode '{val}'. Must be one of: {[m.value for m in cls]}"
        )

    def is_empirical_science(self) -> bool:
        """True if this mode represents genuine empirical simulation or live scientific synthesis."""
        return self in (DataMode.SIMULATION_DERIVED, DataMode.LIVE_COMPUTATION)

    def is_mock_or_demo(self) -> bool:
        """True if this data represents an analytical mock or illustrative demo."""
        return self in (DataMode.ANALYTICAL_MOCK, DataMode.ILLUSTRATIVE_DEMO, DataMode.UNKNOWN_UNVERIFIED)

    def is_verified_scientific(self) -> bool:
        """True if this data mode represents an authorized, verified scientific product."""
        return self in (DataMode.SIMULATION_DERIVED, DataMode.CACHED_REFERENCE, DataMode.LIVE_COMPUTATION)


class ExecutionMode(str, Enum):
    """Canonical computation execution modes."""
    LIVE_BACKEND = "live_backend"           # Live Python GEMM contraction (:8000)
    CLIENT_BROWSER = "client_browser"       # In-browser client JavaScript forward model
    PRECOMPUTED_CACHED = "precomputed_cached"  # Stored reference snapshot on disk or memory

    @classmethod
    def from_str(cls, val: str | ExecutionMode) -> ExecutionMode:
        if isinstance(val, cls):
            return val
        s = str(val).strip().lower()
        for member in cls:
            if member.value == s:
                return member
        if s in ("backend", "live", "gemm", "server"):
            return cls.LIVE_BACKEND
        if s in ("client", "browser", "js", "client_side", "frontend"):
            return cls.CLIENT_BROWSER
        if s in ("cache", "cached", "precomputed", "disk", "static"):
            return cls.PRECOMPUTED_CACHED
        raise ValueError(
            f"Invalid execution_mode '{val}'. Must be one of: {[m.value for m in cls]}"
        )


@dataclass
class SourceProvenance:
    """
    Structured, versioned specification of data origin and physical provenance.
    """
    data_mode: DataMode
    source_name: str
    source_id: Optional[Union[str, int]] = None
    snapshot: Optional[Union[str, int]] = None
    redshift: Optional[float] = None
    cosmology: Optional[dict[str, float]] = None
    checksums: dict[str, str] = field(default_factory=dict)
    verification_state: str = "DECLARED_UNVERIFIED"  # "VERIFIED_AGAINST_MANIFEST", "DECLARED_UNVERIFIED", "TAMPERED_INVALID", "UNAVAILABLE"
    parent_provenance: Optional[dict[str, Any]] = None
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if isinstance(self.data_mode, str):
            self.data_mode = DataMode.from_str(self.data_mode)
        if not self.source_name:
            raise ValueError("source_name must not be empty in SourceProvenance")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["data_mode"] = self.data_mode.value
        return d


@dataclass
class ExecutionProvenance:
    """
    Structured, versioned specification of compute environment, engine, and parameters.
    """
    execution_mode: ExecutionMode
    engine: str
    engine_version: str = "1.0.0"
    endpoint: Optional[str] = None
    parameters_applied: dict[str, Any] = field(default_factory=dict)
    latency_ms: Optional[float] = None
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if isinstance(self.execution_mode, str):
            self.execution_mode = ExecutionMode.from_str(self.execution_mode)
        if not self.engine:
            raise ValueError("engine must not be empty in ExecutionProvenance")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["execution_mode"] = self.execution_mode.value
        return d


def propagate_mode(source_mode: DataMode | str, requested_mode: Optional[DataMode | str] = None) -> DataMode:
    """
    Propagate data mode from source to derived product fail-closed.
    Non-promotion invariant: A derived product cannot have higher scientific authority
    than its source. Specifically:
    - If source is ANALYTICAL_MOCK, ILLUSTRATIVE_DEMO, or UNKNOWN_UNVERIFIED,
      the derived product CANNOT be promoted to SIMULATION_DERIVED or LIVE_COMPUTATION.
    """
    src = DataMode.from_str(source_mode)
    if requested_mode is None:
        return src
    req = DataMode.from_str(requested_mode)
    if src.is_mock_or_demo() and req.is_empirical_science():
        raise ValueError(
            f"Non-promotion invariant violation: Cannot promote mock/demo/unverified source ({src.value}) "
            f"to empirical scientific mode ({req.value})."
        )
    return req


def validate_source_provenance_evidence(data_mode: str | DataMode, provenance: Optional[dict[str, Any]]) -> None:
    """
    Enforce fail-closed truth-in-labeling evidence requirements:
    Claiming 'simulation_derived' requires auditable proof in provenance:
    - non-empty source/simulation name
    - and identifiable subhalo/snapshot or cryptographic checksum.
    """
    mode = DataMode.from_str(data_mode)
    if mode != DataMode.SIMULATION_DERIVED:
        return

    prov = provenance or {}
    source_name = (
        prov.get("source_name")
        or prov.get("simulation")
        or prov.get("simulation_name")
        or prov.get("source")
    )
    if not source_name or "mock" in str(source_name).lower():
        raise ValueError(
            f"Truth-in-labeling violation: Claimed data_mode 'simulation_derived' requires an authentic simulation name in provenance, got '{source_name}'"
        )

    has_identifier = (
        prov.get("source_id") is not None
        or prov.get("subhalo_id") is not None
        or prov.get("snapshot") is not None
        or prov.get("snapshot_id") is not None
        or bool(prov.get("checksums"))
        or bool(prov.get("hdf5_sha256"))
        or bool(prov.get("manifest_hash"))
    )
    if not has_identifier:
        raise ValueError(
            "Truth-in-labeling violation: Claimed data_mode 'simulation_derived' requires identifiable snapshot, subhalo_id, or cryptographic checksum evidence in provenance."
        )


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
