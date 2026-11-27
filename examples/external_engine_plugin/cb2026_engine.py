"""
Simulated Third-Party Astrophysics Engine (Charlot & Bruzual 2026 Preview - CB2026).
==================================================================================
TRUTH-IN-LABELING NOTICE:
This module is an ILLUSTRATIVE MOCK FIXTURE designed strictly for adapter interface,
coordinate translation, and schema contract testing (Pillar 1). It is NOT an authentic
astrophysical engine and MUST NOT be presented as external scientific validation.
"""

from __future__ import annotations

import numpy as np


class CB2026Engine:
    """
    Simulated external SPS engine producing procedural stellar population grids
    for adapter wiring and schema conformance testing only.

    Attributes:
        is_mock: True (strictly a synthetic test fixture).
        data_mode: "illustrative_demo"
        engine_type: "mock_contract_fixture"
    """

    is_mock: bool = True
    data_mode: str = "illustrative_demo"
    engine_type: str = "mock_contract_fixture"

    def __init__(self, imf: str = "chabrier", isochrone: str = "parsec_v1.2"):
        self.imf = imf
        self.isochrone = isochrone
        self.is_mock = True
        self.data_mode = "illustrative_demo"

    def compute_ssp_grid(
        self,
        log_ages: np.ndarray,
        metallicities_z: np.ndarray,
        lambda_min: float = 912.0,
        lambda_max: float = 30000.0,
        n_points: int = 1500,
    ) -> dict[str, np.ndarray]:
        """
        Simulate computing a multi-dimensional SSP grid.

        Returns raw dictionary with engine-specific keys and units:
          - 'rest_wavelength_angstrom': 1D array of wavelengths [Å]
          - 'log10_age_yr': 1D array of log10(age / yr)
          - 'metallicity_z': 1D array of metal mass fractions Z
          - 'flux_flambda_lsun_per_angstrom': 3D array (n_age, n_met, n_wave) [L_sun / Å / M_sun]
        """
        wave = np.linspace(lambda_min, lambda_max, n_points, dtype=np.float64)
        n_age = len(log_ages)
        n_met = len(metallicities_z)
        n_wave = len(wave)

        flux_grid = np.zeros((n_age, n_met, n_wave), dtype=np.float32)

        for i, log_t in enumerate(log_ages):
            t_yr = 10.0 ** log_t
            # Younger populations have higher effective temperature (peak in UV)
            t_eff = max(3000.0, 50000.0 * (1e6 / t_yr) ** 0.25)

            for j, z in enumerate(metallicities_z):
                # Planck-like thermal continuum with Balmer break and metallic line absorption
                w_m = wave * 1e-10
                h = 6.626e-34
                c = 2.998e8
                k = 1.381e-23
                exponent = np.clip(h * c / (w_m * k * t_eff), 0.0, 80.0)
                planck_shape = (2.0 * h * c**2 / (w_m**5)) / (np.exp(exponent) - 1.0 + 1e-30)

                # Scale to ~solar luminosity units
                continuum = planck_shape / (np.max(planck_shape) + 1e-30) * 1e-2

                # Add Balmer break (drop below 3646 Å for older populations)
                balmer_drop = 1.0 - (0.6 * min(1.0, max(0.0, (t_yr - 1e7) / 1e9)))
                is_uv = wave < 3646.0
                continuum[is_uv] *= balmer_drop

                # Metallicity absorption in optical (stronger with higher Z)
                optical_metals = (wave > 4000.0) & (wave < 5500.0)
                continuum[optical_metals] *= (1.0 - 0.2 * (z / 0.02))

                # Young stars dominate luminosity per unit stellar mass
                lum_norm = (1e9 / (t_yr + 1e5)) ** 0.7
                flux_grid[i, j, :] = np.maximum(continuum * lum_norm, 0.0).astype(np.float32)

        return {
            "rest_wavelength_angstrom": wave,
            "log10_age_yr": np.asarray(log_ages, dtype=np.float64),
            "metallicity_z": np.asarray(metallicities_z, dtype=np.float64),
            "flux_flambda_lsun_per_angstrom": flux_grid,
        }
