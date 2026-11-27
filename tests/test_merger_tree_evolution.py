from __future__ import annotations

import json
from pathlib import Path
import pytest

from specsynth.contracts.evolution import (
    EvolutionaryTrackContract,
    MergerEvent,
    ProgenitorNode,
)
from specsynth.cosmology import TNG_COSMOLOGY
from specsynth.evolution import (
    build_tng_sublink_track,
    diagnose_merger_mass_accounting,
    generate_highz_starburst_evolution_track,
    generate_reference_tng_evolution_track,
    load_sublink_merger_tree,
)
from specsynth.mcp.server import SpecsynthMCPServer
from scripts.fetch_tng_merger_tree import verify_merger_tree_provenance


def test_sublink_merger_tree_ingestion():
    """Verify ingestion of genuine SubLink merger tree across cosmological epochs."""
    track = build_tng_sublink_track(subhalo_id=424601)

    assert track.galaxy_id == "tng100_subhalo_424601"
    assert track.data_mode == "simulation_derived"
    assert track.tree_type == "SubLink"
    assert len(track.main_branch) == 10

    # Redshift spans z=0 to z=8.5
    assert track.main_branch[0].redshift == pytest.approx(0.0, abs=1e-3)
    assert track.main_branch[-1].redshift == pytest.approx(8.5, abs=1e-3)

    # Masses and SFR
    z0 = track.main_branch[0]
    assert z0.stellar_mass_msun == pytest.approx(3006610432.0, rel=1e-3)
    assert z0.gas_mass_msun > 0.0
    assert z0.dark_matter_mass_msun > z0.stellar_mass_msun
    assert z0.total_mass_msun == pytest.approx(z0.stellar_mass_msun + z0.gas_mass_msun + z0.dark_matter_mass_msun)

    # Snapshots monotonic ascending by redshift
    redshifts = [n.redshift for n in track.main_branch]
    assert all(x < y for x, y in zip(redshifts, redshifts[1:]))


def test_source_native_identifiers_and_links():
    """Verify source-native SubLink identifiers and tree connectivity."""
    track = build_tng_sublink_track(subhalo_id=424601)

    # Validate parent-child connectivity
    assert track.validate_tree_connectivity() is True

    # Check root node (z=0, Snap 99)
    root = track.main_branch[0]
    assert root.snap_num == 99
    assert root.subfind_id == 424601
    assert root.descendant_subhalo_id == ""

    # Check child nodes link to descendant
    for i in range(1, len(track.main_branch)):
        node = track.main_branch[i]
        expected_descendant = track.main_branch[i - 1].subhalo_id
        assert node.descendant_subhalo_id == expected_descendant
        assert "sublink_id" in node.tree_links


def test_merger_mass_accounting_diagnostics():
    """Verify physical mass balance for major and minor mergers."""
    track = build_tng_sublink_track(subhalo_id=424601)

    assert len(track.mergers) == 2
    minor_m = track.mergers[0]
    major_m = track.mergers[1]

    # Minor merger at z=0.5
    assert minor_m.redshift == pytest.approx(0.50, abs=1e-3)
    assert minor_m.merger_type == "minor"
    assert minor_m.mass_ratio < 0.25

    # Major merger at z=1.534
    assert major_m.redshift == pytest.approx(1.534, abs=1e-3)
    assert major_m.merger_type == "major"
    assert major_m.mass_ratio >= 0.25

    # Validate tolerance budgets
    results = track.validate_mass_accounting(tolerance_fraction=0.35)
    assert len(results) == 2
    assert all(r["status"] == "PASS" for r in results)
    assert all(r["residual_fraction"] <= 0.35 for r in results)


def test_diagnose_merger_mass_accounting_helper():
    """Verify diagnose_merger_mass_accounting calculates physical residuals."""
    desc = ProgenitorNode(
        redshift=0.500,
        cosmic_time_gyr=8.609,
        lookback_time_gyr=5.194,
        comoving_coords_mpc=(0.0, 0.0, 1945.0),
        physical_coords_kpc=(0.0, 0.0, 0.0),
        stellar_mass_msun=2.42e9,
        sfr_msun_per_yr=0.72,
        metallicity_z=0.02,
        half_mass_radius_kpc=2.0,
    )
    p1 = ProgenitorNode(
        redshift=0.550,
        cosmic_time_gyr=8.350,
        lookback_time_gyr=5.453,
        comoving_coords_mpc=(0.0, 0.0, 2100.0),
        physical_coords_kpc=(0.0, 0.0, 0.0),
        stellar_mass_msun=1.95e9,
        sfr_msun_per_yr=0.85,
        metallicity_z=0.019,
        half_mass_radius_kpc=1.9,
    )
    p2 = ProgenitorNode(
        redshift=0.550,
        cosmic_time_gyr=8.350,
        lookback_time_gyr=5.453,
        comoving_coords_mpc=(0.0, 0.0, 2100.0),
        physical_coords_kpc=(0.0, 0.0, 0.0),
        stellar_mass_msun=3.55e8,
        sfr_msun_per_yr=0.30,
        metallicity_z=0.016,
        half_mass_radius_kpc=1.0,
    )

    report = diagnose_merger_mass_accounting(desc, p1, p2, cosmo=TNG_COSMOLOGY)
    assert report["is_physical"] is True
    assert report["merger_type"] == "minor"
    assert report["mass_ratio"] == pytest.approx(3.55e8 / 1.95e9, abs=1e-3)
    assert report["residual_fraction"] <= 0.35
    assert "tidal_stripping" in report["mass_loss_mechanisms"]


def test_edge_cases_and_error_handling():
    """Verify validation guards reject broken trees, invalid data modes, or non-monotonic times."""
    # 1. Invalid data_mode
    with pytest.raises(ValueError, match="Invalid data_mode"):
        EvolutionaryTrackContract(
            galaxy_id="GAL-FAIL",
            main_branch=[
                ProgenitorNode(
                    redshift=0.0, cosmic_time_gyr=13.8, lookback_time_gyr=0.0,
                    comoving_coords_mpc=(0, 0, 0), physical_coords_kpc=(0, 0, 0),
                    stellar_mass_msun=1e10, sfr_msun_per_yr=1.0, metallicity_z=0.02, half_mass_radius_kpc=1.0
                )
            ],
            data_mode="fabricated_simulation",
        )

    # 2. Broken tree connectivity
    n1 = ProgenitorNode(
        redshift=0.0, cosmic_time_gyr=13.8, lookback_time_gyr=0.0,
        comoving_coords_mpc=(0, 0, 0), physical_coords_kpc=(0, 0, 0),
        stellar_mass_msun=1e10, sfr_msun_per_yr=1.0, metallicity_z=0.02, half_mass_radius_kpc=1.0,
        subhalo_id="SUB_A"
    )
    n2 = ProgenitorNode(
        redshift=0.5, cosmic_time_gyr=8.6, lookback_time_gyr=5.2,
        comoving_coords_mpc=(0, 0, 1945), physical_coords_kpc=(0, 0, 0),
        stellar_mass_msun=8e9, sfr_msun_per_yr=1.5, metallicity_z=0.02, half_mass_radius_kpc=1.0,
        subhalo_id="SUB_B", descendant_subhalo_id="WRONG_PARENT"
    )
    track_broken = EvolutionaryTrackContract(
        galaxy_id="GAL-BROKEN",
        main_branch=[n1, n2],
        data_mode="simulation_derived",
    )
    with pytest.raises(ValueError, match="Tree connectivity broken"):
        track_broken.validate_tree_connectivity()

    # 3. Excessive merger mass violation (> 35%)
    merger_bad = MergerEvent(
        redshift=0.5, lookback_time_gyr=5.2, mass_ratio=0.5, merger_type="major",
        secondary_galaxy_id="M2",
        mass_accounting={"residual_fraction": 0.85, "conservation_status": "WARN"}
    )
    track_violating = EvolutionaryTrackContract(
        galaxy_id="GAL-VIOLATING",
        main_branch=[n1],
        mergers=[merger_bad],
        data_mode="simulation_derived",
    )
    with pytest.raises(ValueError, match="violates mass balance budget"):
        track_violating.validate_mass_accounting(tolerance_fraction=0.35)


def test_cosmological_time_consistency():
    """Verify cosmic time, lookback time, and scale factor match TNG_COSMOLOGY."""
    track = build_tng_sublink_track(subhalo_id=424601)
    cosmo = TNG_COSMOLOGY

    for node in track.main_branch:
        expected_time = cosmo.cosmic_time_gyr(node.redshift)
        assert node.cosmic_time_gyr == pytest.approx(expected_time, rel=1e-2)
        expected_lookback = cosmo.lookback_time_gyr(node.redshift)
        assert node.lookback_time_gyr == pytest.approx(expected_lookback, rel=1e-2)


def test_truth_in_labeling_data_mode():
    """Verify data_mode segregation across contracts and MCP tools."""
    sublink = build_tng_sublink_track(424601)
    assert sublink.data_mode == "simulation_derived"

    demo_disk = generate_reference_tng_evolution_track("TNG-DISC-01")
    assert demo_disk.data_mode == "illustrative_demo"

    demo_monster = generate_highz_starburst_evolution_track("TNG-ANOM-01")
    assert demo_monster.data_mode == "illustrative_demo"

    # MCP tool returns simulation_derived for simulation requests
    mcp = SpecsynthMCPServer()
    res_sim = mcp._tool_get_evolution_track({"galaxy_id": "tng100_subhalo_424601", "data_mode": "simulation_derived"})
    assert res_sim.get("data_mode") == "simulation_derived"
    assert len(res_sim.get("main_branch", [])) == 10

    # MCP tool returns illustrative_demo when demo mode requested
    res_demo = mcp._tool_get_evolution_track({"galaxy_id": "TNG-DISC-01", "data_mode": "illustrative_demo"})
    assert res_demo.get("data_mode") == "illustrative_demo"


def test_fetch_script_and_manifest_reproducibility():
    """Verify scripts/fetch_tng_merger_tree.py verification harness passes."""
    assert verify_merger_tree_provenance() is True
