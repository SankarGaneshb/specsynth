from __future__ import annotations

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData


def _integrate(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Trapezoidal integration compatible with NumPy 1.x and 2.x."""
    fn = getattr(np, "trapezoid", getattr(np, "trapz", None))
    return fn(y, x)


def planck(wave_A: np.ndarray, T: float) -> np.ndarray:
    """Planck function blackbody flux in Angstroms."""
    lam = wave_A * 1e-10
    x = np.clip(1.4388e-2 / (lam * T), 1e-6, 700)
    return 1.0 / (lam**5 * np.expm1(x))


def build_toy_ssp(n_age: int, n_met: int, n_wave: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Physically-flavoured *toy* SSPs: blackbody whose temperature falls with age,
    luminosity per unit mass ~ age^-0.8, a 4000 A break that strengthens with
    age, mild metallicity reddening. Good for exercising the pipeline - NOT for
    science. Layout is age-major: k = i_age * n_met + i_met.
    """
    ages = np.logspace(6.0, np.log10(1.3e10), n_age)  # yr
    mets = np.logspace(-4, np.log10(0.03), n_met)  # Z (absolute)
    wave = np.logspace(np.log10(1000.0), np.log10(25000.0), n_wave)  # Angstrom
    ssp = np.empty((n_age * n_met, n_wave), dtype=np.float32)
    for i, t in enumerate(ages):
        for j, z in enumerate(mets):
            teff = 45000.0 * (t / 1e6) ** -0.18 * (1.0 - 0.08 * np.log10(z / 0.02))
            f = planck(wave, max(teff, 3200.0))
            f /= _integrate(f, wave)
            f *= (t / 1e6) ** -0.8  # L per Msun formed (arbitrary units)
            brk = 1.0 - 0.55 * np.clip(np.log10(t / 1e8) / 2.0, 0, 1)
            f = np.where(wave < 4000.0, f * brk, f)
            ssp[i * n_met + j] = f
    return ages, mets, wave, ssp


class ToyAdapter(BaseAdapter):
    """Adapter for generating synthetic toy SSP grids."""

    def __init__(self, n_age: int = 60, n_met: int = 6, n_wave: int = 4000):
        self.n_age = n_age
        self.n_met = n_met
        self.n_wave = n_wave

    def load(self) -> SSPData:
        ages, mets, wave, ssp = build_toy_ssp(self.n_age, self.n_met, self.n_wave)
        return SSPData(
            ages=ages,
            mets=mets,
            wave=wave,
            ssp=ssp,
            metadata={
                "model": "toy",
                "description": "Synthetic toy SSP model for benchmarking and testing",
            },
        )
