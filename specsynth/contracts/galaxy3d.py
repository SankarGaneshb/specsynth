"""
Versioned Scientific 3D Galaxy Data Model Contract (v1.0.0).
Defines coordinate frames, particle schemas, physical units, and provenance standards.
Enforces P0.4 and P2 data foundations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import numpy as np


class ParticleType(str, Enum):
    """Astrophysical particle and component types in simulations."""
    STAR = "star"
    GAS = "gas"
    DARK_MATTER = "dark_matter"
    BLACK_HOLE = "black_hole"


class GeometrySource(str, Enum):
    """Provenance indicator distinguishing physical simulation data from procedural mocks."""
    SIMULATION_DERIVED = "simulation_derived"
    PROCEDURAL_ILLUSTRATIVE = "procedural_illustrative"


class CoordinateFrame(str, Enum):
    """Standard spatial coordinate systems for 3D galaxies."""
    PHYSICAL_REST = "physical_rest"        # Origin at galaxy center of mass, coordinates in physical kpc, aligned with angular momentum
    COMOVING_BOX = "comoving_box"          # Origin at simulation box corner, coordinates in comoving ckpc/h
    OBSERVER_SKY = "observer_sky"          # Right Ascension (deg), Declination (deg), and line-of-sight comoving distance (Mpc)


@dataclass
class ParticleBatchContract:
    """
    Standard schema for a homogeneous particle component (e.g. all star particles in a subhalo).

    Attributes:
        particle_type: Particle component classification.
        coordinates_kpc: 2D array of shape (N, 3) in physical kpc.
        velocities_km_s: 2D array of shape (N, 3) in km/s.
        masses_msun: 1D array of shape (N,) in solar masses M_sun.
        ages_yr: Optional 1D array of stellar ages in years (required for stars).
        metallicities_z: Optional 1D array of metallicities in mass fraction Z (required for stars).
        smoothing_lengths_kpc: Optional 1D array of SPH smoothing lengths in physical kpc (gas).
    """
    particle_type: ParticleType
    coordinates_kpc: np.ndarray
    velocities_km_s: np.ndarray
    masses_msun: np.ndarray
    ages_yr: Optional[np.ndarray] = None
    metallicities_z: Optional[np.ndarray] = None
    smoothing_lengths_kpc: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        self.coordinates_kpc = np.asarray(self.coordinates_kpc, dtype=np.float32)
        self.velocities_km_s = np.asarray(self.velocities_km_s, dtype=np.float32)
        self.masses_msun = np.asarray(self.masses_msun, dtype=np.float32)

        if self.ages_yr is not None:
            self.ages_yr = np.asarray(self.ages_yr, dtype=np.float32)
        if self.metallicities_z is not None:
            self.metallicities_z = np.asarray(self.metallicities_z, dtype=np.float32)
        if self.smoothing_lengths_kpc is not None:
            self.smoothing_lengths_kpc = np.asarray(self.smoothing_lengths_kpc, dtype=np.float32)

        self.validate()

    def validate(self) -> None:
        """Validate shapes and numerical finiteness."""
        n_particles = len(self.masses_msun)
        if self.coordinates_kpc.shape != (n_particles, 3):
            raise ValueError(f"coordinates_kpc shape mismatch: expected ({n_particles}, 3), got {self.coordinates_kpc.shape}")
        if self.velocities_km_s.shape != (n_particles, 3):
            raise ValueError(f"velocities_km_s shape mismatch: expected ({n_particles}, 3), got {self.velocities_km_s.shape}")

        if not np.all(np.isfinite(self.coordinates_kpc)):
            raise ValueError("coordinates_kpc contains non-finite values")
        if not np.all(np.isfinite(self.velocities_km_s)):
            raise ValueError("velocities_km_s contains non-finite values")
        if not np.all(np.isfinite(self.masses_msun)):
            raise ValueError("masses_msun contains non-finite values")

        if np.any(self.masses_msun <= 0):
            raise ValueError("masses_msun contains non-positive values")

        if self.particle_type == ParticleType.STAR:
            if self.ages_yr is not None and np.any(self.ages_yr < 0):
                raise ValueError("Star particles contain negative ages")
            if self.metallicities_z is not None and np.any(self.metallicities_z < 0):
                raise ValueError("Star particles contain negative metallicities")


@dataclass
class Galaxy3DContract:
    """
    Complete scientific 3D galaxy model representing structural, kinematic, and component data.

    Attributes:
        galaxy_id: Unique string identifier linking 3D model to catalog and spectrum.
        geometry_source: Provenance indicator (SIMULATION_DERIVED or PROCEDURAL_ILLUSTRATIVE).
        coordinate_frame: Spatial coordinate system used for particle coordinates.
        redshift: Cosmological redshift of the snapshot.
        center_of_mass_kpc: Center of mass coordinates (x, y, z) in physical kpc.
        half_mass_radius_kpc: Stellar half-mass radius (r_half / r_e) in physical kpc.
        components: Dictionary of particle components keyed by ParticleType string.
        version: Contract version string.
        provenance: Metadata tracking simulation name, snapshot number, extraction timestamp, and git SHA.
    """
    galaxy_id: str
    geometry_source: GeometrySource
    coordinate_frame: CoordinateFrame
    redshift: float
    center_of_mass_kpc: tuple[float, float, float]
    half_mass_radius_kpc: float
    components: dict[str, ParticleBatchContract]
    version: str = "1.0.0"
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate 3D galaxy physical parameters."""
        if not self.galaxy_id:
            raise ValueError("galaxy_id cannot be empty")
        if self.redshift < 0.0:
            raise ValueError(f"redshift must be non-negative, got {self.redshift}")
        if self.half_mass_radius_kpc <= 0.0:
            raise ValueError(f"half_mass_radius_kpc must be positive, got {self.half_mass_radius_kpc}")
        if len(self.center_of_mass_kpc) != 3:
            raise ValueError(f"center_of_mass_kpc must be a 3D coordinate tuple, got {self.center_of_mass_kpc}")

        # Ensure that simulation-derived geometry contains valid particles
        if self.geometry_source == GeometrySource.SIMULATION_DERIVED and not self.components:
            raise ValueError("Simulation-derived galaxy must contain at least one particle component")

    def total_stellar_mass_msun(self) -> float:
        """Sum total stellar mass across star particles."""
        star_comp = self.components.get(ParticleType.STAR.value)
        if star_comp is None or len(star_comp.masses_msun) == 0:
            return 0.0
        return float(np.sum(star_comp.masses_msun))

    def to_summary_dict(self) -> dict[str, Any]:
        """Generate high-level metadata summary for JSON/API/MCP responses."""
        counts = {k: len(v.masses_msun) for k, v in self.components.items()}
        return {
            "version": self.version,
            "galaxy_id": self.galaxy_id,
            "geometry_source": self.geometry_source.value,
            "coordinate_frame": self.coordinate_frame.value,
            "redshift": self.redshift,
            "center_of_mass_kpc": list(self.center_of_mass_kpc),
            "half_mass_radius_kpc": self.half_mass_radius_kpc,
            "total_stellar_mass_msun": self.total_stellar_mass_msun(),
            "particle_counts": counts,
            "provenance": self.provenance,
        }
