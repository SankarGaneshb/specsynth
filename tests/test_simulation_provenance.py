"""
tests.test_simulation_provenance
================================
Automated scientific test suite for traceable simulation snapshot and particle provenance.
Validates all requirements of Issue #26:
  - Genuine IllustrisTNG-100 cutout ingestion & metadata validation
  - ParticleIDs preservation across ParticleBatchContract & WebGL decimation
  - Scale factor a and Hubble parameter h physical unit conversions
  - Strict rejection of missing/ambiguous cosmological units
  - Truth in labeling segregation (simulation_derived vs procedural_illustrative)
  - Full SHA-256 provenance manifest verification
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
import numpy as np
import pytest

from specsynth.contracts.galaxy3d import (
    CoordinateFrame,
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
)
from specsynth.cosmology import TNG_COSMOLOGY, FlatLambdaCDM
from specsynth.simulation import (
    export_galaxy3d_hdf5,
    export_galaxy3d_web_json,
    generate_mock_simulation_snapshot,
    load_simulation_snapshot,
)
from specsynth.transforms import (
    comoving_to_physical_kpc,
    decimate_particles,
    physical_mass_msun,
    physical_velocity_km_s,
)
from scripts.fetch_tng_cutout import compute_sha256, verify_tng_provenance


def test_simulation_snapshot_real_ingestion() -> None:
    """Verify ingestion of genuine IllustrisTNG cutout fixture with ParticleIDs and units."""
    pytest.importorskip("h5py")
    sample_h5 = Path("sample_models/3d/tng100_subhalo_real.hdf5")
    assert sample_h5.exists(), f"Reference specimen missing: {sample_h5}"

    galaxy = load_simulation_snapshot(
        sample_h5,
        galaxy_id="tng100_subhalo_424601",
        sim_type="illustris_tng",
        subhalo_id=424601,
        align_angular_momentum=True,
    )

    # 1. Truth in labeling: MUST be simulation_derived
    assert galaxy.geometry_source == GeometrySource.SIMULATION_DERIVED
    assert galaxy.coordinate_frame == CoordinateFrame.PHYSICAL_REST
    assert np.isclose(galaxy.redshift, 0.0)
    assert galaxy.half_mass_radius_kpc > 0.0
    assert galaxy.total_stellar_mass_msun() > 1e8

    # 2. Check components
    for ptype in (ParticleType.STAR.value, ParticleType.GAS.value, ParticleType.DARK_MATTER.value):
        assert ptype in galaxy.components
        comp = galaxy.components[ptype]
        assert len(comp.coordinates_kpc) > 0
        assert len(comp.velocities_km_s) == len(comp.coordinates_kpc)
        assert len(comp.masses_msun) == len(comp.coordinates_kpc)
        # 3. ParticleIDs preservation
        assert comp.particle_ids is not None
        assert len(comp.particle_ids) == len(comp.coordinates_kpc)
        assert comp.particle_ids.dtype == np.uint64

    # 4. Provenance tracking
    assert galaxy.provenance.get("particle_ids_preserved") is True
    datasets_consumed = galaxy.provenance.get("datasets_consumed", [])
    assert "PartType4/Coordinates" in datasets_consumed
    assert "PartType4/ParticleIDs" in datasets_consumed
    assert "PartType0/Coordinates" in datasets_consumed
    assert "PartType1/ParticleIDs" in datasets_consumed


def test_comoving_physical_conversions_scale_factors() -> None:
    """
    Verify exact Gadget/Arepo physical unit conversions:
      r_phys = r_comov * a / h
      v_phys = v_code * sqrt(a)
      M_phys = M_code * 10^10 / h
    """
    z = 1.0
    h = 0.6774
    a = 1.0 / (1.0 + z)  # 0.5

    # 1. Coordinates
    r_comov = np.array([[100.0, -50.0, 25.0]], dtype=np.float32)
    r_phys = comoving_to_physical_kpc(r_comov, redshift=z, h=h)
    expected_r = r_comov * (a / h)
    assert np.allclose(r_phys, expected_r, rtol=1e-5)

    # 2. Velocities
    v_code = np.array([[200.0, 150.0, -50.0]], dtype=np.float32)
    v_phys = physical_velocity_km_s(v_code, redshift=z)
    expected_v = v_code * np.sqrt(a)
    assert np.allclose(v_phys, expected_v, rtol=1e-5)

    # 3. Masses
    m_code = np.array([1.5e-5, 2.0e-5], dtype=np.float32)
    m_phys = physical_mass_msun(m_code, h=h)
    expected_m = m_code * (1e10 / h)
    assert np.allclose(m_phys, expected_m, rtol=1e-5)

    # 4. Error rejection on invalid/missing parameters
    with pytest.raises(ValueError, match="redshift must be non-negative"):
        comoving_to_physical_kpc(r_comov, redshift=-0.1, h=h)
    with pytest.raises(ValueError, match="h must be positive"):
        comoving_to_physical_kpc(r_comov, redshift=0.0, h=0.0)
    with pytest.raises(ValueError, match="redshift must be non-negative"):
        physical_velocity_km_s(v_code, redshift=-0.5)
    with pytest.raises(ValueError, match="h must be positive"):
        physical_mass_msun(m_code, h=-0.1)


def test_missing_cosmological_units_in_hdf5_raises_value_error() -> None:
    """Verify that snapshot ingestion strictly raises ValueError if h or z is missing."""
    h5py = pytest.importorskip("h5py")

    with tempfile.TemporaryDirectory() as tmpdir:
        bad_h5 = Path(tmpdir) / "corrupt_units.hdf5"
        with h5py.File(bad_h5, "w") as f:
            # Header without HubbleParam or Redshift
            header = f.create_group("Header")
            header.attrs["BoxSize"] = 75000.0
            grp = f.create_group("PartType4")
            grp.create_dataset("Coordinates", data=np.zeros((10, 3), dtype=np.float32))
            grp.create_dataset("Masses", data=np.ones(10, dtype=np.float32))

        # Must raise ValueError for missing h
        with pytest.raises(ValueError, match="Missing cosmological parameter 'h'"):
            load_simulation_snapshot(bad_h5)

        # Must raise ValueError for missing redshift if h is provided
        with pytest.raises(ValueError, match="Missing cosmological parameter 'redshift'"):
            load_simulation_snapshot(bad_h5, h=0.6774)


def test_mock_fixture_is_clearly_labeled() -> None:
    """Verify that procedural mock models are strictly labeled PROCEDURAL_ILLUSTRATIVE."""
    # 1. Direct generator
    mock_galaxy = generate_mock_simulation_snapshot(
        galaxy_id="mock_specimen_test",
        redshift=0.1,
        n_stars=1000,
    )
    assert mock_galaxy.geometry_source == GeometrySource.PROCEDURAL_ILLUSTRATIVE
    assert mock_galaxy.geometry_source.value == "procedural_illustrative"
    assert "Procedural Mock" in mock_galaxy.provenance.get("simulation", "")

    # 2. Bundled mock specimen file
    mock_h5 = Path("sample_models/3d/mock_procedural_specimen.hdf5")
    if mock_h5.exists():
        loaded_mock = load_simulation_snapshot(
            mock_h5,
            galaxy_id="mock_procedural_specimen",
            redshift=0.0,
            h=0.6774,
        )
        # MUST strictly pass only as PROCEDURAL_ILLUSTRATIVE (no loophole)
        assert loaded_mock.geometry_source == GeometrySource.PROCEDURAL_ILLUSTRATIVE
        assert loaded_mock.geometry_source != GeometrySource.SIMULATION_DERIVED

    # 3. Bundled mock web JSON
    mock_web = Path("sample_models/3d/mock_procedural_specimen_web.json")
    if mock_web.exists():
        with open(mock_web, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("geometry_source") == "procedural_illustrative"

    # 4. Bundled mock manifest
    mock_manifest = Path("sample_models/3d/mock_procedural_specimen_manifest.json")
    if mock_manifest.exists():
        with open(mock_manifest, "r", encoding="utf-8") as f:
            mdata = json.load(f)
        assert mdata.get("geometry_source") == "procedural_illustrative"


def test_particle_decimation_preserves_ids() -> None:
    """Verify that WebGL decimation strictly preserves stable source ParticleIDs and records metadata."""
    rng = np.random.default_rng(999)
    n_particles = 10000
    coords = rng.normal(0, 3, size=(n_particles, 3)).astype(np.float32)
    vels = rng.normal(0, 50, size=(n_particles, 3)).astype(np.float32)
    masses = rng.uniform(1e5, 5e5, size=n_particles).astype(np.float32)
    pids = np.arange(5000000, 5000000 + n_particles, dtype=np.uint64)

    target_sample = 2500
    c_dec, v_dec, m_dec, idx = decimate_particles(coords, vels, masses, max_particles=target_sample, seed=42)

    # Subsampled particle IDs
    dec_pids = pids[idx]
    assert len(dec_pids) == target_sample
    assert len(c_dec) == target_sample
    assert len(m_dec) == target_sample
    # Subsampled IDs must be a strict subset of original IDs
    assert set(dec_pids).issubset(set(pids))

    # Test via ParticleBatchContract and to_web_json
    batch = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=coords,
        velocities_km_s=vels,
        masses_msun=masses,
        particle_ids=pids,
    )
    galaxy = Galaxy3DContract(
        galaxy_id="test_decimation_galaxy",
        geometry_source=GeometrySource.SIMULATION_DERIVED,
        coordinate_frame=CoordinateFrame.PHYSICAL_REST,
        redshift=0.0,
        center_of_mass_kpc=(0.0, 0.0, 0.0),
        half_mass_radius_kpc=2.0,
        components={"star": batch},
    )

    web_data = galaxy.to_web_json(max_particles_per_component=target_sample, seed=42)
    star_data = web_data["particles"]["star"]
    assert "particle_ids" in star_data
    assert len(star_data["particle_ids"]) == target_sample
    assert "downsampling" in star_data
    ds = star_data["downsampling"]
    assert ds["sampled_particles"] == target_sample
    assert ds["total_particles"] == n_particles
    assert np.isclose(ds["sampling_fraction"], 0.25, rtol=1e-3)
    assert ds["seed"] == 42


def test_tng_provenance_manifest_completeness() -> None:
    """Verify that tng100_subhalo_real_manifest.json provides complete, verifiable provenance."""
    manifest_path = Path("sample_models/3d/tng100_subhalo_real_manifest.json")
    h5_path = Path("sample_models/3d/tng100_subhalo_real.hdf5")
    web_path = Path("sample_models/3d/tng100_subhalo_real_web.json")

    assert manifest_path.exists()
    assert h5_path.exists()
    assert web_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Identification
    assert manifest["galaxy_id"] == "tng100_subhalo_424601"
    assert manifest["geometry_source"] == "simulation_derived"
    assert manifest["coordinate_frame"] == "physical_rest"

    # 2. Simulation provenance
    sim = manifest["simulation"]
    assert sim["name"] == "IllustrisTNG-100-1"
    assert sim["snapshot"] == 99
    assert sim["subhalo_id"] == 424601
    assert "tng-project.org" in sim["source_url"]

    # 3. Checksums verification
    actual_h5_sha = compute_sha256(h5_path)
    actual_web_sha = compute_sha256(web_path)
    assert manifest["checksums"]["hdf5_sha256"] == actual_h5_sha
    assert manifest["checksums"]["webgl_json_sha256"] == actual_web_sha

    # 4. Physical unit conversions documentation
    convs = manifest["unit_conversions"]
    assert "coordinates" in convs
    assert "velocities" in convs
    assert "masses" in convs
    assert "stellar_ages" in convs


def test_fetch_tng_cutout_script_verification() -> None:
    """Verify that scripts/fetch_tng_cutout.py verification succeeds cleanly."""
    ok = verify_tng_provenance(
        h5_path=Path("sample_models/3d/tng100_subhalo_real.hdf5"),
        manifest_path=Path("sample_models/3d/tng100_subhalo_real_manifest.json"),
    )
    assert ok is True


def test_tampered_hdf5_fails_checksum_verification() -> None:
    """Verify that any modification or tampering of the HDF5 file strictly fails verification."""
    pytest.importorskip("h5py")
    h5_orig = Path("sample_models/3d/tng100_subhalo_real.hdf5")
    manifest_path = Path("sample_models/3d/tng100_subhalo_real_manifest.json")

    with tempfile.TemporaryDirectory() as tmpdir:
        tampered_h5 = Path(tmpdir) / "tampered_cutout.hdf5"
        tampered_h5.write_bytes(h5_orig.read_bytes() + b"\x00\xff")

        # Must fail-closed due to SHA-256 mismatch
        ok = verify_tng_provenance(h5_path=tampered_h5, manifest_path=manifest_path)
        assert ok is False


def test_mismatched_metadata_fails_verification() -> None:
    """Verify that mismatched simulation, snapshot, or subhalo metadata fails verification."""
    pytest.importorskip("h5py")
    h5_path = Path("sample_models/3d/tng100_subhalo_real.hdf5")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create manifest expecting a different subhalo
        bad_manifest_path = Path(tmpdir) / "bad_manifest.json"
        with open("sample_models/3d/tng100_subhalo_real_manifest.json", "r", encoding="utf-8") as f:
            m = json.load(f)
        m["simulation"]["subhalo_id"] = 999999
        with open(bad_manifest_path, "w", encoding="utf-8") as f:
            json.dump(m, f)

        ok = verify_tng_provenance(h5_path=h5_path, manifest_path=bad_manifest_path)
        assert ok is False


def test_download_without_api_key_fails_closed() -> None:
    """Verify that attempting to download without a TNG API key fails closed rather than producing a mock."""
    from scripts.fetch_tng_cutout import download_tng_cutout
    import os

    old_key = os.environ.pop("TNG_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "cutout.hdf5"
            with pytest.raises(RuntimeError, match="TNG_API_KEY is not set"):
                download_tng_cutout(subhalo_id=424601, snapshot=99, api_key=None, output_path=out_file)
            # Must NOT produce a synthetic file
            assert not out_file.exists()
    finally:
        if old_key is not None:
            os.environ["TNG_API_KEY"] = old_key

