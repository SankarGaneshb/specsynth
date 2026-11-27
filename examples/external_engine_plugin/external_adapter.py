"""
External Adapter for CB2026 Simulated Engine.
=============================================
Demonstrates Pillar 1: "Zero-Core-Modification Pluggability".
An astrophysicist authors this adapter in their own package, repo, or script,
and registers it at runtime with `register_adapter`.
"""

from __future__ import annotations

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData
from specsynth.adapters import register_adapter
from cb2026_engine import CB2026Engine


class CB2026Adapter(BaseAdapter):
    """
    Specsynth-compliant adapter wrapping the third-party CB2026 SPS engine.
    Converts native log-age and 3D grid layout into Specsynth's 2D age-major SSPData.
    """

    def __init__(
        self,
        imf: str = "chabrier",
        isochrone: str = "parsec_v1.2",
        n_wave: int = 1200,
        **kwargs,
    ):
        super().__init__()
        self.engine = CB2026Engine(imf=imf, isochrone=isochrone)
        self.n_wave = n_wave
        self.imf = imf
        self.isochrone = isochrone

    def load(self, wave_resample: np.ndarray | None = None) -> SSPData:
        """
        Execute CB2026 engine computation, conform coordinates, and return SSPData.
        """
        # Standard grid of ages (10 Myr to 10 Gyr) and metallicities (Z = 0.001 to 0.03)
        log_ages = np.linspace(7.0, 10.0, 16)
        metallicities = np.array([0.001, 0.004, 0.008, 0.02, 0.03], dtype=np.float64)

        raw = self.engine.compute_ssp_grid(
            log_ages=log_ages,
            metallicities_z=metallicities,
            lambda_min=912.0,
            lambda_max=30000.0,
            n_points=self.n_wave,
        )

        # Convert log10(age/yr) to linear age in years
        linear_ages = 10.0 ** raw["log10_age_yr"]
        wave = raw["rest_wavelength_angstrom"]
        flux_3d = raw["flux_flambda_lsun_per_angstrom"]  # (n_age, n_met, n_wave)

        # Flatten (n_age, n_met, n_wave) into 2D (n_age * n_met, n_wave) age-major
        n_age, n_met, n_w = flux_3d.shape
        ssp_2d = np.ascontiguousarray(
            flux_3d.reshape((n_age * n_met, n_w)),
            dtype=np.float32,
        )

        data = SSPData(
            ages=linear_ages,
            mets=metallicities,
            wave=wave,
            ssp=ssp_2d,
        )

        if wave_resample is not None:
            return data.resample_wavelength(wave_resample)

        return data

    def validate(self) -> bool:
        """Validate internal engine state and parameters."""
        return self.imf in ["chabrier", "salpeter", "kroupa"]

    def get_capabilities(self) -> dict:
        """Return engine metadata and parameter boundaries."""
        return {
            "name": "cb2026_external",
            "full_name": "Illustrative Demo Engine: Charlot & Bruzual 2026 Mock (Contract Fixture)",
            "engine_source": "Procedural Mock (CB2026 Fixture)",
            "provenance_badge": "Illustrative Demo Engine: CB2026 Mock (Contract Fixture)",
            "is_mock": True,
            "data_mode": "illustrative_demo",
            "scientific_validation": False,
            "imf": self.imf,
            "isochrone": self.isochrone,
            "resolution": "R~2000-5000",
            "wavelength_range_aa": [912.0, 30000.0],
            "age_range_yr": [1e7, 1e10],
            "metallicity_range": [0.001, 0.03],
            "zero_core_mod": True,
        }


# Dynamic self-registration into Specsynth runtime registry upon import
register_adapter(
    name="cb2026",
    adapter_cls=CB2026Adapter,
    aliases=["cb2026_external", "cb26"],
    overwrite=True,
)
