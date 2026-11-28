"""
Unit tests for versioned contracts in specsynth.contracts.
Enforces P0 Scope and Architecture Freeze (Issue #14).
"""

import numpy as np
import pytest

from specsynth.contracts import (
    CANONICAL_MCP_TOOLS,
    CoordinateFrame,
    DataMode,
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
    PhotometryPointContract,
    SimulationGalaxyContract,
    SSPGridContract,
    SyntheticObservationContract,
    get_canonical_tool_schema,
    propagate_mode,
)


def test_ssp_grid_contract_valid():
    ages = np.array([1e7, 1e8, 1e9])
    mets = np.array([0.004, 0.02])
    wave = np.linspace(1000, 10000, 50)
    flux_2d = np.ones((len(ages) * len(mets), len(wave)), dtype=np.float32)

    contract = SSPGridContract(
        source_engine="toy",
        engine_version="1.0.0",
        imf="chabrier_2003",
        isochrones="mist",
        ages_yr=ages,
        mets_z=mets,
        wave_angstrom=wave,
        ssp_flux_2d=flux_2d,
    )
    assert contract.version == "1.0.0"
    summary = contract.to_dict()
    assert summary["n_ages"] == 3
    assert summary["n_mets"] == 2
    assert summary["n_wave"] == 50


def test_ssp_grid_contract_invalid_monotonicity():
    ages = np.array([1e8, 1e7, 1e9])  # Not monotonic
    mets = np.array([0.004, 0.02])
    wave = np.linspace(1000, 10000, 50)
    flux_2d = np.ones((6, 50), dtype=np.float32)

    with pytest.raises(ValueError, match="strictly monotonically increasing"):
        SSPGridContract(
            source_engine="toy",
            engine_version="1.0.0",
            imf="chabrier_2003",
            isochrones="mist",
            ages_yr=ages,
            mets_z=mets,
            wave_angstrom=wave,
            ssp_flux_2d=flux_2d,
        )


def test_ssp_grid_contract_negative_flux():
    ages = np.array([1e7, 1e8])
    mets = np.array([0.02])
    wave = np.array([1000.0, 2000.0])
    flux_2d = np.array([[-1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

    with pytest.raises(ValueError, match="unphysical negative luminosity"):
        SSPGridContract(
            source_engine="toy",
            engine_version="1.0.0",
            imf="chabrier_2003",
            isochrones="mist",
            ages_yr=ages,
            mets_z=mets,
            wave_angstrom=wave,
            ssp_flux_2d=flux_2d,
        )


def test_simulation_galaxy_contract_valid():
    gal = SimulationGalaxyContract(
        galaxy_id="TNG100-1-Subhalo-424601",
        simulation_name="IllustrisTNG-100",
        snapshot=99,
        redshift=0.0,
        stellar_mass_msun=1.2e11,
        sfr_msun_per_yr=2.5,
        metallicity_mass_fraction=0.019,
        tau_diffuse=0.5,
        tau_birth=1.0,
        sfh_onset_gyr=13.0,
        sfh_tau_gyr=2.0,
        celestial_coordinates_deg=(53.1, -27.8),
    )
    assert gal.galaxy_id == "TNG100-1-Subhalo-424601"
    d = gal.to_dict()
    assert d["stellar_mass_msun"] == 1.2e11
    assert d["celestial_coordinates_deg"] == (53.1, -27.8)


def test_simulation_galaxy_contract_invalid_ranges():
    with pytest.raises(ValueError, match="stellar_mass_msun must be positive"):
        SimulationGalaxyContract(
            galaxy_id="G1",
            simulation_name="Test",
            snapshot=99,
            redshift=1.0,
            stellar_mass_msun=-1e9,
            sfr_msun_per_yr=1.0,
            metallicity_mass_fraction=0.02,
            tau_diffuse=0.5,
            tau_birth=1.0,
            sfh_onset_gyr=10.0,
            sfh_tau_gyr=2.0,
        )


def test_galaxy_3d_contract():
    n_stars = 100
    coords = np.random.uniform(-10, 10, size=(n_stars, 3)).astype(np.float32)
    vels = np.random.uniform(-200, 200, size=(n_stars, 3)).astype(np.float32)
    masses = np.full(n_stars, 1e5, dtype=np.float32)
    ages = np.full(n_stars, 5e9, dtype=np.float32)
    mets = np.full(n_stars, 0.019, dtype=np.float32)

    star_batch = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=coords,
        velocities_km_s=vels,
        masses_msun=masses,
        ages_yr=ages,
        metallicities_z=mets,
    )

    galaxy_3d = Galaxy3DContract(
        galaxy_id="TNG100-1-Subhalo-424601",
        geometry_source=GeometrySource.SIMULATION_DERIVED,
        coordinate_frame=CoordinateFrame.PHYSICAL_REST,
        redshift=0.0,
        center_of_mass_kpc=(0.0, 0.0, 0.0),
        half_mass_radius_kpc=4.8,
        components={"star": star_batch},
    )

    assert galaxy_3d.total_stellar_mass_msun() == pytest.approx(1e7)
    summary = galaxy_3d.to_summary_dict()
    assert summary["geometry_source"] == "simulation_derived"
    assert summary["particle_counts"]["star"] == 100


def test_synthetic_observation_contract():
    phot = [
        PhotometryPointContract(
            filter_name="jwst_nircam_f200w",
            pivot_wavelength_angstrom=19886.0,
            flux_density_ujy=12.5,
            ab_magnitude=21.16,
            ab_mag_error=0.02,
            snr=54.2,
        )
    ]
    sed_wave = np.linspace(1000, 50000, 100)
    sed_flux = np.ones(100, dtype=np.float32) * 1e-18

    obs = SyntheticObservationContract(
        galaxy_id="G1",
        redshift=2.0,
        cosmology={"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911},
        dust_model="charlot_fall_2000",
        igm_model="madau_1995",
        ssp_model="fsps_v3.2",
        photometry=phot,
        sed_wave_angstrom=sed_wave,
        sed_flux_obs_cgs=sed_flux,
    )
    assert len(obs.photometry) == 1
    d = obs.to_dict()
    assert d["n_sed_points"] == 100


def test_canonical_mcp_tools():
    assert "specsynth_list_filters" in CANONICAL_MCP_TOOLS
    assert "specsynth_inspect_galaxy" in CANONICAL_MCP_TOOLS
    assert "specsynth_calculate_cosmology" in CANONICAL_MCP_TOOLS
    assert "specsynth_get_3d_galaxy" in CANONICAL_MCP_TOOLS
    assert "specsynth_run_sentry_audit" in CANONICAL_MCP_TOOLS

    schema = get_canonical_tool_schema("specsynth_inspect_galaxy")
    assert schema["name"] == "specsynth_inspect_galaxy"
    assert "galaxy_id" in schema["inputSchema"]["properties"]
    assert schema["annotations"]["readOnlyHint"] is True

    with pytest.raises(KeyError):
        get_canonical_tool_schema("non_existent_tool")


def test_data_mode_enum_and_propagation():
    """Verify DataMode parsing, categories, and non-promotion invariant."""
    assert DataMode.from_str("simulation_derived") == DataMode.SIMULATION_DERIVED
    assert DataMode.from_str("cached_reference") == DataMode.CACHED_REFERENCE
    assert DataMode.from_str("live_computation") == DataMode.LIVE_COMPUTATION
    assert DataMode.from_str("analytical_mock") == DataMode.ANALYTICAL_MOCK
    assert DataMode.from_str("illustrative_demo") == DataMode.ILLUSTRATIVE_DEMO

    # Empirical vs mock classification
    assert DataMode.SIMULATION_DERIVED.is_empirical_science() is True
    assert DataMode.LIVE_COMPUTATION.is_empirical_science() is True
    assert DataMode.ANALYTICAL_MOCK.is_empirical_science() is False
    assert DataMode.ANALYTICAL_MOCK.is_mock_or_demo() is True

    # Non-promotion invariant
    assert propagate_mode(DataMode.SIMULATION_DERIVED) == DataMode.SIMULATION_DERIVED
    assert propagate_mode(DataMode.ANALYTICAL_MOCK, DataMode.ANALYTICAL_MOCK) == DataMode.ANALYTICAL_MOCK

    with pytest.raises(ValueError, match="Non-promotion invariant violation"):
        propagate_mode(DataMode.ANALYTICAL_MOCK, DataMode.SIMULATION_DERIVED)

    with pytest.raises(ValueError, match="Non-promotion invariant violation"):
        propagate_mode(DataMode.ILLUSTRATIVE_DEMO, DataMode.LIVE_COMPUTATION)


def test_truth_in_labeling_procedural_cannot_be_simulation_derived():
    """Verify that procedural mock cannot claim empirical simulation_derived mode."""
    stars = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=np.zeros((10, 3)),
        velocities_km_s=np.zeros((10, 3)),
        masses_msun=np.ones(10) * 1e4,
    )

    with pytest.raises(ValueError, match="Truth-in-labeling violation"):
        Galaxy3DContract(
            galaxy_id="mock_specimen",
            geometry_source=GeometrySource.PROCEDURAL_ILLUSTRATIVE,
            coordinate_frame=CoordinateFrame.PHYSICAL_REST,
            redshift=1.0,
            center_of_mass_kpc=(0.0, 0.0, 0.0),
            half_mass_radius_kpc=2.0,
            components={"star": stars},
            data_mode="simulation_derived",
        )


def test_galaxy3d_non_promotion_to_observation():
    """Verify non-promotion invariant when generating observations from 3D models."""
    stars = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=np.zeros((10, 3)),
        velocities_km_s=np.zeros((10, 3)),
        masses_msun=np.ones(10) * 1e4,
    )
    mock_galaxy = Galaxy3DContract(
        galaxy_id="mock_specimen",
        geometry_source=GeometrySource.PROCEDURAL_ILLUSTRATIVE,
        coordinate_frame=CoordinateFrame.PHYSICAL_REST,
        redshift=1.0,
        center_of_mass_kpc=(0.0, 0.0, 0.0),
        half_mass_radius_kpc=2.0,
        components={"star": stars},
        data_mode="analytical_mock",
    )

    phot = [
        PhotometryPointContract(
            filter_name="jwst_nircam_f200w",
            pivot_wavelength_angstrom=19886.0,
            flux_density_ujy=10.0,
            ab_magnitude=21.4,
        )
    ]
    sed_wave = np.linspace(1000, 50000, 20)
    sed_flux = np.ones(20, dtype=np.float32) * 1e-18
    cosmo = {"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911}

    # Inherits analytical_mock
    obs = mock_galaxy.to_observation_contract(
        photometry_points=phot,
        sed_wave_angstrom=sed_wave,
        sed_flux_obs_cgs=sed_flux,
        cosmology=cosmo,
    )
    assert obs.data_mode == "analytical_mock"

    # Attempted promotion raises
    with pytest.raises(ValueError, match="Non-promotion invariant violation"):
        mock_galaxy.to_observation_contract(
            photometry_points=phot,
            sed_wave_angstrom=sed_wave,
            sed_flux_obs_cgs=sed_flux,
            cosmology=cosmo,
            requested_data_mode="simulation_derived",
        )

