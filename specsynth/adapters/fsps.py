from __future__ import annotations

from typing import Sequence

import numpy as np

from specsynth.adapters.base import BaseAdapter, SSPData


class FSPSAdapter(BaseAdapter):
    """
    Adapter for generating stellar population synthesis libraries dynamically
    using python-fsps (Flexible Stellar Population Synthesis).
    """

    def __init__(
        self,
        imf_type: int | str = "chabrier",
        isochrone: str = "mist",
        ages: Sequence[float] | None = None,
        metallicities: Sequence[float] | None = None,
        add_nebular_emission: bool = False,
    ):
        """
        Args:
            imf_type: IMF choice (0=Salpeter, 1=Chabrier, 2=Kroupa, or string name).
            isochrone: Isochrone set (e.g., 'mist', 'padova').
            ages: Sequence of ages in years (defaults to 100 log-spaced points from 1 Myr to 13.5 Gyr).
            metallicities: Sequence of absolute metallicities Z (defaults to FSPS standard grid).
            add_nebular_emission: Whether to include gas nebular emission lines.
        """
        self.imf_type = imf_type
        self.isochrone = isochrone
        self.ages = (
            np.asarray(ages, dtype=np.float64)
            if ages is not None
            else np.logspace(6.0, np.log10(1.35e10), 100)
        )
        self.metallicities = (
            np.asarray(metallicities, dtype=np.float64)
            if metallicities is not None
            else None
        )
        self.add_nebular_emission = add_nebular_emission

    def load(self) -> SSPData:
        try:
            import fsps
        except ImportError as e:
            raise ImportError(
                "python-fsps is required to run the FSPS adapter. Install it with: "
                "conda install -c conda-forge fsps python-fsps or pip install fsps"
            ) from e

        imf_map = {"salpeter": 0, "chabrier": 1, "kroupa": 2}
        imf_code = (
            imf_map.get(str(self.imf_type).lower(), self.imf_type)
            if isinstance(self.imf_type, str)
            else self.imf_type
        )

        sp = fsps.StellarPopulation(
            compute_vega_mags=False,
            zcontinuous=1,
            imf_type=imf_code,
            add_nebular_emission=self.add_nebular_emission,
        )

        # Retrieve available metallicity grid if not provided
        if self.metallicities is None:
            # Standard solar metallicity Z_sun ~ 0.019 (or 0.014 depending on isochrone)
            z_sun = 0.019
            log_z = sp.zlegend
            mets = (10.0**log_z) * z_sun
        else:
            mets = np.asarray(self.metallicities, dtype=np.float64)

        wave = sp.wavelengths.astype(np.float64)
        n_age = len(self.ages)
        n_met = len(mets)
        n_wave = len(wave)

        grid_3d = np.empty((n_age, n_met, n_wave), dtype=np.float32)

        # Populate grid: FSPS expects log(Z / Z_sun) for zcontinuous=1
        z_sun = 0.019
        for j, z in enumerate(mets):
            log_z_ratio = np.log10(max(z, 1e-6) / z_sun)
            sp.params["logzsol"] = log_z_ratio
            for i, age_yr in enumerate(self.ages):
                # FSPS tage parameter is in Gyr
                _, flux = sp.get_spectrum(tage=age_yr / 1e9, peraa=True)
                grid_3d[i, j, :] = flux

        return SSPData.from_3d_grid(
            ages=self.ages,
            mets=mets,
            wave=wave,
            grid_3d=grid_3d,
            metadata={
                "model": "FSPS",
                "imf": str(self.imf_type),
                "isochrone": self.isochrone,
                "nebular": self.add_nebular_emission,
            },
        )
