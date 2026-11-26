"""
specsynth.sfh
=============
Physical Star Formation History (SFH) models, mass normalization, and SFR decoupling.
Enforces P1.M2.2 and P1.M2.3 scientific foundations.
"""

from __future__ import annotations

from typing import Any, Literal
import numpy as np


def document_sfr_conventions() -> dict[str, str]:
    """
    Formally document the difference between cosmological snapshot SFR and model-derived SFH.
    """
    return {
        "snapshot_sfr": (
            "Instantaneous or short-timescale (e.g. 10-100 Myr) gas star formation rate "
            "reported in cosmological simulation snapshots (e.g. IllustrisTNG 'SubhaloSFR' "
            "or 'sfr' in M_sun/yr). Derived from instantaneous gas cell densities, temperatures, "
            "and cooling timescales in the simulation hydrodynamics."
        ),
        "model_derived_sfh": (
            "Continuous or binned star formation rate curve psi(t) parameterized over cosmic time "
            "and integrated across the stellar population age grid. Normalized such that the integral "
            "of psi(t) dt over the galaxy's lifetime equals the total formed stellar mass M_formed."
        ),
        "formed_vs_surviving_mass": (
            "M_formed is the cumulative stellar mass created by star formation. Due to stellar evolution, "
            "supernovae, and mass loss via stellar winds, the surviving stellar mass at lookback time 0 "
            "is M_surviving(t) = M_formed * f_surv(t), where f_surv ~ 0.55-0.70 for standard Chabrier/Kroupa IMFs."
        ),
    }


def chabrier_surviving_mass_fraction(age_yr: np.ndarray | float) -> np.ndarray | float:
    """
    Approximation of the surviving stellar mass fraction f_surv(t) = M_alive(t) / M_formed
    for a Chabrier (2003) IMF as a function of stellar population age in years.
    Based on standard stellar evolution remnants (Leitner & Kravtsov 2011, Maraston 2005):
      f_surv(t) = 1.0 - 0.046 * ln(1 + t / 2.76e5 yr).
    """
    age = np.asarray(age_yr, dtype=np.float64)
    # Leitner & Kravtsov (2011) continuous recycling fraction
    loss_fraction = 0.046 * np.log(1.0 + np.maximum(0.0, age) / 2.76e5)
    f_surv = 1.0 - loss_fraction
    return np.clip(f_surv, 0.45, 1.0)


def compute_delayed_tau_sfh(
    mass_formed_msun: np.ndarray,
    t_onset_gyr: np.ndarray,
    tau_gyr: np.ndarray,
    ages_yr: np.ndarray,
    mets_z: np.ndarray,
    log_z_centre: np.ndarray | None = None,
    z_dispersion: float = 0.3,
) -> np.ndarray:
    """
    Compute delayed-tau star formation history matrix with exact mass conservation.

    SFH model: psi(t) ~ t * exp(-t / tau), where t = t_onset - age is time since formation onset.
    Integrated over each age bin dt to ensure exact mass normalization:
      sum_{i} psi_i * dt_i = M_formed.

    Args:
        mass_formed_msun: 1D array of formed stellar masses in M_sun of shape (N_gal,).
        t_onset_gyr: 1D array of formation onset times in Gyr of shape (N_gal,).
        tau_gyr: 1D array of e-folding timescales in Gyr of shape (N_gal,).
        ages_yr: 1D strictly ascending stellar age grid in years of shape (N_age,).
        mets_z: 1D strictly ascending metallicity grid in mass fraction Z of shape (N_met,).
        log_z_centre: Optional 1D array of log10(Z) centers of shape (N_gal,).
        z_dispersion: Gaussian metallicity dispersion in dex.

    Returns:
        2D array of shape (N_gal, N_age * N_met) representing mass formed in each age-met bin.
    """
    n_gal = len(mass_formed_msun)
    n_age = len(ages_yr)
    n_met = len(mets_z)

    # Compute logarithmic mid-point age bin widths dt
    edges = np.sqrt(ages_yr[1:] * ages_yr[:-1])
    edges = np.concatenate([[ages_yr[0] ** 2 / edges[0]], edges, [ages_yr[-1] ** 2 / edges[-1]]])
    dt = np.diff(edges)  # years

    # Time since formation onset for each galaxy and age bin
    t_on_yr = t_onset_gyr[:, None] * 1e9
    tau_yr = tau_gyr[:, None] * 1e9
    t_form_yr = np.clip(t_on_yr - ages_yr[None, :], 0.0, None)  # shape: (n_gal, n_age)

    # Delayed-tau rate: psi(t) = (t / tau^2) * exp(-t / tau)
    # Using relative weight psi * dt normalized across ages
    sfr_relative = (t_form_yr / np.maximum(tau_yr, 1e6)) * np.exp(-t_form_yr / np.maximum(tau_yr, 1e6))
    weight_age = sfr_relative * dt[None, :] + 1e-30
    weight_age /= weight_age.sum(axis=1, keepdims=True)

    # Metallicity distribution: Gaussian in log10(Z)
    if log_z_centre is not None:
        lz_grid = np.log10(mets_z)[None, :]
        z_c = log_z_centre[:, None]
        weight_met = np.exp(-0.5 * ((lz_grid - z_c) / z_dispersion) ** 2) + 1e-30
        weight_met /= weight_met.sum(axis=1, keepdims=True)
    else:
        # Uniform across metallicities if no center provided
        weight_met = np.full((n_gal, n_met), 1.0 / n_met, dtype=np.float64)

    # Contract mass * age_weight * met_weight -> shape (n_gal, n_age, n_met)
    mass_f64 = np.asarray(mass_formed_msun, dtype=np.float64)
    sfh_3d = mass_f64[:, None, None] * weight_age[:, :, None] * weight_met[:, None, :]

    # Return age-major flattened matrix (n_gal, n_age * n_met)
    return sfh_3d.reshape(n_gal, -1).astype(np.float32)


def compute_constant_sfh(
    sfr_msun_per_yr: np.ndarray,
    duration_gyr: np.ndarray,
    ages_yr: np.ndarray,
    mets_z: np.ndarray,
) -> np.ndarray:
    """
    Compute constant star formation history over a finite duration: psi(t) = const for age < duration.
    """
    n_gal = len(sfr_msun_per_yr)
    edges = np.sqrt(ages_yr[1:] * ages_yr[:-1])
    edges = np.concatenate([[ages_yr[0] ** 2 / edges[0]], edges, [ages_yr[-1] ** 2 / edges[-1]]])
    dt = np.diff(edges)

    dur_yr = duration_gyr[:, None] * 1e9
    mask = ages_yr[None, :] <= dur_yr
    weight_age = mask.astype(np.float64) * dt[None, :]
    total_dt = np.maximum(weight_age.sum(axis=1, keepdims=True), 1.0)
    weight_age /= total_dt

    total_mass = sfr_msun_per_yr[:, None] * dur_yr
    n_met = len(mets_z)
    sfh_3d = (total_mass * weight_age)[:, :, None] * (1.0 / n_met)
    return sfh_3d.reshape(n_gal, -1).astype(np.float32)
