"""
Versioned Synthetic Photometry and SED Contract (v1.0.0).
Defines standard schema, physical units, and provenance standards for synthetic observations.
Enforces P0.2 and P1/P5 data foundations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np


@dataclass
class PhotometryPointContract:
    """
    Standard schema for a single telescope filter measurement.

    Attributes:
        filter_name: Standardized filter identifier (e.g. 'jwst_nircam_f200w').
        pivot_wavelength_angstrom: Pivot wavelength lambda_pivot in Angstroms.
        flux_density_ujy: Observed flux density in microJanskys (uJy = 1e-29 erg/s/cm^2/Hz).
        ab_magnitude: Monochromatic AB magnitude (-2.5 * log10(F_nu / 3631 Jy)).
        ab_mag_error: Optional 1-sigma magnitude error from instrumental noise model.
        snr: Optional signal-to-noise ratio.
        transmission_sha256: Cryptographic SHA-256 hash of the filter throughput curve.
    """
    filter_name: str
    pivot_wavelength_angstrom: float
    flux_density_ujy: float
    ab_magnitude: float
    ab_mag_error: Optional[float] = None
    snr: Optional[float] = None
    transmission_sha256: Optional[str] = None

    def __post_init__(self) -> None:
        if self.pivot_wavelength_angstrom <= 0:
            raise ValueError(f"pivot_wavelength_angstrom must be positive, got {self.pivot_wavelength_angstrom}")
        if self.flux_density_ujy < 0:
            raise ValueError(f"flux_density_ujy cannot be negative, got {self.flux_density_ujy}")


@dataclass
class SyntheticObservationContract:
    """
    Complete synthetic observation bundle containing SED, photometry, and full provenance.

    Attributes:
        galaxy_id: Target galaxy identifier.
        redshift: Cosmological redshift z.
        cosmology: Dict specifying cosmological parameters (H0, Om0, Ol0).
        dust_model: Name and parameters of dust attenuation (e.g. 'charlot_fall_2000').
        igm_model: Name of IGM attenuation recipe (e.g. 'madau_1995').
        ssp_model: Name and version of SSP library used (e.g. 'fsps_v3.2_mist').
        photometry: List of filter measurements.
        sed_wave_angstrom: 1D array of observed wavelengths in Angstroms.
        sed_flux_obs_cgs: 1D array of observed-frame flux densities F_lambda in erg/s/cm^2/Angstrom.
        sed_flux_rest_lsun_angstrom: Optional 1D array of rest-frame luminosities L_lambda in L_sun/Angstrom.
        version: Contract version string.
        provenance: Complete provenance manifest containing engine version, execution runtime, and git commit.
    """
    galaxy_id: str
    redshift: float
    cosmology: dict[str, float]
    dust_model: str
    igm_model: str
    ssp_model: str
    photometry: list[PhotometryPointContract]
    sed_wave_angstrom: np.ndarray
    sed_flux_obs_cgs: np.ndarray
    sed_flux_rest_lsun_angstrom: Optional[np.ndarray] = None
    version: str = "1.0.0"
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.sed_wave_angstrom = np.asarray(self.sed_wave_angstrom, dtype=np.float64)
        self.sed_flux_obs_cgs = np.asarray(self.sed_flux_obs_cgs, dtype=np.float32)
        if self.sed_flux_rest_lsun_angstrom is not None:
            self.sed_flux_rest_lsun_angstrom = np.asarray(self.sed_flux_rest_lsun_angstrom, dtype=np.float32)

        self.validate()

    def validate(self) -> None:
        """Validate dimensions, non-negativity, and numerical integrity."""
        if not self.galaxy_id:
            raise ValueError("galaxy_id cannot be empty")
        if self.redshift < 0:
            raise ValueError(f"redshift must be non-negative, got {self.redshift}")
        if len(self.sed_wave_angstrom) != len(self.sed_flux_obs_cgs):
            raise ValueError(
                f"SED wavelength ({len(self.sed_wave_angstrom)}) and flux ({len(self.sed_flux_obs_cgs)}) lengths do not match"
            )

        if not np.all(np.isfinite(self.sed_wave_angstrom)):
            raise ValueError("sed_wave_angstrom contains non-finite values")
        if not np.all(np.isfinite(self.sed_flux_obs_cgs)):
            raise ValueError("sed_flux_obs_cgs contains non-finite values")

        if np.any(self.sed_flux_obs_cgs < 0):
            raise ValueError("sed_flux_obs_cgs contains negative flux values")

    def to_dict(self) -> dict[str, Any]:
        """Convert observation contract to serializable summary dictionary."""
        return {
            "version": self.version,
            "galaxy_id": self.galaxy_id,
            "redshift": self.redshift,
            "cosmology": self.cosmology,
            "dust_model": self.dust_model,
            "igm_model": self.igm_model,
            "ssp_model": self.ssp_model,
            "photometry": [
                {
                    "filter_name": p.filter_name,
                    "pivot_wavelength_angstrom": p.pivot_wavelength_angstrom,
                    "flux_density_ujy": p.flux_density_ujy,
                    "ab_magnitude": p.ab_magnitude,
                    "ab_mag_error": p.ab_mag_error,
                    "snr": p.snr,
                    "transmission_sha256": p.transmission_sha256,
                }
                for p in self.photometry
            ],
            "n_sed_points": len(self.sed_wave_angstrom),
            "sed_wave_range_angstrom": [float(self.sed_wave_angstrom[0]), float(self.sed_wave_angstrom[-1])],
            "provenance": self.provenance,
        }
