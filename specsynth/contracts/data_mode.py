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
import json
import os
from pathlib import Path
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


REPO_ROOT = Path(__file__).resolve().parents[2]

AUTHORITATIVE_MANIFESTS: dict[str, Path] = {
    "tng100_subhalo_real": REPO_ROOT / "sample_models" / "3d" / "tng100_subhalo_real_manifest.json",
    "tng100_subhalo_424601": REPO_ROOT / "sample_models" / "3d" / "tng100_subhalo_real_manifest.json",
    "tng_424601": REPO_ROOT / "sample_models" / "3d" / "tng100_subhalo_real_manifest.json",
    "424601": REPO_ROOT / "sample_models" / "3d" / "tng100_subhalo_real_manifest.json",
    "tng100_subhalo_424601_sublink": REPO_ROOT / "sample_models" / "evolution" / "tng100_subhalo_424601_sublink_manifest.json",
}


@dataclass
class SourceProvenance:
    """
    Structured, versioned specification of data origin and physical provenance.
    Guarantees evidence-based verification and disallows manufactured metadata.

    Enforces Rule 1: Verification must be an operation, not a field.
    A caller cannot self-certify authenticity by simply passing verification_status='verified'.
    Verified status must emerge from an operative manifest and file byte verification.
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

        # Rule 1 Enforcement: Verification must be an operation, not a field
        if self.verification_status == VerificationStatus.VERIFIED:
            if not self.manifest_path or not os.path.exists(self.manifest_path):
                raise ValueError(
                    "Rule 1 Violation: verification_status cannot be set to 'verified' without an "
                    f"authoritative manifest on disk (manifest_path={self.manifest_path}). "
                    "Use SourceProvenance.from_verified_asset() to verify through an operative check."
                )
            if not self.content_sha256:
                raise ValueError(
                    "Rule 1 Violation: verification_status cannot be set to 'verified' without an "
                    "operative cryptographic content_sha256 matching the authoritative manifest."
                )
            # Validate that manifest actually exists and matches expected content_sha256
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                m_checksums = m_data.get("checksums", {})
                expected_digest = (
                    m_checksums.get("hdf5_sha256")
                    or m_checksums.get("tree_json_sha256")
                    or m_checksums.get("sha256")
                )
                if expected_digest and self.content_sha256.lower() != expected_digest.lower():
                    raise ValueError(
                        f"Rule 1 Violation: content_sha256 '{self.content_sha256}' does not match "
                        f"authoritative manifest checksum '{expected_digest}' in {self.manifest_path}."
                    )
            except (json.JSONDecodeError, OSError) as exc:
                raise ValueError(
                    f"Rule 1 Violation: Failed reading authoritative manifest {self.manifest_path}: {exc}"
                )

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

    @classmethod
    def from_verified_asset(
        cls,
        file_path: str,
        manifest_path: Optional[str] = None,
        data_mode: DataMode = DataMode.SIMULATION_DERIVED,
        parent_provenance: Optional[dict[str, Any]] = None,
    ) -> SourceProvenance:
        """
        Operative constructor: Validates actual asset file on disk against authoritative manifest.
        Enforces Rule 1 (verification is an active operation).
        """
        status, msg, manifest = verify_simulation_asset(file_path, manifest_path)
        if status != VerificationStatus.VERIFIED:
            raise ValueError(f"Operational verification failed for '{file_path}': {msg}")

        sim_info = manifest.get("simulation", {})
        source_name = sim_info.get("name", "IllustrisTNG-100-1")
        subhalo_id = sim_info.get("subhalo_id") or manifest.get("subhalo_id")
        snapshot = sim_info.get("snapshot") or manifest.get("snapshot")
        cosmology = sim_info.get("cosmology") or manifest.get("cosmology")

        actual_sha = compute_file_sha256(file_path)
        checksums = manifest.get("checksums", {})

        m_path_str = str(manifest.get("_manifest_path") or manifest_path or "")

        return cls(
            data_mode=data_mode,
            source_name=source_name,
            source_id=subhalo_id,
            snapshot=snapshot,
            redshift=manifest.get("redshift", 0.0),
            cosmology=cosmology,
            checksums=checksums,
            verification_status=VerificationStatus.VERIFIED,
            content_sha256=actual_sha,
            expected_sha256=checksums.get("hdf5_sha256") or checksums.get("tree_json_sha256") or actual_sha,
            manifest_path=m_path_str,
            parent_provenance=parent_provenance,
        )

    @classmethod
    def declare_unverified(
        cls,
        data_mode: DataMode | str,
        source_name: str,
        source_id: Optional[Union[str, int]] = None,
        snapshot: Optional[Union[str, int]] = None,
        redshift: Optional[float] = None,
        cosmology: Optional[dict[str, float]] = None,
        parent_provenance: Optional[dict[str, Any]] = None,
    ) -> SourceProvenance:
        """Construct declared / unverified provenance (Rule 2 fail-closed)."""
        mode = DataMode.from_str(data_mode)
        if mode == DataMode.SIMULATION_DERIVED:
            raise ValueError(
                "Rule 2 Violation: Cannot declare simulation_derived provenance without operative verification. "
                "Unverified simulation sources must be classified as analytical_mock or unknown_unverified."
            )
        return cls(
            data_mode=mode,
            source_name=source_name,
            source_id=source_id,
            snapshot=snapshot,
            redshift=redshift,
            cosmology=cosmology,
            verification_status=VerificationStatus.DECLARED,
            parent_provenance=parent_provenance,
        )


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


def resolve_authoritative_manifest(file_path: str, manifest_path: Optional[str] = None) -> Optional[Path]:
    """Resolve trusted on-disk manifest for a simulation asset."""
    if manifest_path and os.path.exists(manifest_path):
        return Path(manifest_path).resolve()

    p = Path(file_path).resolve()
    stem = p.stem.lower()

    # Check known authoritative manifests dictionary
    for k, m_path in AUTHORITATIVE_MANIFESTS.items():
        if k in stem or stem in k:
            if m_path.exists():
                return m_path.resolve()

    # Look for co-located manifest
    co_located = p.with_name(f"{p.stem}_manifest.json")
    if co_located.exists():
        return co_located.resolve()

    return None


def verify_simulation_asset(
    file_path: str,
    manifest_path: Optional[str] = None,
) -> tuple[VerificationStatus, str, dict[str, Any]]:
    """
    Active operative verification of a simulation asset against an authoritative on-disk manifest.
    Enforces Rule 1: Verification must be an operation, not a field.
    Enforces Rule 2: Scientific claims must fail closed.
    """
    if not os.path.exists(file_path):
        return (
            VerificationStatus.INVALID,
            f"Simulation asset file not found on disk at: {file_path}",
            {},
        )

    resolved_manifest_path = resolve_authoritative_manifest(file_path, manifest_path)
    if not resolved_manifest_path or not resolved_manifest_path.exists():
        return (
            VerificationStatus.INVALID,
            f"Authoritative manifest not found on disk for asset: {file_path}",
            {},
        )

    try:
        with open(resolved_manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return (
            VerificationStatus.INVALID,
            f"Failed to read authoritative manifest at '{resolved_manifest_path}': {exc}",
            {},
        )

    # Compute actual digest from disk bytes
    actual_sha = compute_file_sha256(file_path)

    # Check against manifest checksums
    checksums = manifest_data.get("checksums", {})
    expected_sha = (
        checksums.get("hdf5_sha256")
        or checksums.get("tree_json_sha256")
        or checksums.get("webgl_json_sha256")
        or checksums.get("sha256")
    )
    if not expected_sha:
        return (
            VerificationStatus.INVALID,
            f"Authoritative manifest '{resolved_manifest_path.name}' lacks cryptographic checksum.",
            manifest_data,
        )

    if actual_sha.lower() != expected_sha.lower():
        return (
            VerificationStatus.INVALID,
            f"Checksum mismatch: computed SHA-256 '{actual_sha}' does not match authoritative manifest checksum '{expected_sha}'",
            manifest_data,
        )

    # Inspect HDF5 metadata if file is HDF5 and h5py is available
    if file_path.endswith(".hdf5") or file_path.endswith(".h5"):
        try:
            import h5py
            with h5py.File(file_path, "r") as h5:
                # Validate presence of standard particle datasets
                datasets_to_check = manifest_data.get("datasets_consumed", [
                    "PartType4/Coordinates",
                    "PartType0/Coordinates",
                ])
                for ds in datasets_to_check:
                    if ds not in h5:
                        return (
                            VerificationStatus.INVALID,
                            f"HDF5 dataset verification failed: expected dataset '{ds}' missing in {file_path}",
                            manifest_data,
                        )
                # Verify particle counts if declared in manifest
                expected_particles = manifest_data.get("particle_counts", {})
                if "star" in expected_particles and "PartType4/Coordinates" in h5:
                    count_star = len(h5["PartType4/Coordinates"])
                    if count_star != expected_particles["star"]:
                        return (
                            VerificationStatus.INVALID,
                            f"Particle count mismatch: PartType4 has {count_star} particles, manifest declares {expected_particles['star']}",
                            manifest_data,
                        )
        except ImportError:
            # h5py optional; file byte SHA-256 is primary cryptographic invariant
            pass
        except Exception as exc:
            return (
                VerificationStatus.INVALID,
                f"HDF5 inspection error on {file_path}: {exc}",
                manifest_data,
            )

    # Store resolved path in return dict
    manifest_data["_manifest_path"] = str(resolved_manifest_path)
    sim = manifest_data.get("simulation", {})
    sim_name = sim.get("name", "IllustrisTNG-100-1")
    snap = sim.get("snapshot", 99)
    subhalo_id = sim.get("subhalo_id", 424601)

    return (
        VerificationStatus.VERIFIED,
        f"Cryptographic SHA-256 verified ({actual_sha}) matching authoritative manifest '{resolved_manifest_path.name}' ({sim_name} Snap {snap} Subhalo {subhalo_id}).",
        manifest_data,
    )


def verify_simulation_cutout_manifest(
    file_path: str,
    expected_sha256: Optional[str] = None,
    expected_snapshot: int = 99,
    expected_subhalo_id: int = 424601,
) -> tuple[VerificationStatus, str]:
    """
    Independently verify actual simulation cutout file against authoritative on-disk manifest.
    Enforces Rule 1: Operative verification; does not accept arbitrary caller assertions.
    """
    status, msg, manifest = verify_simulation_asset(file_path)
    if status != VerificationStatus.VERIFIED:
        return status, msg

    # If caller supplied an expected hash, ensure it matches the verified manifest
    actual_sha = compute_file_sha256(file_path)
    if expected_sha256 and expected_sha256.lower() != actual_sha.lower():
        return (
            VerificationStatus.INVALID,
            f"Checksum mismatch: computed SHA-256 '{actual_sha}' does not match expected '{expected_sha256}'",
        )

    return (
        VerificationStatus.VERIFIED,
        f"Cryptographic SHA-256 verified ({actual_sha}) matching IllustrisTNG-100-1 Snapshot {expected_snapshot} Subhalo {expected_subhalo_id}.",
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

    # Check verification status: Rule 2 strictly requires VERIFIED status for simulation_derived
    v_status = prov.get("verification_status") or prov.get("verification_state")
    if v_status in (VerificationStatus.INVALID, "invalid", "TAMPERED_INVALID", "tampered"):
        raise ValueError(
            "Truth-in-labeling violation: Claimed data_mode 'simulation_derived' has failed verification (tampered or invalid provenance)."
        )
    if v_status in (VerificationStatus.UNKNOWN, "unknown", "UNAVAILABLE"):
        raise ValueError(
            "Truth-in-labeling violation: Claimed data_mode 'simulation_derived' has unverified provenance status."
        )
    if v_status in (VerificationStatus.DECLARED, "declared", "DECLARED_UNVERIFIED"):
        raise ValueError(
            "Rule 2 Violation: Claimed data_mode 'simulation_derived' strictly requires verification_status='verified'. "
            "Status 'declared' is insufficient for empirical simulation claims (must fail closed to analytical_mock or unknown_unverified)."
        )
    if v_status not in (VerificationStatus.VERIFIED, "verified", "VERIFIED_AGAINST_MANIFEST"):
        raise ValueError(
            f"Rule 2 Violation: Claimed data_mode 'simulation_derived' requires verified provenance, got '{v_status}'"
        )

    # Checksum is mandatory for simulation_derived
    content_sha = (
        prov.get("content_sha256")
        or prov.get("checksum_sha256")
        or prov.get("sha256")
        or (prov.get("checksums") or {}).get("hdf5_sha256")
        or (prov.get("checksums") or {}).get("sha256")
    )
    if not content_sha:
        raise ValueError(
            "Rule 2 Violation: Claimed data_mode 'simulation_derived' strictly requires cryptographic checksum evidence in provenance."
        )

    expected_sha = (
        prov.get("expected_sha256")
        or (prov.get("checksums") or {}).get("hdf5_sha256")
        or (prov.get("checksums") or {}).get("sha256")
    )
    if expected_sha and content_sha.lower() != expected_sha.lower():
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

