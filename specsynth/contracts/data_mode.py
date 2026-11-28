"""
specsynth.contracts.data_mode
=============================
Canonical DataMode, ExecutionMode, and Structured Provenance Specifications (v1.2.0).

Strictly decouples two orthogonal dimensions:
1. Source / Data Provenance: Where input data originated and what it physically represents
   (simulation_derived, cached_reference, analytical_mock, illustrative_demo, unknown_unverified).
2. Execution Provenance: Where and how the active result was computed
   (live_backend, client_browser, precomputed_cached).

Enforces non-promotion, authentic manifest checking, and truth-in-labeling invariants fail-closed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import os
from typing import Any, Dict, Optional, Union


class VerificationStatus(str, Enum):
    """
    Authoritative verification status of data provenance.
    Requires auditable proof against trusted manifests or cryptographic checksums.
    """
    UNKNOWN = "unknown"        # Unverified / no manifest available
    DECLARED = "declared"      # Caller asserted metadata without independent validation
    VERIFIED = "verified"      # Independently verified against authentic on-disk manifest and checksum
    INVALID = "invalid"        # Failed validation, tampered checksum, or fabricated identity

    @classmethod
    def from_str(cls, val: str | VerificationStatus) -> VerificationStatus:
        if isinstance(val, cls):
            return val
        s = str(val).strip().lower()
        for member in cls:
            if member.value == s:
                return member
        if s in ("verified_against_manifest", "verified_authentic", "authentic", "pass"):
            return cls.VERIFIED
        if s in ("declared_unverified", "asserted", "unverified"):
            return cls.DECLARED
        if s in ("tampered_invalid", "tampered", "corrupted", "failed", "fail"):
            return cls.INVALID
        if s in ("unknown_unverified", "none", "", "unavailable"):
            return cls.UNKNOWN
        raise ValueError(
            f"Invalid verification_status '{val}'. Must be one of: {[m.value for m in cls]}"
        )


class DataMode(str, Enum):
    """Canonical data provenance modes."""
    SIMULATION_DERIVED = "simulation_derived"
    CACHED_REFERENCE = "cached_reference"
    LIVE_COMPUTATION = "live_computation"  # DEPRECATED: Legacy alias; use ExecutionMode.LIVE_BACKEND.
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
    Guarantees evidence-based verification and disallows manufactured metadata.
    """
    data_mode: DataMode
    source_name: str
    source_id: Optional[Union[str, int]] = None
    snapshot: Optional[Union[str, int]] = None
    redshift: Optional[float] = None
    cosmology: Optional[dict[str, float]] = None
    checksums: dict[str, str] = field(default_factory=dict)
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    verification_state: str = "DECLARED_UNVERIFIED"
    content_sha256: Optional[str] = None
    expected_sha256: Optional[str] = None
    manifest_path: Optional[str] = None
    parent_provenance: Optional[dict[str, Any]] = None
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if isinstance(self.data_mode, str):
            self.data_mode = DataMode.from_str(self.data_mode)
        if isinstance(self.verification_status, str):
            self.verification_status = VerificationStatus.from_str(self.verification_status)
        if not self.source_name:
            raise ValueError("source_name must not be empty in SourceProvenance")
        # Keep verification_state in sync for backward compatibility
        if self.verification_status == VerificationStatus.VERIFIED:
            self.verification_state = "VERIFIED_AGAINST_MANIFEST"
        elif self.verification_status == VerificationStatus.INVALID:
            self.verification_state = "TAMPERED_INVALID"
        elif self.verification_status == VerificationStatus.DECLARED:
            self.verification_state = "DECLARED_UNVERIFIED"
        else:
            self.verification_state = "UNAVAILABLE"

    @property
    def is_verified(self) -> bool:
        return self.verification_status == VerificationStatus.VERIFIED

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["data_mode"] = self.data_mode.value
        d["verification_status"] = self.verification_status.value
        d["is_verified"] = self.is_verified
        return d


@dataclass
class ExecutionProvenance:
    """
    Structured, versioned specification of compute environment, engine, and parameters.
    Binds results atomically to their computation environment.
    """
    execution_mode: ExecutionMode
    engine: str
    engine_version: str = "1.0.0"
    endpoint: Optional[str] = None
    request_id: Optional[str] = None
    input_fingerprint: Optional[str] = None
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


def compute_file_sha256(file_path: str) -> str:
    """Compute cryptographic SHA-256 from actual file bytes on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_simulation_cutout_manifest(
    file_path: str,
    expected_sha256: str = "8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31",
    expected_snapshot: int = 99,
    expected_subhalo_id: int = 424601,
) -> tuple[VerificationStatus, str]:
    """
    Independently verify actual simulation cutout file against expected checksum and snapshot metadata.
    Does not accept caller assertions or inferred simulation identity.
    """
    if not os.path.exists(file_path):
        return VerificationStatus.INVALID, f"Simulation cutout file not found at: {file_path}"

    actual_hash = compute_file_sha256(file_path)
    if actual_hash != expected_sha256:
        return (
            VerificationStatus.INVALID,
            f"Checksum mismatch: computed SHA-256 '{actual_hash}' does not match expected '{expected_sha256}'",
        )

    return (
        VerificationStatus.VERIFIED,
        f"Cryptographic SHA-256 verified ({actual_hash}) matching IllustrisTNG-100-1 Snapshot {expected_snapshot} Subhalo {expected_subhalo_id}.",
    )


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
    - non-empty authentic simulation name (not mock or demo)
    - identifiable subhalo and snapshot
    - valid verification status (not INVALID or UNKNOWN)
    - matching cryptographic checksum where checksums are declared.
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

    # Check verification status
    v_status = prov.get("verification_status") or prov.get("verification_state")
    if v_status in (VerificationStatus.INVALID, "invalid", "TAMPERED_INVALID", "tampered"):
        raise ValueError(
            "Truth-in-labeling violation: Claimed data_mode 'simulation_derived' has failed verification (tampered or invalid provenance)."
        )
    if v_status in (VerificationStatus.UNKNOWN, "unknown", "UNAVAILABLE"):
        raise ValueError(
            "Truth-in-labeling violation: Claimed data_mode 'simulation_derived' has unverified provenance status."
        )

    # Check checksum consistency if provided
    content_sha = prov.get("content_sha256") or prov.get("checksum_sha256") or prov.get("sha256")
    expected_sha = prov.get("expected_sha256") or (prov.get("checksums") or {}).get("sha256")
    if content_sha and expected_sha and content_sha != expected_sha:
        raise ValueError(
            f"Truth-in-labeling violation: Cryptographic checksum mismatch: content '{content_sha}' != expected '{expected_sha}'"
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

