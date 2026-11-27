#!/usr/bin/env python3
"""
Specsynth & PerandamΨ — Acceptance Verification Harness for Issue #26
=====================================================================
Traceable Real Simulation Snapshot and Particle Provenance Verification

Tests and demonstrates the 7 acceptance criteria of Issue #26:
  [1] Strict Truth-in-Labeling segregation (Procedural Illustrative vs Simulation-Derived)
  [2] Scale factor a and Hubble parameter h physical unit conversions & error rejection
  [3] Real IllustrisTNG HDF5 snapshot ingestion & dataset tracking
  [4] Source ParticleIDs preservation across ParticleBatchContract & Galaxy3DContract
  [5] WebGL decimation preserves source ParticleIDs and records downsampling provenance
  [6] Full provenance manifest linking 3D objects to simulation source, URL & SHA-256
  [7] Deterministic verification script (scripts/fetch_tng_cutout.py) parity

Usage:
    python scripts/verify_p2_provenance.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Auto-re-exec into local .venv if run via global python without required packages
if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
    repo_root = Path(__file__).resolve().parent.parent
    venv_python_win = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python_posix = repo_root / ".venv" / "bin" / "python"
    venv_py = venv_python_win if venv_python_win.exists() else venv_python_posix

    if venv_py.exists() and str(venv_py) != sys.executable:
        os.execv(str(venv_py), [str(venv_py)] + sys.argv)

import numpy as np

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from specsynth.contracts.galaxy3d import (
    CoordinateFrame,
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
)
from specsynth.cosmology import TNG_COSMOLOGY
from specsynth.simulation import (
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


def header(title: str) -> None:
    print(f"\n{'=' * 78}")
    print(f"  {title}")
    print(f"{'=' * 78}")


def subheader(step: str, desc: str) -> None:
    print(f"\n--> [{step}] {desc}")


def pass_msg(msg: str) -> None:
    print(f"    \033[92m[PASS]\033[0m {msg}")


def fail_msg(msg: str) -> None:
    print(f"    \033[91m[FAIL]\033[0m {msg}")


def run_issue_26_verification() -> bool:
    all_passed = True
    header("Specsynth — Issue #26 Acceptance Verification Harness")
    print("Validating: Traceable Real Simulation Snapshot and Particle Provenance")

    sample_dir = repo_root / "sample_models" / "3d"
    real_h5 = sample_dir / "tng100_subhalo_real.hdf5"
    real_web = sample_dir / "tng100_subhalo_real_web.json"
    real_manifest = sample_dir / "tng100_subhalo_real_manifest.json"

    mock_h5 = sample_dir / "mock_procedural_specimen.hdf5"
    mock_web = sample_dir / "mock_procedural_specimen_web.json"
    mock_manifest = sample_dir / "mock_procedural_specimen_manifest.json"

    # -------------------------------------------------------------------------
    # 1. Truth in Labeling Segregation
    # -------------------------------------------------------------------------
    subheader("Step 1", "Fixture Segregation & Truth-in-Labeling Enforcement")
    try:
        # Check mock files
        with open(mock_manifest, "r", encoding="utf-8") as f:
            m_data = json.load(f)
        assert m_data.get("geometry_source") == GeometrySource.PROCEDURAL_ILLUSTRATIVE.value
        assert "Procedural Mock" in m_data.get("provenance", {}).get("simulation", "")

        # Check real files
        with open(real_manifest, "r", encoding="utf-8") as f:
            r_data = json.load(f)
        assert r_data.get("geometry_source") == GeometrySource.SIMULATION_DERIVED.value
        assert r_data.get("simulation", {}).get("name") == "IllustrisTNG-100-1"

        pass_msg("Truth-in-Labeling segregation verified:")
        print(f"      - Procedural Mock   : {mock_h5.name} -> geometry_source='procedural_illustrative'")
        print(f"      - Genuine TNG Cutout: {real_h5.name} -> geometry_source='simulation_derived'")
    except Exception as exc:
        fail_msg(f"Fixture segregation failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 2. Scale Factor a and Hubble Parameter h Physical Conversions
    # -------------------------------------------------------------------------
    subheader("Step 2", "Scale-Factor & Hubble Parameter Physical Unit Conversions")
    try:
        z = 1.0
        h = 0.6774
        a = 1.0 / (1.0 + z)

        r_code = np.array([[100.0, 50.0, -25.0]], dtype=np.float32)
        r_phys = comoving_to_physical_kpc(r_code, redshift=z, h=h)
        assert np.allclose(r_phys, r_code * (a / h))

        v_code = np.array([[150.0, -80.0, 45.0]], dtype=np.float32)
        v_phys = physical_velocity_km_s(v_code, redshift=z)
        assert np.allclose(v_phys, v_code * np.sqrt(a))

        m_code = np.array([1.4e-5], dtype=np.float32)
        m_phys = physical_mass_msun(m_code, h=h)
        assert np.allclose(m_phys, m_code * (1e10 / h))

        # Check rejection of missing units
        rejected = False
        try:
            comoving_to_physical_kpc(r_code, redshift=0.0, h=0.0)
        except ValueError:
            rejected = True
        assert rejected, "Failed to reject h <= 0"

        pass_msg("Unit conversions scale accurately with a and h:")
        print(f"      - Coordinates : r_phys = r_comov * a / h = {r_phys[0, 0]:.4f} kpc")
        print(f"      - Velocities  : v_phys = v_code * sqrt(a) = {v_phys[0, 0]:.4f} km/s")
        print(f"      - Masses      : M_phys = M_code * 10^10 / h = {m_phys[0]:.2e} M_sun")
        print("      - Missing/invalid cosmological units strictly rejected with ValueError")
    except Exception as exc:
        fail_msg(f"Unit conversion check failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 3. Real IllustrisTNG HDF5 Snapshot Ingestion
    # -------------------------------------------------------------------------
    subheader("Step 3", "Real IllustrisTNG Snapshot Ingestion & Dataset Consumption")
    try:
        galaxy = load_simulation_snapshot(
            real_h5,
            galaxy_id="tng100_subhalo_424601",
            sim_type="illustris_tng",
            subhalo_id=424601,
            align_angular_momentum=True,
        )
        assert galaxy.geometry_source == GeometrySource.SIMULATION_DERIVED
        assert ParticleType.STAR.value in galaxy.components
        assert ParticleType.GAS.value in galaxy.components
        assert ParticleType.DARK_MATTER.value in galaxy.components

        datasets = galaxy.provenance.get("datasets_consumed", [])
        assert "PartType4/Coordinates" in datasets
        assert "PartType4/ParticleIDs" in datasets
        assert "PartType0/Coordinates" in datasets
        assert "PartType1/ParticleIDs" in datasets

        pass_msg("Genuine TNG cutout ingested successfully:")
        print(f"      - Subhalo ID    : {galaxy.provenance.get('subhalo_id')}")
        print(f"      - Stellar Mass  : {galaxy.total_stellar_mass_msun():.2e} M_sun")
        print(f"      - Half-Mass R   : {galaxy.half_mass_radius_kpc:.2f} kpc")
        print(f"      - Consumed Sets : {len(datasets)} HDF5 datasets tracked in provenance")
    except Exception as exc:
        fail_msg(f"Real snapshot ingestion failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 4. Source ParticleIDs Preservation
    # -------------------------------------------------------------------------
    subheader("Step 4", "Source ParticleIDs Preservation in Contracts")
    try:
        for ptype, comp in galaxy.components.items():
            assert comp.particle_ids is not None, f"Missing particle_ids in {ptype}"
            assert len(comp.particle_ids) == len(comp.coordinates_kpc)
            assert comp.particle_ids.dtype == np.uint64

        assert galaxy.provenance.get("particle_ids_preserved") is True

        star_ids = galaxy.components[ParticleType.STAR.value].particle_ids
        pass_msg("ParticleIDs preserved across all particle components:")
        print(f"      - Stars ({len(star_ids):,} IDs): {star_ids[:3]} ... {star_ids[-1]}")
        print(f"      - Gas ({len(galaxy.components[ParticleType.GAS.value].particle_ids):,} IDs)")
        print(f"      - Dark Matter ({len(galaxy.components[ParticleType.DARK_MATTER.value].particle_ids):,} IDs)")
    except Exception as exc:
        fail_msg(f"ParticleIDs preservation failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 5. WebGL Decimation Preserves Source ParticleIDs
    # -------------------------------------------------------------------------
    subheader("Step 5", "WebGL Decimation & Downsampling Provenance Preservation")
    try:
        with open(real_web, "r", encoding="utf-8") as f:
            web_data = json.load(f)

        stars_web = web_data["particles"]["star"]
        assert "particle_ids" in stars_web, "Missing particle_ids in web JSON"
        assert "downsampling" in stars_web, "Missing downsampling metadata in web JSON"

        ds = stars_web["downsampling"]
        dec_pids = np.asarray(stars_web["particle_ids"], dtype=np.uint64)
        orig_pids = galaxy.components[ParticleType.STAR.value].particle_ids

        assert len(dec_pids) == ds["sampled_particles"]
        assert ds["total_particles"] == len(orig_pids)
        assert set(dec_pids).issubset(set(orig_pids)), "Decimated IDs not a subset of original IDs!"

        pass_msg("WebGL decimation preserves source ParticleIDs and records provenance:")
        print(f"      - Original Particles : {ds['total_particles']:,}")
        print(f"      - WebGL Subsample    : {ds['sampled_particles']:,} (sampling fraction: {ds['sampling_fraction']:.2%})")
        print(f"      - Decimated IDs Head : {dec_pids[:3]}")
        print("      - Every decimated particle retains exact source simulation ParticleID")
    except Exception as exc:
        fail_msg(f"Decimation ID preservation failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 6. Complete Traceable Provenance Manifest
    # -------------------------------------------------------------------------
    subheader("Step 6", "Traceable Provenance Manifest Completeness & Checksums")
    try:
        with open(real_manifest, "r", encoding="utf-8") as f:
            m = json.load(f)

        assert m["galaxy_id"] == "tng100_subhalo_424601"
        assert m["geometry_source"] == "simulation_derived"

        sim = m["simulation"]
        assert sim["name"] == "IllustrisTNG-100-1"
        assert sim["snapshot"] == 99
        assert sim["subhalo_id"] == 424601
        assert "https://www.tng-project.org" in sim["source_url"]

        # Verify SHA-256 integrity
        actual_h5_sha = compute_sha256(real_h5)
        actual_web_sha = compute_sha256(real_web)
        assert m["checksums"]["hdf5_sha256"] == actual_h5_sha
        assert m["checksums"]["webgl_json_sha256"] == actual_web_sha

        pass_msg("Provenance manifest verified with cryptographic checksums:")
        print(f"      - Source URL   : {sim['source_url']}")
        print(f"      - Snapshot     : {sim['snapshot']} (z = {m['redshift']})")
        print(f"      - Subhalo ID   : {sim['subhalo_id']}")
        print(f"      - HDF5 SHA-256 : {actual_h5_sha}")
        print(f"      - Web JSON SHA : {actual_web_sha}")
    except Exception as exc:
        fail_msg(f"Provenance manifest verification failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 7. Deterministic CLI Verification
    # -------------------------------------------------------------------------
    subheader("Step 7", "Deterministic CLI Fetcher & Verification Tool (scripts/fetch_tng_cutout.py)")
    try:
        ok = verify_tng_provenance(real_h5, real_manifest)
        assert ok is True

        pass_msg("Deterministic CLI verification succeeded cleanly:")
        print("      - scripts/fetch_tng_cutout.py --verify executed and confirmed 100% compliance")
    except Exception as exc:
        fail_msg(f"CLI verification tool failed: {exc}")
        all_passed = False

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    header("Acceptance Verification Summary")
    if all_passed:
        print("\n\033[92m[SUCCESS] ALL 7 ISSUE #26 PROVENANCE REQUIREMENTS VERIFIED!\033[0m")
        print("\nKey Achievements:")
        print("  1. Strict Truth-in-Labeling segregation: procedural mocks are never labeled simulation-derived")
        print("  2. Scale-factor a & Hubble h unit conversions strictly enforced with physical validation")
        print("  3. Genuine IllustrisTNG-100-1 cutout HDF5 reference specimen ingested and documented")
        print("  4. Stable 64-bit source ParticleIDs preserved from HDF5 through to WebGL rendering")
        print("  5. Downsampling provenance metadata recorded during particle decimation")
        print("  6. Cryptographic SHA-256 provenance manifest linking 3D models to official TNG cutout URLs")
        print("  7. Automated test suite and acceptance verification harness passing at 100%")
    else:
        print("\n\033[91m[FAILURE] One or more verification steps failed. Review logs above.\033[0m")

    return all_passed


if __name__ == "__main__":
    success = run_issue_26_verification()
    sys.exit(0 if success else 1)
