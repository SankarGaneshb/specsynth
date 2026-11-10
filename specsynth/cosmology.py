from __future__ import annotations

import numpy as np


class FlatLambdaCDM:
    """
    Lightweight, fast Flat Lambda-CDM cosmological calculator using pure NumPy.
    Matches Planck / standard cosmology parameters.
    """

    def __init__(self, H0: float = 70.0, Om0: float = 0.3):
        """
        Args:
            H0: Hubble constant in km/s/Mpc (default: 70.0).
            Om0: Matter density parameter at z=0 (default: 0.3).
        """
        self.H0 = float(H0)
        self.Om0 = float(Om0)
        self.Ode0 = 1.0 - self.Om0
        self.c_km_s = 299792.458  # Speed of light in km/s
        self.Mpc_to_cm = 3.08567758128e24

    def E(self, z: np.ndarray | float) -> np.ndarray:
        """Dimensionless Hubble parameter: E(z) = H(z) / H0."""
        z = np.asarray(z)
        return np.sqrt(self.Om0 * (1.0 + z) ** 3 + self.Ode0)

    def comoving_distance(self, z: float, n_steps: int = 100) -> float:
        r"""
        Line-of-sight comoving distance in Mpc.
        D_C(z) = (c / H0) * \int_0^z dz' / E(z')
        """
        if z <= 0.0:
            return 0.0

        # Gauss-Legendre quadrature for high precision
        nodes, weights = np.polynomial.legendre.leggauss(n_steps)
        # Transform [-1, 1] to [0, z]
        z_sample = 0.5 * z * (nodes + 1.0)
        integrand = 1.0 / self.E(z_sample)
        integral = 0.5 * z * np.sum(weights * integrand)
        return (self.c_km_s / self.H0) * integral

    def luminosity_distance(self, z: float) -> float:
        """
        Luminosity distance in Mpc.
        D_L(z) = (1 + z) * D_C(z)
        """
        if z <= 0.0:
            return 0.0
        return (1.0 + z) * self.comoving_distance(z)

    def luminosity_distance_cm(self, z: float) -> float:
        """Luminosity distance in cm."""
        return self.luminosity_distance(z) * self.Mpc_to_cm


# Default benchmark cosmology (Planck 2018 compatible)
DEFAULT_COSMOLOGY = FlatLambdaCDM(H0=70.0, Om0=0.3)


def redshift_flux(
    wave_rest: np.ndarray,
    flux_rest: np.ndarray,
    z: float,
    cosmo: FlatLambdaCDM | None = None,
    distance_dimming: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Cosmologically redshift a rest-frame spectrum.

    Args:
        wave_rest: Rest-frame wavelength array in Angstroms.
        flux_rest: Rest-frame luminosity density L_lambda (e.g. erg/s/A or L_sun/A).
        z: Cosmological redshift.
        cosmo: FlatLambdaCDM instance (defaults to H0=70, Om0=0.3).
        distance_dimming: If True, scale flux by 1 / (4 * pi * D_L^2) in cm^2.
                         If False, only apply (1 / (1 + z)) bandpass compression.

    Returns:
        wave_obs: Observed-frame wavelength array in Angstroms: lambda_obs = lambda_rest * (1 + z).
        flux_obs: Observed-frame flux density F_lambda.
    """
    if z <= 0.0:
        return np.asarray(wave_rest), np.asarray(flux_rest)

    cosmo = cosmo or DEFAULT_COSMOLOGY
    wave_obs = np.asarray(wave_rest) * (1.0 + z)

    # Spectral flux density transformation:
    # F_lambda(lambda_obs) = (1 / (1 + z)) * L_lambda(lambda_rest) / (4 * pi * D_L^2)
    dimming_factor = 1.0 / (1.0 + z)
    if distance_dimming:
        d_L_cm = cosmo.luminosity_distance_cm(z)
        dimming_factor /= 4.0 * np.pi * (d_L_cm**2)

    flux_obs = np.asarray(flux_rest, dtype=np.float32) * dimming_factor
    return wave_obs, flux_obs
