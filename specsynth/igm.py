from __future__ import annotations

import numpy as np

# Madau (1995) Lyman series transition rest wavelengths (Angstroms) and coefficients
LYMAN_SERIES = [
    (1215.67, 0.0036),  # Ly-alpha
    (1025.72, 0.0017),  # Ly-beta
    (972.54, 0.0012),   # Ly-gamma
    (949.74, 0.00093),  # Ly-delta
]
LYMAN_LIMIT_AA = 911.75


def madau_transmission(wave_obs: np.ndarray, z: float) -> np.ndarray:
    """
    Compute Intergalactic Medium (IGM) transmission using the Madau (1995) prescription.

    Args:
        wave_obs: Observed-frame wavelength array in Angstroms.
        z: Galaxy cosmological redshift.

    Returns:
        transmission: Multiplicative flux transmission array T_IGM in [0, 1].
    """
    if z <= 0.0:
        return np.ones_like(wave_obs, dtype=np.float32)

    wave_obs = np.asarray(wave_obs, dtype=np.float64)
    tau_eff = np.zeros_like(wave_obs)

    # 1. Lyman series line blanketing
    for lambda_j, a_j in LYMAN_SERIES:
        # Effective only when observed wavelength is between lambda_j and lambda_j * (1 + z)
        mask = (wave_obs >= lambda_j) & (wave_obs <= lambda_j * (1.0 + z))
        tau_eff[mask] += a_j * (wave_obs[mask] / lambda_j) ** 3.46

    # 2. Lyman continuum photoelectric absorption (rest-frame < 912 A)
    lyman_limit_obs = LYMAN_LIMIT_AA * (1.0 + z)
    lc_mask = wave_obs < lyman_limit_obs
    if np.any(lc_mask):
        xc = wave_obs[lc_mask] / LYMAN_LIMIT_AA
        # Madau (1995) Eq. 16: photoelectric absorption by neutral hydrogen
        tau_lc = (
            0.25 * (xc**3) * ((1.0 + z) ** 0.46 - (xc**0.46))
            + 9.4 * (xc**1.5) * ((1.0 + z) ** 0.18 - (xc**0.18))
            - 0.7 * (xc**3) * ((xc**-1.32) - (1.0 + z) ** -1.32)
            - 0.023 * ((1.0 + z) ** 1.68 - (xc**1.68))
        )
        tau_eff[lc_mask] += np.clip(tau_lc, 0.0, 50.0)

    # Transmission is exp(-tau)
    return np.exp(-np.clip(tau_eff, 0.0, 50.0)).astype(np.float32)
