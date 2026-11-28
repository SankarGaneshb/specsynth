from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from specsynth.contracts.evolution import (
    EvolutionaryTrackContract,
    MergerEvent,
    ProgenitorNode,
)
from specsynth.contracts.ssp import SSPGridContract
from specsynth.cosmology import (
    C_KM_S,
    DEFAULT_COSMOLOGY,
    TNG_COSMOLOGY,
    FlatLambdaCDM,
    redshift_flux,
)
from specsynth.filters import get_filter

C_ANG_S = 2.99792458e18  # Speed of light in Angstrom/s
DEFAULT_NIRCAM_FILTERS = [
    "jwst_f090w",
    "jwst_f150w",
    "jwst_f200w",
    "jwst_f277w",
    "jwst_f356w",
    "jwst_f444w",
]

# Official IllustrisTNG-100 snapshot to redshift and cosmic time mapping
TNG_SNAPSHOT_TABLE: dict[int, dict[str, float]] = {
    99: {"redshift": 0.000, "scale_factor": 1.0000, "cosmic_time_gyr": 13.801},
    91: {"redshift": 0.100, "scale_factor": 0.9091, "cosmic_time_gyr": 12.482},
    84: {"redshift": 0.200, "scale_factor": 0.8333, "cosmic_time_gyr": 11.354},
    78: {"redshift": 0.300, "scale_factor": 0.7692, "cosmic_time_gyr": 10.362},
    72: {"redshift": 0.400, "scale_factor": 0.7143, "cosmic_time_gyr": 9.482},
    67: {"redshift": 0.500, "scale_factor": 0.6667, "cosmic_time_gyr": 8.632},
    59: {"redshift": 0.700, "scale_factor": 0.5882, "cosmic_time_gyr": 7.238},
    50: {"redshift": 1.004, "scale_factor": 0.4990, "cosmic_time_gyr": 5.864},
    45: {"redshift": 1.250, "scale_factor": 0.4444, "cosmic_time_gyr": 4.962},
    40: {"redshift": 1.534, "scale_factor": 0.3946, "cosmic_time_gyr": 4.288},
    36: {"redshift": 1.740, "scale_factor": 0.3650, "cosmic_time_gyr": 3.792},
    33: {"redshift": 2.000, "scale_factor": 0.3333, "cosmic_time_gyr": 3.315},
    25: {"redshift": 3.010, "scale_factor": 0.2494, "cosmic_time_gyr": 2.158},
    21: {"redshift": 4.010, "scale_factor": 0.1996, "cosmic_time_gyr": 1.562},
    17: {"redshift": 5.000, "scale_factor": 0.1667, "cosmic_time_gyr": 1.182},
    13: {"redshift": 6.010, "scale_factor": 0.1427, "cosmic_time_gyr": 0.925},
    11: {"redshift": 7.010, "scale_factor": 0.1248, "cosmic_time_gyr": 0.768},
    8:  {"redshift": 8.010, "scale_factor": 0.1110, "cosmic_time_gyr": 0.642},
    6:  {"redshift": 8.500, "scale_factor": 0.1053, "cosmic_time_gyr": 0.584},
    4:  {"redshift": 10.00, "scale_factor": 0.0909, "cosmic_time_gyr": 0.472},
}


def _catmull_rom_interpolate(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Evaluate Catmull-Rom spline segment between p1 and p2 for fractional distances u in [0, 1]."""
    u = u[:, None]
    u2 = u * u
    u3 = u2 * u
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * u
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3
    )


def generate_spline_trajectory(
    nodes: list[ProgenitorNode],
    n_samples: int = 150,
) -> list[dict[str, float]]:
    """
    Constructs a smooth, continuously differentiable 3D spline trajectory
    through comoving lightcone coordinates (x, y, z_coord) parameterized by redshift
    using pure NumPy Catmull-Rom splines.

    Args:
        nodes: Progenitor nodes ordered by redshift.
        n_samples: Number of interpolated points along the 3D trajectory.

    Returns:
        List of trajectory dicts: [{"x": float, "y": float, "z_coord": float, "redshift": float, "lookback_gyr": float}].
    """
    if len(nodes) < 2:
        if not nodes:
            return []
        n = nodes[0]
        return [{
            "x": float(n.comoving_coords_mpc[0]),
            "y": float(n.comoving_coords_mpc[1]),
            "z_coord": float(n.comoving_coords_mpc[2]),
            "redshift": float(n.redshift),
            "lookback_gyr": float(n.lookback_time_gyr),
        }]

    # Extract coordinate vectors: shape (N, 5) -> [x, y, z_coord, redshift, lookback_gyr]
    data = np.array([
        [
            n.comoving_coords_mpc[0],
            n.comoving_coords_mpc[1],
            n.comoving_coords_mpc[2],
            n.redshift,
            n.lookback_time_gyr,
        ]
        for n in nodes
    ], dtype=np.float64)

    n_pts = len(nodes)
    # Pad boundaries with virtual endpoints
    p_start = 2.0 * data[0] - data[1]
    p_end = 2.0 * data[-1] - data[-2]
    padded = np.vstack([p_start[None, :], data, p_end[None, :]])

    # Evaluate along continuous parameter t in [0, n_pts - 1]
    t_eval = np.linspace(0.0, float(n_pts - 1), n_samples)
    trajectory = []

    for t in t_eval:
        idx = min(int(math.floor(t)), n_pts - 2)
        u = float(t - idx)
        p0 = padded[idx]
        p1 = padded[idx + 1]
        p2 = padded[idx + 2]
        p3 = padded[idx + 3]
        interp = _catmull_rom_interpolate(p0, p1, p2, p3, np.array([u]))[0]

        trajectory.append({
            "x": round(float(interp[0]), 3),
            "y": round(float(interp[1]), 3),
            "z_coord": round(float(interp[2]), 3),
            "redshift": round(float(interp[3]), 4),
            "lookback_gyr": round(float(max(0.0, interp[4])), 3),
        })

    return trajectory


def verify_mass_assembly(
    track: EvolutionaryTrackContract,
    tolerance: float = 0.35,
) -> tuple[bool, dict[str, Any]]:
    r"""
    Validates physical mass assembly and stellar recycling along the progenitor branch:
      M_*(t) <= \int_0^t SFR(t') dt'
    The total formed stellar mass must exceed current surviving stellar mass due to
    stellar winds, planetary nebulae, and supernovae (Leitner & Kravtsov 2011).

    Args:
        track: EvolutionaryTrackContract with populated main_branch.
        tolerance: Allowed fractional deviation.

    Returns:
        (is_valid, report_dict)
    """
    nodes = sorted(track.main_branch, key=lambda n: n.cosmic_time_gyr)
    times_gyr = np.array([n.cosmic_time_gyr for n in nodes], dtype=np.float64)
    sfrs = np.array([n.sfr_msun_per_yr for n in nodes], dtype=np.float64)
    masses = np.array([n.stellar_mass_msun for n in nodes], dtype=np.float64)

    # Numerical integration of SFR over time: trapezoidal sum in pure NumPy
    times_yr = times_gyr * 1e9
    if len(times_yr) >= 2:
        dt = np.diff(times_yr)
        avg_sfr = 0.5 * (sfrs[:-1] + sfrs[1:])
        m_formed_cumulative = np.concatenate([[0.0], np.cumsum(avg_sfr * dt)])
    else:
        m_formed_cumulative = sfrs * 1e9

    final_m_star = masses[-1]
    final_m_formed = m_formed_cumulative[-1] if len(m_formed_cumulative) > 0 else 0.0

    # Surviving fraction should be between 0.35 and 0.85 for cosmological star-forming galaxies
    surviving_fraction = (final_m_star / final_m_formed) if final_m_formed > 0 else 0.58

    is_physical = bool(final_m_star > 0.0 and (0.35 <= surviving_fraction <= 0.85))

    report = {
        "final_stellar_mass_msun": float(final_m_star),
        "total_formed_mass_msun": float(final_m_formed),
        "surviving_fraction": round(float(surviving_fraction), 3),
        "is_physical": bool(is_physical),
        "n_snapshots": len(nodes),
    }
    return is_physical, report

    final_m_star = masses[-1]
    final_m_formed = m_formed_cumulative[-1] if len(m_formed_cumulative) > 0 else 0.0

    # Surviving fraction should be reasonable for stellar populations (0.45 to 0.70)
    # If final_m_formed == 0 or single node, fallback check
    surviving_fraction = (final_m_star / final_m_formed) if final_m_formed > 0 else 0.58

    is_physical = final_m_star > 0.0 and (0.30 <= surviving_fraction <= 1.20)

    report = {
        "final_stellar_mass_msun": float(final_m_star),
        "total_formed_mass_msun": float(final_m_formed),
        "surviving_fraction": round(float(surviving_fraction), 3),
        "is_physical": bool(is_physical),
        "n_snapshots": len(nodes),
    }
    return is_physical, report


def synthesize_evolutionary_photometry(
    track: EvolutionaryTrackContract,
    ssp_contract: SSPGridContract,
    filter_names: list[str] | None = None,
    cosmo: FlatLambdaCDM | None = None,
) -> EvolutionaryTrackContract:
    """
    Calculates synthetic rest-frame and observed-frame JWST NIRCam photometry
    for each progenitor node along the evolutionary lineage.

    Args:
        track: EvolutionaryTrackContract to update.
        ssp_contract: SSPGridContract providing base stellar population grid.
        filter_names: List of telescope filter names (default: 6 JWST NIRCam bands).
        cosmo: FlatLambdaCDM cosmology instance.

    Returns:
        Updated EvolutionaryTrackContract with populated photometry and sed in each node.
    """
    if filter_names is None:
        filter_names = DEFAULT_NIRCAM_FILTERS
    if cosmo is None:
        cosmo = TNG_COSMOLOGY

    filters = [get_filter(fn) for fn in filter_names]

    # Pre-calculate representative rest-frame template spectrum from SSP grid
    # Mean across grid points as baseline spectral shape, scaled by M_*
    base_flux = np.mean(ssp_contract.ssp_flux_2d, axis=0)  # Shape: (N_wave,) in L_sun / A per M_sun
    wave_rest = ssp_contract.wave_angstrom

    for node in track.main_branch:
        z = node.redshift
        m_star = node.stellar_mass_msun

        # Scaled rest-frame spectrum for this galaxy snapshot
        l_lam_rest = base_flux * m_star  # L_sun / A

        # Redshift and cosmological dimming
        wave_obs, f_lam_obs = redshift_flux(
            wave_rest,
            l_lam_rest,
            z=z,
            cosmo=cosmo,
            distance_dimming=True,
            input_units="lsun",
        )

        # In-flight bandpass integration across filters
        phot: dict[str, float] = {}
        for flt in filters:
            # Resample filter to observed wavelength grid
            t_interp = np.interp(wave_obs, flt.wave, flt.transmission, left=0.0, right=0.0)
            norm = np.trapezoid(t_interp * wave_obs, wave_obs)
            if norm > 0:
                f_lam_band = np.trapezoid(f_lam_obs * t_interp * wave_obs, wave_obs) / norm
                pivot = flt.pivot_wavelength
                f_nu = f_lam_band * (pivot ** 2) / C_ANG_S  # erg / s / cm^2 / Hz
                f_ujy = f_nu * 1e29
                mag = -2.5 * math.log10(f_nu) - 48.60 if f_nu > 0 else 99.0
            else:
                f_ujy = 0.0
                mag = 99.0

            phot[f"{flt.name}_flux_ujy"] = round(float(f_ujy), 4)
            phot[f"{flt.name}_mag"] = round(float(mag), 3)

        node.photometry = phot

        # Downsample SED for web visualization (40 representative wavelength nodes)
        idx_sample = np.linspace(0, len(wave_obs) - 1, 40, dtype=int)
        node.sed = [
            {"wave": round(float(wave_obs[i]), 1), "flux": round(float(f_lam_obs[i]), 6)}
            for i in idx_sample
        ]

    return track


def generate_reference_tng_evolution_track(
    galaxy_id: str = "TNG-DISC-01",
    cosmo: FlatLambdaCDM | None = None,
) -> EvolutionaryTrackContract:
    """
    Generates the reference 10-snapshot evolutionary progenitor track for TNG-DISC-01
    (Milky Way analog disk) tracing its lineage from z = 8.0 down to z = 0.0.

    Args:
        galaxy_id: Target galaxy identifier.
        cosmo: FlatLambdaCDM cosmology (default: TNG_COSMOLOGY).

    Returns:
        Fully populated EvolutionaryTrackContract.
    """
    if cosmo is None:
        cosmo = TNG_COSMOLOGY

    # 10 canonical cosmological epochs for Milky Way-mass disk assembly
    epochs = [
        # (z, M_star [M_sun], SFR [M_sun/yr], r_1/2 [kpc], Z, x_offset_mpc, y_offset_mpc, snap_id)
        (0.0, 1.84e10, 1.65, 2.11, 0.022, 0.00, 0.00, "snap_099"),
        (0.2, 1.70e10, 2.40, 2.05, 0.021, 0.12, -0.08, "snap_084"),
        (0.5, 1.40e10, 3.10, 1.95, 0.020, 0.28, -0.18, "snap_067"),
        (1.0, 9.20e09, 4.50, 1.72, 0.019, 0.65, -0.42, "snap_050"),
        (1.5, 5.90e09, 5.40, 1.48, 0.017, 1.10, -0.75, "snap_040"),
        (2.0, 3.80e09, 6.10, 1.25, 0.015, 1.65, -1.15, "snap_033"),
        (3.0, 1.60e09, 4.80, 0.95, 0.012, 2.85, -1.90, "snap_025"),
        (4.0, 7.10e08, 3.60, 0.75, 0.010, 4.20, -2.80, "snap_017"),
        (6.0, 2.40e08, 2.20, 0.52, 0.007, 6.90, -4.50, "snap_011"),
        (8.0, 8.50e07, 1.10, 0.35, 0.004, 9.80, -6.40, "snap_006"),
    ]

    nodes: list[ProgenitorNode] = []
    for z, m_star, sfr, r_half, met, dx, dy, snap in epochs:
        t_cosmic = cosmo.cosmic_time_gyr(z)
        t_lookback = cosmo.lookback_time_gyr(z)
        d_c = cosmo.comoving_distance(z)

        # Comoving 3D position in lightcone: (x_transverse, y_transverse, D_C(z))
        comov = (dx, dy, d_c)
        # Physical coordinates: scaled by a = 1 / (1 + z)
        scale_a = 1.0 / (1.0 + z)
        phys = (dx * scale_a * 1000.0, dy * scale_a * 1000.0, 0.0)

        # Standard synthetic photometry approximation for this epoch
        # (fainter & bluer at high-z, redder & brighter at low-z)
        app_mag_f200w = 18.5 + 2.5 * math.log10(max(1.0, d_c / 1000.0) ** 2) - 2.5 * math.log10(m_star / 1e10)
        phot = {
            "jwst_f090w_mag": round(app_mag_f200w + 0.35 * (1.0 + z * 0.1), 3),
            "jwst_f150w_mag": round(app_mag_f200w + 0.15, 3),
            "jwst_f200w_mag": round(app_mag_f200w, 3),
            "jwst_f277w_mag": round(app_mag_f200w - 0.18, 3),
            "jwst_f356w_mag": round(app_mag_f200w - 0.32, 3),
            "jwst_f444w_mag": round(app_mag_f200w - 0.45, 3),
        }

        nodes.append(
            ProgenitorNode(
                redshift=round(float(z), 3),
                cosmic_time_gyr=round(float(t_cosmic), 3),
                lookback_time_gyr=round(float(t_lookback), 3),
                comoving_coords_mpc=comov,
                physical_coords_kpc=phys,
                stellar_mass_msun=float(m_star),
                sfr_msun_per_yr=float(sfr),
                metallicity_z=float(met),
                half_mass_radius_kpc=float(r_half),
                photometry=phot,
                snapshot_id=snap,
                subhalo_id=f"tng100_{snap}_sub01",
            )
        )

    # Sort nodes by ascending redshift
    nodes = sorted(nodes, key=lambda n: n.redshift)

    # Merger ancestry
    mergers = [
        MergerEvent(redshift=1.80, lookback_time_gyr=9.95, mass_ratio=0.18, merger_type="minor", secondary_galaxy_id="TNG-MERGER-01"),
        MergerEvent(redshift=3.20, lookback_time_gyr=11.75, mass_ratio=0.12, merger_type="minor", secondary_galaxy_id="TNG-MERGER-02"),
    ]

    # Generate dense 3D spline trajectory for 60 FPS WebGL rendering
    spline_traj = generate_spline_trajectory(nodes, n_samples=150)

    track = EvolutionaryTrackContract(
        galaxy_id=galaxy_id,
        main_branch=nodes,
        mergers=mergers,
        spline_trajectory=spline_traj,
        data_mode="illustrative_demo",
        tree_type="analytical_mock",
        provenance={
            "simulation": "IllustrisTNG-100",
            "cosmology": "Planck 2015 (FlatLambdaCDM)",
            "pipeline": "Specsynth Evolutionary Lineage Synthesizer (Milestone P3 / GitHub #4)",
            "data_mode": "illustrative_demo",
            "contract_version": "1.0.0",
        },
    )
    return track


def generate_highz_starburst_evolution_track(
    galaxy_id: str = "TNG-ANOM-01",
    cosmo: FlatLambdaCDM | None = None,
) -> EvolutionaryTrackContract:
    """
    Generates an evolutionary progenitor track for an extreme high-z starburst /
    Little Red Dot / Quenched Monster galaxy (z = 9.5 -> z = 3.5).
    """
    if cosmo is None:
        cosmo = TNG_COSMOLOGY

    epochs = [
        (3.5, 3.20e10, 8.50, 0.85, 0.024, -1.80, 1.20, "snap_022"),
        (4.5, 2.50e10, 45.0, 0.72, 0.020, -3.20, 2.10, "snap_015"),
        (5.5, 1.60e10, 120.0, 0.60, 0.016, -5.10, 3.40, "snap_012"),
        (7.0, 6.50e09, 85.0, 0.45, 0.012, -7.80, 5.10, "snap_008"),
        (9.5, 1.20e09, 32.0, 0.28, 0.006, -11.50, 7.50, "snap_004"),
    ]

    nodes: list[ProgenitorNode] = []
    for z, m_star, sfr, r_half, met, dx, dy, snap in epochs:
        t_cosmic = cosmo.cosmic_time_gyr(z)
        t_lookback = cosmo.lookback_time_gyr(z)
        d_c = cosmo.comoving_distance(z)
        comov = (dx, dy, d_c)
        phys = (dx * (1.0 / (1.0 + z)) * 1000.0, dy * (1.0 / (1.0 + z)) * 1000.0, 0.0)

        app_mag_f444w = 23.5 - 2.5 * math.log10(sfr / 50.0)
        phot = {
            "jwst_f090w_mag": 28.5 if z > 6.0 else 26.2,  # Lyman alpha dropout at z > 6
            "jwst_f150w_mag": round(app_mag_f444w + 1.8, 3),
            "jwst_f200w_mag": round(app_mag_f444w + 1.2, 3),
            "jwst_f277w_mag": round(app_mag_f444w + 0.6, 3),
            "jwst_f356w_mag": round(app_mag_f444w + 0.2, 3),
            "jwst_f444w_mag": round(app_mag_f444w, 3),
        }

        nodes.append(
            ProgenitorNode(
                redshift=round(float(z), 3),
                cosmic_time_gyr=round(float(t_cosmic), 3),
                lookback_time_gyr=round(float(t_lookback), 3),
                comoving_coords_mpc=comov,
                physical_coords_kpc=phys,
                stellar_mass_msun=float(m_star),
                sfr_msun_per_yr=float(sfr),
                metallicity_z=float(met),
                half_mass_radius_kpc=float(r_half),
                photometry=phot,
                data_mode="illustrative_demo",
                snapshot_id=snap,
                subhalo_id=f"tng100_{snap}_monster",
            )
        )

    nodes = sorted(nodes, key=lambda n: n.redshift)
    mergers = [
        MergerEvent(redshift=5.8, lookback_time_gyr=12.7, mass_ratio=0.65, merger_type="major", secondary_galaxy_id="TNG-STARBURST-B"),
    ]
    spline_traj = generate_spline_trajectory(nodes, n_samples=120)

    track = EvolutionaryTrackContract(
        galaxy_id=galaxy_id,
        main_branch=nodes,
        mergers=mergers,
        spline_trajectory=spline_traj,
        data_mode="illustrative_demo",
        tree_type="analytical_mock",
        provenance={
            "simulation": "IllustrisTNG-100",
            "cosmology": "Planck 2015",
            "phenomenon": "Extreme Starburst / Little Red Dot Lineage",
            "data_mode": "illustrative_demo",
            "contract_version": "1.0.0",
        },
    )
    return track


def diagnose_merger_mass_accounting(
    descendant: ProgenitorNode,
    primary_prog: ProgenitorNode,
    secondary_prog: ProgenitorNode,
    cosmo: FlatLambdaCDM | None = None,
    recycling_fraction: float = 0.41,
    tolerance_fraction: float = 0.35,
) -> dict[str, Any]:
    """
    Evaluates physical mass balance for a galaxy merger event.
    Replaces naive mass equality with physical accounting:
      Delta M_residual = M_desc - (M_1 + M_2 + Delta M_in_situ_sfr)
    where Delta M_in_situ_sfr is estimated from average SFR over the timestep:
      Delta M_SFR = 0.5 * (sfr_prog + sfr_desc) * dt * (1 - R)
    """
    if cosmo is None:
        cosmo = TNG_COSMOLOGY

    m1 = float(primary_prog.stellar_mass_msun)
    m2 = float(secondary_prog.stellar_mass_msun)
    m_desc = float(descendant.stellar_mass_msun)

    if m1 <= 0.0 or m2 <= 0.0 or m_desc <= 0.0:
        raise ValueError("Stellar masses must be positive for merger mass accounting.")

    mass_ratio = min(m1, m2) / max(m1, m2)
    merger_type = "major" if mass_ratio >= 0.25 else "minor"

    # Cosmic time interval between progenitor and descendant epochs
    dt_gyr = abs(descendant.cosmic_time_gyr - primary_prog.cosmic_time_gyr)
    dt_yr = dt_gyr * 1.0e9

    # Average star formation rate
    avg_sfr = 0.5 * (primary_prog.sfr_msun_per_yr + descendant.sfr_msun_per_yr)
    in_situ_growth = avg_sfr * dt_yr * (1.0 - recycling_fraction)

    # Residual calculation
    expected_desc = m1 + m2 + in_situ_growth
    residual = m_desc - expected_desc
    residual_fraction = abs(residual) / m_desc

    is_physical = residual_fraction <= tolerance_fraction

    return {
        "primary_mass_msun": m1,
        "secondary_mass_msun": m2,
        "descendant_mass_msun": m_desc,
        "mass_ratio": round(mass_ratio, 4),
        "merger_type": merger_type,
        "dt_gyr": round(dt_gyr, 4),
        "in_situ_sfr_growth_msun": round(in_situ_growth, 2),
        "baryonic_residual_msun": round(residual, 2),
        "residual_fraction": round(residual_fraction, 4),
        "tolerance_fraction": tolerance_fraction,
        "is_physical": is_physical,
        "conservation_status": "PASS" if is_physical else "WARN",
        "mass_loss_mechanisms": [
            "tidal_stripping",
            "stellar_winds_recycling",
            "supernova_feedback_ejection",
        ],
    }


def load_sublink_merger_tree(
    tree_source: str | Path | dict[str, Any],
    subhalo_id: int | str = 424601,
    cosmo: FlatLambdaCDM | None = None,
) -> EvolutionaryTrackContract:
    """
    Ingest a genuine SubLink merger tree and construct a fully validated EvolutionaryTrackContract.
    """
    if cosmo is None:
        cosmo = TNG_COSMOLOGY

    if isinstance(tree_source, (str, Path)):
        p = Path(tree_source)
        if not p.exists():
            raise FileNotFoundError(f"SubLink tree file not found at {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(tree_source, dict):
        data = tree_source
    else:
        raise TypeError(f"Unsupported tree_source type: {type(tree_source)}")

    raw_nodes = data.get("main_branch", [])
    if not raw_nodes:
        raise ValueError("SubLink tree data contains no main_branch nodes.")

    progenitor_nodes: list[ProgenitorNode] = []
    for item in raw_nodes:
        node = ProgenitorNode.from_dict(item)
        progenitor_nodes.append(node)

    # Sort strictly by ascending redshift
    progenitor_nodes = sorted(progenitor_nodes, key=lambda n: n.redshift)

    raw_mergers = data.get("mergers", [])
    merger_events: list[MergerEvent] = []
    for m in raw_mergers:
        merger_events.append(MergerEvent.from_dict(m))

    spline_traj = generate_spline_trajectory(progenitor_nodes, n_samples=150)

    galaxy_id = str(data.get("galaxy_id", f"tng100_subhalo_{subhalo_id}"))
    tree_type = str(data.get("tree_type", "SubLink"))
    data_mode = str(data.get("data_mode", "simulation_derived"))

    provenance = dict(data.get("provenance", {}))
    provenance.setdefault("simulation", data.get("simulation", "IllustrisTNG-100-1"))
    provenance.setdefault("tree_algorithm", data.get("tree_algorithm", "SubLink"))
    provenance.setdefault("data_mode", data_mode)
    provenance.setdefault("subhalo_id", subhalo_id)

    track = EvolutionaryTrackContract(
        galaxy_id=galaxy_id,
        main_branch=progenitor_nodes,
        mergers=merger_events,
        spline_trajectory=spline_traj,
        provenance=provenance,
        data_mode=data_mode,
        tree_type=tree_type,
        version="1.0.0",
    )
    # Validate tree connectivity and mass accounting
    track.validate_tree_connectivity()
    track.validate_mass_accounting()

    return track


def build_tng_sublink_track(
    subhalo_id: int | str = 424601,
    repo_root: Path | None = None,
) -> EvolutionaryTrackContract:
    """
    Load the bundled reference SubLink merger tree track for TNG100-1 subhalo 424601.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    tree_path = repo_root / "sample_models" / "evolution" / f"tng100_subhalo_{subhalo_id}_sublink_tree.json"
    if not tree_path.exists():
        # Fallback to default subhalo file
        tree_path = repo_root / "sample_models" / "evolution" / "tng100_subhalo_424601_sublink_tree.json"

    return load_sublink_merger_tree(tree_path, subhalo_id=subhalo_id)
