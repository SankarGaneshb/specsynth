from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

# Speed of light in Angstrom / second
C_AA_S = 2.99792458e18


@dataclass
class FilterCurve:
    """
    Astronomical filter transmission curve.

    Attributes:
        name: Filter identifier (e.g., 'jwst_f200w', 'sdss_r', 'lsst_g').
        wave: Wavelength grid in Angstroms (1D array, strictly ascending).
        transmission: Normalized transmission response T(lambda) in [0, 1].
    """
    name: str
    wave: np.ndarray
    transmission: np.ndarray

    def __post_init__(self):
        self.wave = np.asarray(self.wave, dtype=np.float64)
        self.transmission = np.asarray(self.transmission, dtype=np.float64)
        if len(self.wave) != len(self.transmission):
            raise ValueError("wave and transmission arrays must have the same length")
        if np.any(np.diff(self.wave) <= 0):
            raise ValueError("Filter wave grid must be strictly monotonically increasing")
        # Ensure non-negative transmission
        self.transmission = np.clip(self.transmission, 0.0, None)

    @property
    def pivot_wavelength(self) -> float:
        r"""
        Filter pivot wavelength in Angstroms:
        lambda_piv = sqrt( \int T(lam) lam dlam / \int [T(lam) / lam] dlam )
        """
        dl = np.gradient(self.wave)
        num = np.sum(self.transmission * self.wave * dl)
        denom = np.sum((self.transmission / np.maximum(self.wave, 1e-10)) * dl)
        if denom <= 0:
            return float(np.mean(self.wave))
        return float(np.sqrt(num / denom))

    @property
    def effective_wavelength(self) -> float:
        r"""
        Mean transmission wavelength in Angstroms:
        lambda_eff = \int lam T(lam) dlam / \int T(lam) dlam
        """
        dl = np.gradient(self.wave)
        denom = np.sum(self.transmission * dl)
        if denom <= 0:
            return float(np.mean(self.wave))
        return float(np.sum(self.wave * self.transmission * dl) / denom)

    def resample(self, target_wave: np.ndarray) -> np.ndarray:
        """Interpolate transmission curve onto target wavelength grid."""
        return np.interp(target_wave, self.wave, self.transmission, left=0.0, right=0.0)


# --------------------------------------------------------------------------
# Built-in Standard Filter Profiles (Analytical Flat-Top with Gaussian Roll-off)
# --------------------------------------------------------------------------
def _make_bandpass(name: str, center: float, fwhm: float, n_points: int = 500) -> FilterCurve:
    """Generate realistic transmission profile with flat top and smooth edges."""
    half_w = 0.5 * fwhm
    wave = np.linspace(center - 2.0 * fwhm, center + 2.0 * fwhm, n_points)
    # Super-Gaussian profile for realistic steep band edges: exp(-(dx / w)^8)
    dx = (wave - center) / (half_w * 1.05)
    trans = np.exp(-(dx**8))
    # Normalize peak to 0.9 (typical optical/NIR throughput)
    trans = trans * 0.9
    return FilterCurve(name=name, wave=wave, transmission=trans)


# Filter definitions: (center in Angstroms, FWHM in Angstroms)
STANDARD_FILTER_SPECS = {
    # JWST NIRCam Wide Filters
    "jwst_f090w": (9000.0, 2000.0),
    "jwst_f115w": (11500.0, 2300.0),
    "jwst_f150w": (15000.0, 3000.0),
    "jwst_f200w": (20000.0, 4600.0),
    "jwst_f277w": (27700.0, 6800.0),
    "jwst_f356w": (35600.0, 7800.0),
    "jwst_f444w": (44400.0, 10200.0),
    # HST ACS & WFC3
    "hst_f435w": (4328.0, 700.0),
    "hst_f606w": (5921.0, 1570.0),
    "hst_f814w": (8057.0, 1530.0),
    "hst_f160w": (15369.0, 2680.0),
    # Rubin / LSST
    "rubin_u": (3671.0, 560.0),
    "rubin_g": (4827.0, 1400.0),
    "rubin_r": (6223.0, 1400.0),
    "rubin_i": (7546.0, 1400.0),
    "rubin_z": (8691.0, 1000.0),
    "rubin_y": (9712.0, 1000.0),
    # SDSS
    "sdss_u": (3557.0, 560.0),
    "sdss_g": (4825.0, 1380.0),
    "sdss_r": (6261.0, 1370.0),
    "sdss_i": (7672.0, 1530.0),
    "sdss_z": (9097.0, 1370.0),
    # Euclid
    "euclid_vis": (7000.0, 3500.0),
    "euclid_y": (10850.0, 2600.0),
    "euclid_j": (13750.0, 4000.0),
    "euclid_h": (17720.0, 5000.0),
}

FILTER_SETS = {
    "jwst_nircam": ["jwst_f090w", "jwst_f115w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"],
    "hst": ["hst_f435w", "hst_f606w", "hst_f814w", "hst_f160w"],
    "rubin": ["rubin_u", "rubin_g", "rubin_r", "rubin_i", "rubin_z", "rubin_y"],
    "sdss": ["sdss_u", "sdss_g", "sdss_r", "sdss_i", "sdss_z"],
    "euclid": ["euclid_vis", "euclid_y", "euclid_j", "euclid_h"],
}


def get_filter(name: str) -> FilterCurve:
    """Retrieve or load a FilterCurve by standard name or filepath."""
    name_clean = name.strip().lower()
    if name_clean in STANDARD_FILTER_SPECS:
        c, w = STANDARD_FILTER_SPECS[name_clean]
        return _make_bandpass(name_clean, c, w)

    # Check if name is a filepath
    path = Path(name)
    if path.is_file():
        data = np.loadtxt(path)
        return FilterCurve(name=path.stem, wave=data[:, 0], transmission=data[:, 1])

    raise ValueError(
        f"Unknown filter '{name}'. Built-ins: {list(STANDARD_FILTER_SPECS.keys())} "
        f"or filter sets: {list(FILTER_SETS.keys())}"
    )


def resolve_filter_names(names: Sequence[str] | str) -> list[str]:
    """Resolve a comma-separated list of filter names or set names."""
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]

    resolved = []
    for item in names:
        key = item.lower()
        if key in FILTER_SETS:
            resolved.extend(FILTER_SETS[key])
        else:
            resolved.append(key)
    return resolved


def build_filter_projection_matrix(
    wave: np.ndarray,
    filter_names: Sequence[str] | str,
) -> tuple[np.ndarray, list[str], list[float]]:
    r"""
    Build the linear projection matrix M of shape (n_wave, n_filters) to project
    spectra S (N x n_wave) directly into photon-counting band fluxes:
        Photometry = S @ M

    Photon-counting flux definition:
        F_band = \int S(lam) * T(lam) * lam dlam / \int T(lam) * lam dlam

    Returns:
        matrix: (n_wave, n_filters) float32 projection matrix
        names: list of filter names
        pivots: list of pivot wavelengths in Angstroms
    """
    resolved_names = resolve_filter_names(filter_names)
    wave = np.asarray(wave, dtype=np.float64)
    dl = np.gradient(wave)

    columns = []
    pivots = []
    for fname in resolved_names:
        flt = get_filter(fname)
        trans = flt.resample(wave)  # Resample onto target wave
        weight = trans * wave * dl
        norm = np.sum(weight)
        if norm <= 0:
            norm = 1.0  # Avoid division by zero for out-of-range filters
        col = (weight / norm).astype(np.float32)
        columns.append(col)
        pivots.append(flt.pivot_wavelength)

    matrix = np.stack(columns, axis=1)
    return matrix, resolved_names, pivots


def flux_to_ab_mag(flux_density_cgs: np.ndarray) -> np.ndarray:
    """
    Convert flux density in erg / s / cm^2 / Hz (F_nu) to AB magnitudes:
    m_AB = -2.5 * log10(F_nu) - 48.60
    """
    flux_safe = np.maximum(flux_density_cgs, 1e-35)
    return -2.5 * np.log10(flux_safe) - 48.60


def f_lambda_to_f_nu(f_lambda: np.ndarray, pivot_wave_A: float | np.ndarray) -> np.ndarray:
    """
    Convert F_lambda (in erg / s / cm^2 / A) to F_nu (in erg / s / cm^2 / Hz):
    F_nu = F_lambda * (lambda_pivot^2 / c)
    """
    pivot = np.asarray(pivot_wave_A, dtype=np.float64)
    factor = (pivot**2) / C_AA_S
    return f_lambda * factor
