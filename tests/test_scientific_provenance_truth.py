"""
tests.test_scientific_provenance_truth
======================================
Dedicated behavioral, adversarial, negative, and parity test suite for Issue #33.
Directly verifies:
1. Rejection of unmanifested, unverified, and fabricated simulation claims (fail-closed).
2. Detection and rejection of tampered cryptographic checksums.
3. Authentic verification of genuine IllustrisTNG-100 snapshot 99 cutout on disk.
4. Fail-closed non-promotion invariants across all transformation pipelines.
5. Typed SourceProvenance and ExecutionProvenance serialization roundtrips.
6. Photometry and 3D galaxy contracts enforce authoritative provenance without fabrication.
"""

from __future__ import annotations

import os
import pytest
import numpy as np

from specsynth.contracts.data_mode import (
    DataMode,
    ExecutionMode,
    ExecutionProvenance,
    SourceProvenance,
    VerificationStatus,
    compute_file_sha256,
    propagate_mode,
    validate_source_provenance_evidence,
    verify_simulation_asset,
    verify_simulation_cutout_manifest,
)
from specsynth.contracts.photometry import (
    PhotometryPointContract,
    SyntheticObservationContract,
)
from specsynth.contracts.galaxy3d import (
    CoordinateFrame,
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
)


# Path to authentic IllustrisTNG cutout and manifest in repo
TNG_REAL_CUTOUT = os.path.join(
    os.path.dirname(__file__), "..", "sample_models", "3d", "tng100_subhalo_real.hdf5"
)
TNG_REAL_MANIFEST = os.path.join(
    os.path.dirname(__file__), "..", "sample_models", "3d", "tng100_subhalo_real_manifest.json"
)
EXPECTED_TNG_SHA256 = "8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31"


# ==============================================================================
# Negative & Adversarial Tests: Source Provenance Rejection
# ==============================================================================

def test_unmanifested_galaxy_cannot_be_simulation_derived():
    """AC-1 Negative: A galaxy without source manifest must not be classified as simulation_derived."""
    # Empty provenance dict
    with pytest.raises(ValueError, match="requires an authentic simulation name"):
        validate_source_provenance_evidence(DataMode.SIMULATION_DERIVED, {})

    # Mock source name claiming simulation_derived
    with pytest.raises(ValueError, match="requires an authentic simulation name"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {"source_name": "Procedural Mock Bulge", "subhalo_id": 424601},
        )

    # Missing identifier
    with pytest.raises(ValueError, match="requires identifiable snapshot"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {
                "source_name": "IllustrisTNG-100-1",
                "verification_status": VerificationStatus.VERIFIED,
                "content_sha256": EXPECTED_TNG_SHA256,
            },
        )


def test_fabricated_tng_identity_rejected():
    """AC-2 Negative: A fabricated TNG identity without authentic backing must fail verification."""
    # Fabricated cutout path that does not exist
    status, msg = verify_simulation_cutout_manifest(
        file_path="nonexistent_tng_cutout.hdf5",
        expected_sha256=EXPECTED_TNG_SHA256,
        expected_snapshot=99,
        expected_subhalo_id=424601,
    )
    assert status == VerificationStatus.INVALID
    assert "not found" in msg

    # Provenance with unknown / unverified status claiming simulation_derived must fail
    with pytest.raises(ValueError, match="unverified provenance status"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {
                "source_name": "IllustrisTNG-100-1",
                "subhalo_id": 999999,
                "snapshot": 99,
                "verification_status": VerificationStatus.UNKNOWN,
            },
        )


def test_tampered_checksum_fails_verification():
    """AC-3 Negative: A tampered checksum must fail verification and be rejected."""
    # 1. verify_simulation_cutout_manifest with tampered expected digest
    if os.path.exists(TNG_REAL_CUTOUT):
        tampered_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        status, msg = verify_simulation_cutout_manifest(
            file_path=TNG_REAL_CUTOUT,
            expected_sha256=tampered_hash,
            expected_snapshot=99,
            expected_subhalo_id=424601,
        )
        assert status == VerificationStatus.INVALID
        assert "Checksum mismatch" in msg

    # 2. validate_source_provenance_evidence with mismatched content_sha256
    with pytest.raises(ValueError, match="Cryptographic checksum mismatch"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {
                "source_name": "IllustrisTNG-100-1",
                "subhalo_id": 424601,
                "snapshot": 99,
                "verification_status": VerificationStatus.VERIFIED,
                "content_sha256": "bad_digest_12345",
                "expected_sha256": EXPECTED_TNG_SHA256,
            },
        )

    # 3. Explicit INVALID status must be rejected fail-closed
    with pytest.raises(ValueError, match="failed verification"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {
                "source_name": "IllustrisTNG-100-1",
                "subhalo_id": 424601,
                "snapshot": 99,
                "verification_status": VerificationStatus.INVALID,
                "content_sha256": EXPECTED_TNG_SHA256,
            },
        )


def test_rule_1_source_provenance_cannot_be_self_certified():
    """Rule 1: SourceProvenance cannot be constructed with status=VERIFIED without on-disk manifest proof."""
    # Attempting to self-certify with verification_status='verified' without manifest_path
    with pytest.raises(ValueError, match="Rule 1 Violation.*manifest"):
        SourceProvenance(
            data_mode=DataMode.SIMULATION_DERIVED,
            source_name="IllustrisTNG-100-1",
            source_id=424601,
            verification_status=VerificationStatus.VERIFIED,
            content_sha256=EXPECTED_TNG_SHA256,
        )

    # Attempting to self-certify with a nonexistent manifest path
    with pytest.raises(ValueError, match="Rule 1 Violation.*manifest"):
        SourceProvenance(
            data_mode=DataMode.SIMULATION_DERIVED,
            source_name="IllustrisTNG-100-1",
            source_id=424601,
            verification_status=VerificationStatus.VERIFIED,
            content_sha256=EXPECTED_TNG_SHA256,
            manifest_path="nonexistent_manifest.json",
        )


def test_rule_1_operative_factory_verification():
    """Rule 1: Verified state emerges only from an active operation against the on-disk asset."""
    if not os.path.exists(TNG_REAL_CUTOUT):
        pytest.skip(f"TNG cutout asset not found at {TNG_REAL_CUTOUT}")

    # Operative verification produces verified SourceProvenance
    src = SourceProvenance.from_verified_asset(
        file_path=TNG_REAL_CUTOUT,
        manifest_path=TNG_REAL_MANIFEST,
    )
    assert src.is_verified is True
    assert src.verification_status == VerificationStatus.VERIFIED
    assert src.content_sha256 == EXPECTED_TNG_SHA256
    assert src.source_name == "IllustrisTNG-100-1"
    assert src.source_id == 424601


def test_rule_2_declared_status_rejected_for_simulation_derived():
    """Rule 2: Scientific claims must fail closed; simulation_derived rejects DECLARED status."""
    with pytest.raises(ValueError, match="Rule 2 Violation.*verification_status='verified'"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {
                "source_name": "IllustrisTNG-100-1",
                "subhalo_id": 424601,
                "snapshot": 99,
                "verification_status": VerificationStatus.DECLARED,
                "content_sha256": EXPECTED_TNG_SHA256,
            },
        )

    # Missing checksum is also strictly rejected for simulation_derived
    with pytest.raises(ValueError, match="Rule 2 Violation.*cryptographic checksum"):
        validate_source_provenance_evidence(
            DataMode.SIMULATION_DERIVED,
            {
                "source_name": "IllustrisTNG-100-1",
                "subhalo_id": 424601,
                "snapshot": 99,
                "verification_status": VerificationStatus.VERIFIED,
            },
        )


def test_authentic_tng100_cutout_verified():
    """Positive: The genuine IllustrisTNG-100 snapshot 99 cutout on disk passes cryptographic verification."""
    if not os.path.exists(TNG_REAL_CUTOUT):
        pytest.skip(f"TNG cutout asset not found at {TNG_REAL_CUTOUT}")

    # Compute actual digest from disk bytes
    computed_sha = compute_file_sha256(TNG_REAL_CUTOUT)
    assert computed_sha == EXPECTED_TNG_SHA256

    status, msg = verify_simulation_cutout_manifest(
        file_path=TNG_REAL_CUTOUT,
        expected_sha256=EXPECTED_TNG_SHA256,
        expected_snapshot=99,
        expected_subhalo_id=424601,
    )
    assert status == VerificationStatus.VERIFIED
    assert "Cryptographic SHA-256 verified" in msg


# ==============================================================================
# Non-Promotion Invariants
# ==============================================================================

def test_non_promotion_invariants_fail_closed():
    """Verify that lower-tier sources cannot be upgraded to empirical modes."""
    # analytical_mock cannot become simulation_derived
    with pytest.raises(ValueError, match="Non-promotion invariant violation"):
        propagate_mode(DataMode.ANALYTICAL_MOCK, DataMode.SIMULATION_DERIVED)

    # illustrative_demo cannot become live_computation
    with pytest.raises(ValueError, match="Non-promotion invariant violation"):
        propagate_mode(DataMode.ILLUSTRATIVE_DEMO, DataMode.LIVE_COMPUTATION)

    # unknown_unverified cannot become simulation_derived
    with pytest.raises(ValueError, match="Non-promotion invariant violation"):
        propagate_mode(DataMode.UNKNOWN_UNVERIFIED, DataMode.SIMULATION_DERIVED)

    # Legitimate non-upgrading propagation works
    assert propagate_mode(DataMode.SIMULATION_DERIVED, DataMode.CACHED_REFERENCE) == DataMode.CACHED_REFERENCE
    assert propagate_mode(DataMode.ANALYTICAL_MOCK, DataMode.ANALYTICAL_MOCK) == DataMode.ANALYTICAL_MOCK


# ==============================================================================
# Typed Contract Propagation & Serialization
# ==============================================================================

def test_typed_source_and_execution_provenance_roundtrip():
    """Verify typed dataclass serialization, property evaluation, and field fidelity."""
    src = SourceProvenance(
        data_mode=DataMode.SIMULATION_DERIVED,
        source_name="IllustrisTNG-100-1",
        source_id="424601",
        snapshot=99,
        redshift=0.0,
        cosmology={"h0": 67.74, "om0": 0.3089},
        verification_status=VerificationStatus.VERIFIED,
        content_sha256=EXPECTED_TNG_SHA256,
        expected_sha256=EXPECTED_TNG_SHA256,
        manifest_path=TNG_REAL_MANIFEST,
    )
    assert src.is_verified is True
    assert src.verification_state == "VERIFIED_AGAINST_MANIFEST"

    d = src.to_dict()
    assert d["data_mode"] == "simulation_derived"
    assert d["verification_status"] == "verified"
    assert d["is_verified"] is True
    assert d["content_sha256"] == EXPECTED_TNG_SHA256

    exec_prov = ExecutionProvenance(
        execution_mode=ExecutionMode.LIVE_BACKEND,
        engine="SpecSynth Python GEMM (:8000)",
        endpoint="http://127.0.0.1:8000/api/inspect",
        request_id="req_tng_424601_z2.0",
        input_fingerprint="tng_424601:z=2.0000:av=0.5000",
        parameters_applied={"redshift": 2.0, "dust_av": 0.5},
        latency_ms=14.2,
    )
    ed = exec_prov.to_dict()
    assert ed["execution_mode"] == "live_backend"
    assert ed["request_id"] == "req_tng_424601_z2.0"
    assert ed["input_fingerprint"] == "tng_424601:z=2.0000:av=0.5000"
    assert ed["latency_ms"] == 14.2


def test_synthetic_observation_contract_provenance_enforcement():
    """Verify SyntheticObservationContract enforces typed provenance and fail-closed validation."""
    phot = [
        PhotometryPointContract(
            filter_name="jwst_f200w",
            pivot_wavelength_angstrom=19890.0,
            flux_density_ujy=12.5,
            ab_magnitude=21.15,
        )
    ]

    src = SourceProvenance(
        data_mode=DataMode.CACHED_REFERENCE,
        source_name="GOODS-S Calibrated Reference Mock",
        verification_status=VerificationStatus.DECLARED,
    )
    exec_prov = ExecutionProvenance(
        execution_mode=ExecutionMode.PRECOMPUTED_CACHED,
        engine="SpecSynth Reference Cache",
    )

    obs = SyntheticObservationContract(
        galaxy_id="test_gal_01",
        redshift=1.5,
        cosmology={"h0": 67.74, "om0": 0.3089},
        dust_model="charlot_fall_2000",
        igm_model="madau_1995",
        ssp_model="fsps_v3.2",
        photometry=phot,
        sed_wave_angstrom=np.linspace(1000, 10000, 50),
        sed_flux_obs_cgs=np.ones(50, dtype=np.float32) * 1e-18,
        source_provenance=src,
        execution_provenance=exec_prov,
    )

    assert obs.data_mode == "cached_reference"
    assert obs.source_provenance.verification_status == VerificationStatus.DECLARED

    summary = obs.to_dict()
    assert summary["data_mode"] == "cached_reference"
    assert summary["source_provenance"]["source_name"] == "GOODS-S Calibrated Reference Mock"
    assert summary["execution_provenance"]["execution_mode"] == "precomputed_cached"
