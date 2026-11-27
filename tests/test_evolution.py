import numpy as np
import pytest

from specsynth.contracts.evolution import (
    EvolutionaryTrackContract,
    MergerEvent,
    ProgenitorNode,
)
from specsynth.cosmology import TNG_COSMOLOGY
from specsynth.evolution import (
    generate_highz_starburst_evolution_track,
    generate_reference_tng_evolution_track,
    generate_spline_trajectory,
    verify_mass_assembly,
)


def test_progenitor_node_invariants():
    """Verify ProgenitorNode validation rules."""
    node = ProgenitorNode(
        redshift=1.0,
        cosmic_time_gyr=5.9,
        lookback_time_gyr=7.9,
        comoving_coords_mpc=(1.0, 2.0, 3300.0),
        physical_coords_kpc=(500.0, 1000.0, 0.0),
        stellar_mass_msun=1.0e10,
        sfr_msun_per_yr=5.0,
        metallicity_z=0.02,
        half_mass_radius_kpc=2.0,
    )
    assert node.redshift == 1.0
    d = node.to_dict()
    assert d["stellar_mass_msun"] == 1.0e10

    # Negative redshift rejected
    with pytest.raises(ValueError, match="Redshift must be non-negative"):
        ProgenitorNode(
            redshift=-0.5,
            cosmic_time_gyr=13.0,
            lookback_time_gyr=0.0,
            comoving_coords_mpc=(0.0, 0.0, 0.0),
            physical_coords_kpc=(0.0, 0.0, 0.0),
            stellar_mass_msun=1e10,
            sfr_msun_per_yr=1.0,
            metallicity_z=0.02,
            half_mass_radius_kpc=1.0,
        )

    # Negative or zero mass rejected
    with pytest.raises(ValueError, match="Stellar mass must be positive"):
        ProgenitorNode(
            redshift=0.5,
            cosmic_time_gyr=8.5,
            lookback_time_gyr=5.1,
            comoving_coords_mpc=(0.0, 0.0, 0.0),
            physical_coords_kpc=(0.0, 0.0, 0.0),
            stellar_mass_msun=0.0,
            sfr_msun_per_yr=1.0,
            metallicity_z=0.02,
            half_mass_radius_kpc=1.0,
        )


def test_evolutionary_track_contract_monotonicity():
    """Verify EvolutionaryTrackContract enforces monotonic redshift ordering."""
    n1 = ProgenitorNode(
        redshift=0.5,
        cosmic_time_gyr=8.5,
        lookback_time_gyr=5.1,
        comoving_coords_mpc=(0.0, 0.0, 1950.0),
        physical_coords_kpc=(0.0, 0.0, 0.0),
        stellar_mass_msun=1e10,
        sfr_msun_per_yr=3.0,
        metallicity_z=0.02,
        half_mass_radius_kpc=2.0,
    )
    n2 = ProgenitorNode(
        redshift=1.0,
        cosmic_time_gyr=5.9,
        lookback_time_gyr=7.9,
        comoving_coords_mpc=(0.0, 0.0, 3350.0),
        physical_coords_kpc=(0.0, 0.0, 0.0),
        stellar_mass_msun=5e9,
        sfr_msun_per_yr=8.0,
        metallicity_z=0.018,
        half_mass_radius_kpc=1.5,
    )

    # Ascending order is valid
    track = EvolutionaryTrackContract(
        galaxy_id="GAL-01",
        main_branch=[n1, n2],
    )
    assert len(track.main_branch) == 2
    assert track.version == "1.0.0"

    # Inverted order raises ValueError
    with pytest.raises(ValueError, match="main_branch nodes must be ordered monotonically by redshift"):
        EvolutionaryTrackContract(
            galaxy_id="GAL-01",
            main_branch=[n2, n1],
        )


def test_spline_trajectory_generation():
    """Verify smooth 3D spline trajectory generation across cosmological epochs."""
    track = generate_reference_tng_evolution_track("TNG-DISC-01")
    assert len(track.main_branch) == 10

    traj = generate_spline_trajectory(track.main_branch, n_samples=100)
    assert len(traj) == 100

    # Redshifts along the trajectory must increase monotonically
    z_vals = [p["redshift"] for p in traj]
    assert z_vals[0] == pytest.approx(0.0, abs=1e-3)
    assert z_vals[-1] == pytest.approx(8.0, abs=1e-3)
    assert np.all(np.diff(z_vals) >= 0.0)

    # Comoving distance (z_coord) must increase monotonically
    z_coords = [p["z_coord"] for p in traj]
    assert z_coords[0] == pytest.approx(0.0, abs=1e-2)
    assert z_coords[-1] > 8000.0  # D_C(z=8) is > 8000 Mpc


def test_mass_assembly_verification():
    """Verify Leitner-Kravtsov mass assembly validation."""
    track = generate_reference_tng_evolution_track("TNG-DISC-01")
    is_valid, report = verify_mass_assembly(track)

    assert is_valid is True
    assert report["is_physical"] is True
    assert 0.35 <= report["surviving_fraction"] <= 0.85
    assert report["n_snapshots"] == 10


def test_highz_starburst_lineage():
    """Verify high-z starburst progenitor track characteristics."""
    track = generate_highz_starburst_evolution_track("TNG-ANOM-01")
    assert track.galaxy_id == "TNG-ANOM-01"
    assert len(track.main_branch) == 5
    assert len(track.mergers) == 1
    assert track.mergers[0].merger_type == "major"

    # Redshift range covers z=3.5 to z=9.5
    assert track.main_branch[0].redshift == 3.5
    assert track.main_branch[-1].redshift == 9.5

    # Check serialization round-trip
    d = track.to_dict()
    reconstructed = EvolutionaryTrackContract.from_dict(d)
    assert reconstructed.galaxy_id == track.galaxy_id
    assert len(reconstructed.main_branch) == 5
    assert len(reconstructed.mergers) == 1
