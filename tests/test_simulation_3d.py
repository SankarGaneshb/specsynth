"""
tests.test_simulation_3d
========================
Automated scientific test suite for Milestone 3 (P2 — Simulation-Derived 3D Galaxy Foundation).
Verifies:
  - Coordinate conversions (ckpc/h -> physical kpc)
  - Kinematic centering & Rodrigues angular momentum alignment
  - Spherical half-mass radius and density preservation
  - Decimation filter mass conservation
  - 3D star particle linking to non-parametric SFH & SPS matrix contraction
  - HDF5 snapshot export and re-import roundtrip
  - Truth in labeling contract invariants
"""

from __future__ import annotations

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
    align_to_angular_momentum,
    center_of_mass,
    center_particles,
    comoving_to_physical_kpc,
    compute_angular_momentum,
    compute_half_mass_radius,
    compute_rotation_matrix_to_z,
    decimate_particles,
)


def test_comoving_to_physical_kpc() -> None:
    """Verify r_phys = r_comov / ((1 + z) * h)."""
    coords_ckpc = np.array([
        [100.0, 200.0, 300.0],
        [0.0, 0.0, 0.0],
    ], dtype=np.float32)

    z = 1.0
    h = 0.7
    expected_factor = 1.0 / ((1.0 + z) * h)  # 1 / 1.4 = 0.7142857

    coords_phys = comoving_to_physical_kpc(coords_ckpc, redshift=z, h=h)
    assert np.allclose(coords_phys, coords_ckpc * expected_factor, atol=1e-5)

    with pytest.raises(ValueError, match="redshift must be non-negative"):
        comoving_to_physical_kpc(coords_ckpc, redshift=-0.5)
    with pytest.raises(ValueError, match="h must be positive"):
        comoving_to_physical_kpc(coords_ckpc, redshift=1.0, h=0.0)


def test_center_of_mass_and_centering() -> None:
    """Verify mass-weighted center of mass shifts the system to origin."""
    coords = np.array([
        [10.0, 0.0, 0.0],
        [-10.0, 0.0, 0.0],
        [0.0, 20.0, 0.0],
    ], dtype=np.float32)
    masses = np.array([1.0, 1.0, 2.0], dtype=np.float32)

    # CoM: x = (10 - 10 + 0)/4 = 0; y = (0 + 0 + 40)/4 = 10; z = 0
    com = center_of_mass(coords, masses)
    assert np.allclose(com, [0.0, 10.0, 0.0])

    centered, com_out = center_particles(coords, masses)
    assert np.allclose(com_out, [0.0, 10.0, 0.0])
    # New center of mass should be (0, 0, 0)
    new_com = center_of_mass(centered, masses)
    assert np.allclose(new_com, [0.0, 0.0, 0.0], atol=1e-6)


def test_angular_momentum_rodrigues_alignment() -> None:
    """
    Verify that rotating particles by R aligns total J with the +Z axis [0, 0, 1].
    Also verifies SO(3) properties: R^T @ R = I and det(R) = +1.
    """
    rng = np.random.default_rng(123)
    n = 1000

    # Create a planar rotating disk inclined in 3D
    r = rng.uniform(0.5, 10.0, size=n)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    x = r * np.cos(phi)
    y = r * np.sin(phi)
    z = rng.normal(0.0, 0.1, size=n)
    coords_flat = np.stack([x, y, z], axis=-1)

    # Tangential velocities
    v_circ = 200.0  # km/s
    vx = -v_circ * np.sin(phi)
    vy = v_circ * np.cos(phi)
    vz = rng.normal(0.0, 5.0, size=n)
    vels_flat = np.stack([vx, vy, vz], axis=-1)
    masses = np.ones(n, dtype=np.float32)

    # Arbitrary 3D tilt
    tilt_axis = np.array([1.0, 1.0, 0.5])
    R_tilt = compute_rotation_matrix_to_z(tilt_axis)
    coords_tilted = coords_flat @ R_tilt.T
    vels_tilted = vels_flat @ R_tilt.T

    # Align back to +Z using align_to_angular_momentum
    coords_aligned, vels_aligned, R_align = align_to_angular_momentum(
        coords_tilted, vels_tilted, masses
    )

    # 1. SO(3) mathematical invariants
    assert np.allclose(R_align.T @ R_align, np.eye(3), atol=1e-6)
    assert np.isclose(np.linalg.det(R_align), 1.0, atol=1e-6)

    # 2. Check total angular momentum in aligned frame
    j_aligned = compute_angular_momentum(coords_aligned, vels_aligned, masses)
    j_hat = j_aligned / np.linalg.norm(j_aligned)
    assert np.allclose(j_hat, [0.0, 0.0, 1.0], atol=1e-4)

    # 3. Pairwise distances must be strictly preserved under rotation
    dist_before = np.linalg.norm(coords_tilted[0] - coords_tilted[1])
    dist_after = np.linalg.norm(coords_aligned[0] - coords_aligned[1])
    assert np.isclose(dist_before, dist_after, atol=1e-5)


def test_half_mass_radius() -> None:
    """Verify spherical half-mass radius definition."""
    # Spherically symmetric shells with known masses
    coords = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 2.0, 0.0],
        [0.0, 0.0, 3.0],
        [4.0, 0.0, 0.0],
    ], dtype=np.float32)
    masses = np.array([10.0, 10.0, 10.0, 10.0], dtype=np.float32)  # total = 40, half = 20

    # Radii are 1, 2, 3, 4. Cum mass at r=2 is 20 -> half mass radius is 2.0
    r_half = compute_half_mass_radius(coords, masses)
    assert np.isclose(r_half, 2.0, atol=1e-5)


def test_decimate_particles_mass_conservation() -> None:
    """Verify decimation filter preserves total mass and reduces particle count."""
    rng = np.random.default_rng(42)
    n_dense = 20000
    coords = rng.normal(0.0, 5.0, size=(n_dense, 3)).astype(np.float32)
    vels = rng.normal(0.0, 100.0, size=(n_dense, 3)).astype(np.float32)
    masses = rng.uniform(1e4, 5e4, size=n_dense).astype(np.float32)

    total_mass_initial = float(np.sum(masses))

    target_n = 3000
    c_dec, v_dec, m_dec, idx = decimate_particles(coords, vels, masses, max_particles=target_n, seed=42)

    assert len(c_dec) == target_n
    assert len(v_dec) == target_n
    assert len(m_dec) == target_n
    assert len(idx) == target_n

    # Total mass must be strictly conserved within 1e-4
    total_mass_decimated = float(np.sum(m_dec))
    assert np.isclose(total_mass_initial, total_mass_decimated, rtol=1e-4)


def test_mock_simulation_snapshot_generation() -> None:
    """Verify mock simulation snapshot generation fulfills contracts."""
    galaxy = generate_mock_simulation_snapshot(
        galaxy_id="tng100_subhalo_009873",
        redshift=0.5,
        n_stars=4000,
        n_gas=1500,
        n_dm=2000,
        total_stellar_mass_msun=2.5e10,
        seed=42,
    )

    assert galaxy.galaxy_id == "tng100_subhalo_009873"
    assert galaxy.geometry_source == GeometrySource.PROCEDURAL_ILLUSTRATIVE
    assert galaxy.coordinate_frame == CoordinateFrame.PHYSICAL_REST
    assert np.isclose(galaxy.redshift, 0.5)
    assert galaxy.half_mass_radius_kpc > 0.0

    # Verify components
    assert ParticleType.STAR.value in galaxy.components
    assert ParticleType.GAS.value in galaxy.components
    assert ParticleType.DARK_MATTER.value in galaxy.components

    stars = galaxy.components[ParticleType.STAR.value]
    assert len(stars.masses_msun) == 4000
    assert stars.ages_yr is not None
    assert stars.metallicities_z is not None
    assert np.all(stars.ages_yr >= 0.0)
    assert np.all(stars.metallicities_z > 0.0)

    # Check total stellar mass
    assert np.isclose(galaxy.total_stellar_mass_msun(), 2.5e10, rtol=1e-3)

    # Verify web JSON export serialization
    web_json = galaxy.to_web_json(max_particles_per_component=1000)
    assert web_json["version"] == "1.0.0"
    assert web_json["geometry_source"] == "procedural_illustrative"
    assert len(web_json["particles"]["star"]["coordinates_kpc"]) == 1000


def test_simulation_3d_hdf5_roundtrip() -> None:
    """Verify HDF5 snapshot export and re-import."""
    h5py = pytest.importorskip("h5py")

    galaxy_orig = generate_mock_simulation_snapshot(
        galaxy_id="tng100_subhalo_009873",
        redshift=0.25,
        n_stars=2000,
        n_gas=500,
        n_dm=1000,
        seed=101,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = Path(tmpdir) / "subhalo_9873.hdf5"
        export_galaxy3d_hdf5(galaxy_orig, h5_path)
        assert h5_path.exists()

        # Re-import
        galaxy_reloaded = load_simulation_snapshot(
            h5_path,
            sim_type="tng",
            galaxy_id="tng100_subhalo_009873",
            subhalo_id=9873,
            redshift=0.25,
        )

        assert galaxy_reloaded.galaxy_id == "tng100_subhalo_009873"
        assert galaxy_reloaded.geometry_source == galaxy_orig.geometry_source
        assert np.isclose(galaxy_reloaded.redshift, 0.25)

        orig_stars = galaxy_orig.components[ParticleType.STAR.value]
        reloaded_stars = galaxy_reloaded.components[ParticleType.STAR.value]
        assert len(reloaded_stars.masses_msun) == len(orig_stars.masses_msun)

        # Stellar mass parity
        assert np.isclose(
            galaxy_orig.total_stellar_mass_msun(),
            galaxy_reloaded.total_stellar_mass_msun(),
            rtol=1e-3,
        )


def test_3d_star_particles_to_sfh_and_sps_contraction() -> None:
    """
    Verify extracting non-parametric SFH from 3D star particles and
    contracting it with an SPS grid (S = SFH . SSP).
    """
    galaxy = generate_mock_simulation_snapshot(
        galaxy_id="tng100_subhalo_009873",
        redshift=0.0,
        n_stars=3000,
        total_stellar_mass_msun=1.5e10,
        seed=77,
    )

    # 40 ages x 4 metallicities
    ages_yr = np.logspace(7.0, 10.1, 40)
    mets_z = np.array([0.004, 0.008, 0.019, 0.03])

    # 1. Extract non-parametric SFH without formed mass scaling
    sfh_surviving = galaxy.extract_non_parametric_sfh(ages_yr, mets_z, formed_mass=False)
    assert sfh_surviving.shape == (1, 40 * 4)

    # Mass in SFH must equal total surviving stellar mass
    assert np.isclose(np.sum(sfh_surviving), galaxy.total_stellar_mass_msun(), rtol=1e-5)

    # 2. Extract non-parametric SFH with formed mass scaling (Leitner & Kravtsov 2011)
    sfh_formed = galaxy.extract_non_parametric_sfh(ages_yr, mets_z, formed_mass=True)
    # Formed mass must be strictly greater than surviving mass due to stellar death
    assert np.sum(sfh_formed) > np.sum(sfh_surviving)
    # Typical surviving fraction ~ 0.5 - 0.7 for evolved populations
    ratio = np.sum(sfh_surviving) / np.sum(sfh_formed)
    assert 0.45 < ratio < 0.75

    # 3. Contract with mock SSP spectral grid
    n_wave = 1500
    mock_ssp_grid = np.ones((40 * 4, n_wave), dtype=np.float64) * 1e-4

    # Matrix contraction: S = SFH @ SSP
    synth_sed = sfh_formed @ mock_ssp_grid
    assert synth_sed.shape == (1, n_wave)
    assert np.all(synth_sed > 0.0)
    assert np.all(np.isfinite(synth_sed))


def test_truth_in_labeling_contract_invariants() -> None:
    """Verify that empirical simulation data and procedural mocks are strictly segregated."""
    # Empty components for simulation-derived model must raise error
    with pytest.raises(ValueError, match="Simulation-derived galaxy must contain at least one particle component"):
        Galaxy3DContract(
            galaxy_id="invalid_empty_sim",
            geometry_source=GeometrySource.SIMULATION_DERIVED,
            coordinate_frame=CoordinateFrame.PHYSICAL_REST,
            redshift=0.0,
            center_of_mass_kpc=(0.0, 0.0, 0.0),
            half_mass_radius_kpc=2.0,
            components={},
        )
