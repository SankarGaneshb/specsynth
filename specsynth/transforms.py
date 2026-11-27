"""
specsynth.transforms
====================
Astrophysical spatial coordinate transformations, kinematic centering, angular momentum
rotation, half-mass radii, and WebGL particle decimation.
Enforces P2.M3.1 and P2.M3.4 standards.
"""

from __future__ import annotations

from typing import Tuple
import numpy as np


def comoving_to_physical_kpc(
    coords_ckpc_h: np.ndarray,
    redshift: float,
    h: float = 0.6774,
) -> np.ndarray:
    """
    Convert simulation comoving coordinates in ckpc/h to physical kpc:
      r_phys = r_comov / ((1 + z) * h).

    Args:
        coords_ckpc_h: Array of shape (N, 3) in comoving ckpc/h.
        redshift: Cosmological redshift z >= 0.
        h: Dimensionless Hubble parameter H0 / 100.

    Returns:
        Array of shape (N, 3) in physical kpc.
    """
    if redshift < 0:
        raise ValueError(f"redshift must be non-negative, got {redshift}")
    if h <= 0:
        raise ValueError(f"h must be positive, got {h}")

    scale_factor = 1.0 / (1.0 + redshift)
    factor = scale_factor / h
    return (np.asarray(coords_ckpc_h, dtype=np.float64) * factor).astype(np.float32)


def physical_velocity_km_s(
    vel_code: np.ndarray,
    redshift: float,
    convention: str = "gadget",
) -> np.ndarray:
    """
    Convert simulation peculiar velocity in code units to physical peculiar velocity in km/s:
      v_phys = v_code * sqrt(a) where a = 1 / (1 + z).

    In Gadget/Arepo/IllustrisTNG, peculiar velocity code units are v_code = v_pec * sqrt(a).
    """
    if redshift < 0:
        raise ValueError(f"redshift must be non-negative, got {redshift}")
    scale_factor = 1.0 / (1.0 + redshift)
    return (np.asarray(vel_code, dtype=np.float64) * np.sqrt(scale_factor)).astype(np.float32)


def physical_mass_msun(
    mass_code: np.ndarray,
    h: float = 0.6774,
    mass_unit_msun: float = 1e10,
) -> np.ndarray:
    """
    Convert simulation mass in code units (typically 10^10 M_sun / h for TNG/Gadget) to solar masses M_sun:
      M_phys = M_code * mass_unit_msun / h.
    """
    if h <= 0:
        raise ValueError(f"h must be positive, got {h}")
    return (np.asarray(mass_code, dtype=np.float64) * (mass_unit_msun / h)).astype(np.float32)


def center_of_mass(
    coords: np.ndarray,
    masses: np.ndarray,
) -> np.ndarray:
    """
    Calculate the mass-weighted center of mass:
      r_CoM = sum(m_i * r_i) / sum(m_i).

    Args:
        coords: Array of shape (N, 3).
        masses: Array of shape (N,) positive masses.

    Returns:
        1D array of shape (3,) representing center of mass coordinates.
    """
    c = np.asarray(coords, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)
    total_mass = np.sum(m)
    if total_mass <= 0:
        return np.mean(c, axis=0) if len(c) > 0 else np.zeros(3)
    return np.sum(c * m[:, None], axis=0) / total_mass


def center_particles(
    coords: np.ndarray,
    masses: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Shift coordinates so that the mass-weighted center of mass is at (0, 0, 0).

    Returns:
        centered_coords: Shape (N, 3).
        com: Center of mass vector of shape (3,).
    """
    com = center_of_mass(coords, masses)
    centered = coords - com[None, :]
    return centered.astype(np.float32), com


def compute_angular_momentum(
    coords: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
) -> np.ndarray:
    """
    Compute total angular momentum vector J = sum(m_i * (r_i x v_i)).

    Args:
        coords: Centered coordinates of shape (N, 3).
        velocities: Velocities of shape (N, 3) in km/s.
        masses: Masses of shape (N,).

    Returns:
        1D array of shape (3,) representing total angular momentum vector.
    """
    r = np.asarray(coords, dtype=np.float64)
    v = np.asarray(velocities, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)

    # Cross product r x v
    rxv = np.cross(r, v)
    return np.sum(rxv * m[:, None], axis=0)


def compute_rotation_matrix_to_z(target_vector: np.ndarray) -> np.ndarray:
    """
    Compute the 3x3 Rodrigues rotation matrix that aligns target_vector with the +Z axis [0, 0, 1].

    If target_vector is zero or already aligned, returns identity.
    """
    v = np.asarray(target_vector, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm < 1e-12:
        return np.eye(3, dtype=np.float64)

    v_hat = v / norm
    z_hat = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    # Dot product
    dot = np.dot(v_hat, z_hat)

    # If already aligned
    if np.isclose(dot, 1.0, atol=1e-8):
        return np.eye(3, dtype=np.float64)

    # If anti-aligned (180 degree rotation around X axis)
    if np.isclose(dot, -1.0, atol=1e-8):
        return np.diag([1.0, -1.0, -1.0])

    # Rotation axis: u = v_hat x z_hat
    u = np.cross(v_hat, z_hat)
    u_norm = np.linalg.norm(u)
    u_hat = u / u_norm

    angle = np.arccos(np.clip(dot, -1.0, 1.0))
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)

    # Rodrigues formula: R = I + sin(a)*K + (1 - cos(a))*K^2
    ux, uy, uz = u_hat
    K = np.array([
        [0.0, -uz, uy],
        [uz, 0.0, -ux],
        [-uy, ux, 0.0],
    ], dtype=np.float64)

    R = np.eye(3, dtype=np.float64) + sin_a * K + (1.0 - cos_a) * (K @ K)
    return R


def align_to_angular_momentum(
    coords: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Rotate coordinates and velocities such that the total angular momentum J
    aligns with the +Z axis. This places rotating galactic disks into the X-Y plane.

    Returns:
        aligned_coords: Shape (N, 3).
        aligned_velocities: Shape (N, 3).
        rotation_matrix: 3x3 rotation matrix.
    """
    j_vec = compute_angular_momentum(coords, velocities, masses)
    R = compute_rotation_matrix_to_z(j_vec)

    # Rotate coordinates: r_rot = r @ R.T
    coords_rot = (coords @ R.T).astype(np.float32)
    vels_rot = (velocities @ R.T).astype(np.float32)

    return coords_rot, vels_rot, R


def compute_half_mass_radius(
    coords_kpc: np.ndarray,
    masses_msun: np.ndarray,
) -> float:
    """
    Compute 3D spherical stellar half-mass radius r_half (radius enclosing 50% of total mass).

    Args:
        coords_kpc: Centered coordinates of shape (N, 3) in physical kpc.
        masses_msun: Masses of shape (N,).

    Returns:
        r_half: Radius in physical kpc.
    """
    r = np.linalg.norm(coords_kpc, axis=1)
    m = np.asarray(masses_msun, dtype=np.float64)

    total_mass = np.sum(m)
    if total_mass <= 0 or len(r) == 0:
        return 1.0

    sort_idx = np.argsort(r)
    r_sorted = r[sort_idx]
    m_sorted = m[sort_idx]

    cum_mass = np.cumsum(m_sorted)
    target = 0.5 * total_mass

    idx = np.searchsorted(cum_mass, target)
    if idx >= len(r_sorted):
        idx = len(r_sorted) - 1

    return float(r_sorted[idx])


def decimate_particles(
    coords: np.ndarray,
    velocities: np.ndarray | None,
    masses: np.ndarray,
    max_particles: int = 5000,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray, np.ndarray]:
    """
    Intelligently decimate particles for smooth 60 FPS WebGL rendering
    while preserving spatial density profile and mass distribution.

    Args:
        coords: Coordinates of shape (N, 3).
        velocities: Velocities of shape (N, 3) or None.
        masses: Masses of shape (N,).
        max_particles: Target maximum particle count.
        seed: Random seed for deterministic decimation.

    Returns:
        sampled_coords: Shape (min(N, max_particles), 3).
        sampled_velocities: Shape (min(N, max_particles), 3) or None.
        sampled_masses: Scaled masses.
        sample_indices: Indices chosen.
    """
    n = len(coords)
    if n <= max_particles:
        indices = np.arange(n)
        return coords, velocities, masses, indices

    rng = np.random.default_rng(seed)

    # Stratified sampling: sample proportionally to radial density
    r = np.linalg.norm(coords, axis=1)
    # Give higher sampling weight to core while maintaining outer envelope
    weights = np.maximum(masses, 1e-10) / (np.maximum(r, 0.1) ** 0.5)
    weights /= np.sum(weights)

    indices = rng.choice(n, size=max_particles, replace=False, p=weights)
    indices.sort()

    sampled_c = coords[indices]
    sampled_v = velocities[indices] if velocities is not None else None
    # Scale sampled masses so total mass is preserved
    mass_scale = np.sum(masses) / np.sum(masses[indices])
    sampled_m = (masses[indices] * mass_scale).astype(np.float32)

    return sampled_c, sampled_v, sampled_m, indices
