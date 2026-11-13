from __future__ import annotations

import numpy as np

# Physical astronomical constants (IAU 2015 Resolution B3)
L_SUN_ERG_S = 3.828e33          # Nominal solar luminosity in erg/s
PC_TO_CM = 3.08567758128e18      # Parsec in cm
MPC_TO_CM = 3.08567758128e24     # Megaparsec in cm
C_KM_S = 299792.458              # Speed of light in km/s


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
        self.c_km_s = C_KM_S
        self.Mpc_to_cm = MPC_TO_CM

    def E(self, z: np.ndarray | float) -> np.ndarray:
        """Dimensionless Hubble parameter: E(z) = H(z) / H0."""
        z = np.asarray(z)
        return np.sqrt(self.Om0 * (1.0 + z) ** 3 + self.Ode0)

    def comoving_distance(self, z: float | np.ndarray, n_steps: int = 100) -> float | np.ndarray:
        r"""
        Line-of-sight comoving distance in Mpc.
        D_C(z) = (c / H0) * \int_0^z dz' / E(z')
        Supports scalar float or 1D array of redshifts.
        """
        z_arr = np.atleast_1d(np.asarray(z, dtype=np.float64))
        is_scalar = np.isscalar(z) or (isinstance(z, np.ndarray) and z.ndim == 0)

        # Gauss-Legendre quadrature for high precision
        nodes, weights = np.polynomial.legendre.leggauss(n_steps)
        # Transform [-1, 1] to [0, z]
        z_sample = 0.5 * z_arr[:, None] * (nodes[None, :] + 1.0)
        integrand = 1.0 / self.E(z_sample)
        integral = 0.5 * z_arr * np.sum(weights[None, :] * integrand, axis=1)
        dc = (self.c_km_s / self.H0) * integral
        dc = np.where(z_arr <= 0.0, 0.0, dc)
        return float(dc[0]) if is_scalar else dc

    def luminosity_distance(self, z: float | np.ndarray) -> float | np.ndarray:
        """
        Luminosity distance in Mpc.
        D_L(z) = (1 + z) * D_C(z)
        """
        z_arr = np.asarray(z)
        return (1.0 + z_arr) * self.comoving_distance(z)

    def luminosity_distance_cm(self, z: float | np.ndarray) -> float | np.ndarray:
        """Luminosity distance in cm."""
        return self.luminosity_distance(z) * self.Mpc_to_cm


# Default benchmark cosmology (Planck 2018 compatible)
DEFAULT_COSMOLOGY = FlatLambdaCDM(H0=70.0, Om0=0.3)


def redshift_flux(
    wave_rest: np.ndarray,
    flux_rest: np.ndarray,
    z: float | np.ndarray,
    cosmo: FlatLambdaCDM | None = None,
    distance_dimming: bool = True,
    input_units: str = "lsun",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Cosmologically redshift a rest-frame spectrum or batch of spectra.

    Args:
        wave_rest: Rest-frame wavelength array in Angstroms.
        flux_rest: Rest-frame luminosity density L_lambda (e.g. erg/s/A or L_sun/A).
        z: Cosmological redshift (scalar float or 1D array of redshifts).
        cosmo: FlatLambdaCDM instance (defaults to H0=70, Om0=0.3).
        distance_dimming: If True, scale flux by 1 / (4 * pi * D_L^2) in cm^2.
                         If False, only apply (1 / (1 + z)) bandpass energy compression.
        input_units: 'lsun' (L_sun/A per formed M_sun) or 'cgs' (erg/s/A).
                     When distance_dimming=True and input_units='lsun', scales by
                     L_SUN_ERG_S (3.828e33 erg/s) to produce physical cgs flux density.

    Returns:
        wave_obs: Observed-frame wavelength array in Angstroms.
        flux_obs: Observed-frame flux density F_lambda.
    """
    z_arr = np.asarray(z)
    if z_arr.ndim == 0 and float(z_arr) <= 0.0:
        return np.asarray(wave_rest), np.asarray(flux_rest)

    cosmo = cosmo or DEFAULT_COSMOLOGY

    # Spectral flux density transformation:
    # F_lambda(lambda_obs) = (1 / (1 + z)) * L_lambda(lambda_rest) / (4 * pi * D_L^2)
    dimming_factor = 1.0 / (1.0 + z_arr)
    if distance_dimming:
        d_L_cm = cosmo.luminosity_distance_cm(z_arr)
        dimming_factor = dimming_factor / (4.0 * np.pi * (np.maximum(d_L_cm, 1e-10) ** 2))
        if input_units == "lsun":
            dimming_factor = dimming_factor * L_SUN_ERG_S

    dtype = np.float64 if distance_dimming else np.float32

    if z_arr.ndim > 0 and flux_rest.ndim == 2:
        flux_obs = (np.asarray(flux_rest, dtype=dtype) * dimming_factor[:, None]).astype(dtype)
        return np.asarray(wave_rest), flux_obs
    else:
        wave_obs = np.asarray(wave_rest) * (1.0 + float(z_arr))
        flux_obs = (np.asarray(flux_rest, dtype=dtype) * float(dimming_factor)).astype(dtype)
        return wave_obs, flux_obs


def apply_redshift_to_chunk(
    spec_block: np.ndarray,
    z_block: np.ndarray,
    wave_rest: np.ndarray,
    apply_igm: bool = False,
    distance_dimming: bool = False,
    input_units: str = "lsun",
    cosmo: FlatLambdaCDM | None = None,
) -> np.ndarray:
    """
    Apply cosmological redshift, distance dimming, and optional Madau IGM attenuation
    to a 2D chunk of rest-frame spectra (N x W) for heterogeneous per-galaxy redshifts.
    """
    z = np.atleast_1d(np.squeeze(np.asarray(z_block, dtype=np.float64)))
    n_gal = spec_block.shape[0]
    if len(z) == 1 and n_gal > 1:
        z = np.full(n_gal, z[0], dtype=np.float64)

    cosmo = cosmo or DEFAULT_COSMOLOGY
    dimming_factor = 1.0 / (1.0 + z)
    if distance_dimming:
        d_L_cm = cosmo.luminosity_distance_cm(z)
        dimming_factor = dimming_factor / (4.0 * np.pi * (np.maximum(d_L_cm, 1e-10) ** 2))
        if input_units == "lsun":
            dimming_factor = dimming_factor * L_SUN_ERG_S

    dtype = np.float64 if distance_dimming else np.float32
    out = (spec_block.astype(dtype) * dimming_factor[:, None]).astype(dtype)

    if apply_igm:
        from specsynth.igm import madau_transmission
        for i, zi in enumerate(z):
            if zi > 0.0:
                w_obs = wave_rest * (1.0 + zi)
                t_igm = madau_transmission(w_obs, zi)
                out[i] = out[i] * t_igm

    return out.astype(np.float64 if distance_dimming else np.float32)


def project_per_galaxy_photometry_chunk(
    spec_block: np.ndarray,
    z_block: np.ndarray,
    wave_rest: np.ndarray,
    filter_data: list[tuple[str, np.ndarray, np.ndarray, float]],
    apply_igm: bool = False,
    distance_dimming: bool = False,
    input_units: str = "lsun",
    cosmo: FlatLambdaCDM | None = None,
) -> np.ndarray:
    """
    Project rest-frame spectra (N x W) into observed broadband photometry (N x F)
    for per-galaxy redshifts z_i, optionally applying distance dimming and IGM absorption.

    Args:
        spec_block: (N, W) galaxy rest-frame spectra.
        z_block: (N,) or (N, 1) per-galaxy redshifts.
        wave_rest: (W,) rest-frame wavelength grid.
        filter_data: List of (name, wave, transmission, norm) tuples for each filter.
        apply_igm: Whether to apply Madau (1995) IGM attenuation.
        distance_dimming: Whether to apply 1 / (4 * pi * D_L^2) cosmological distance dimming.
        input_units: 'lsun' or 'cgs'.
        cosmo: FlatLambdaCDM instance.
    """
    z = np.atleast_1d(np.squeeze(np.asarray(z_block, dtype=np.float64)))
    n_gal = spec_block.shape[0]
    if len(z) == 1 and n_gal > 1:
        z = np.full(n_gal, z[0], dtype=np.float64)

    n_filters = len(filter_data)
    cosmo = cosmo or DEFAULT_COSMOLOGY

    dimming_factor = 1.0 / (1.0 + z)
    if distance_dimming:
        d_L_cm = cosmo.luminosity_distance_cm(z)
        dimming_factor = dimming_factor / (4.0 * np.pi * (np.maximum(d_L_cm, 1e-10) ** 2))
        if input_units == "lsun":
            dimming_factor = dimming_factor * L_SUN_ERG_S

    dtype = np.float64 if distance_dimming else np.float32
    phot = np.zeros((n_gal, n_filters), dtype=dtype)

    igm_fn = None
    if apply_igm:
        from specsynth.igm import madau_transmission
        igm_fn = madau_transmission

    dw_rest = np.gradient(wave_rest)

    for i in range(n_gal):
        zi = float(z[i])
        z_p1 = 1.0 + zi
        w_obs = wave_rest * z_p1
        dw_obs = dw_rest * z_p1

        if igm_fn is not None and zi > 0.0:
            t_igm = igm_fn(w_obs, zi)
        else:
            t_igm = 1.0

        s_rest = spec_block[i].astype(dtype)

        for j, (fname, fw, ft, fnorm) in enumerate(filter_data):
            t_eval = np.interp(w_obs, fw, ft, left=0.0, right=0.0)
            weight = (t_eval * t_igm * w_obs * dw_obs) / fnorm
            phot[i, j] = np.sum(s_rest * weight) * dimming_factor[i]

    return phot
