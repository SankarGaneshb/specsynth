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

    def to_web_json(
        self,
        max_particles_per_component: int = 5000,
        seed: int = 42,
    ) -> dict[str, Any]:
        """
        Serialize 3D model to a lightweight JSON structure suitable for WebGL 60 FPS rendering.
        Decimates dense particle batches while strictly preserving density profiles and total mass.
        """
        from specsynth.transforms import decimate_particles

        particles_dict = {}
        for comp_name, comp_batch in self.components.items():
            c, v, m, idx = decimate_particles(
                comp_batch.coordinates_kpc,
                comp_batch.velocities_km_s,
                comp_batch.masses_msun,
                max_particles=max_particles_per_component,
                seed=seed,
            )
            data: dict[str, Any] = {
                "particle_type": comp_batch.particle_type.value,
                "coordinates_kpc": np.round(c, 3).tolist(),
                "masses_msun": np.round(m, 2).tolist(),
            }
            if comp_batch.ages_yr is not None:
                data["ages_yr"] = np.round(comp_batch.ages_yr[idx], 0).tolist()
            if comp_batch.metallicities_z is not None:
                data["metallicities_z"] = np.round(comp_batch.metallicities_z[idx], 6).tolist()
            if v is not None:
                data["velocities_km_s"] = np.round(v, 2).tolist()
            particles_dict[comp_name] = data

        return {
            "version": self.version,
            "galaxy_id": self.galaxy_id,
            "geometry_source": self.geometry_source.value,
            "coordinate_frame": self.coordinate_frame.value,
            "redshift": float(self.redshift),
            "center_of_mass_kpc": [round(float(x), 3) for x in self.center_of_mass_kpc],
            "half_mass_radius_kpc": round(float(self.half_mass_radius_kpc), 3),
            "total_stellar_mass_msun": float(self.total_stellar_mass_msun()),
            "particles": particles_dict,
            "provenance": self.provenance,
        }

    def extract_non_parametric_sfh(
        self,
        ages_yr: np.ndarray,
        mets_z: np.ndarray,
        formed_mass: bool = True,
    ) -> np.ndarray:
        """
        Extract non-parametric SFH matrix of shape (1, N_age * N_met)
        by binning 3D star particles across the 2D (age, metallicity) SPS grid.

        Args:
            ages_yr: 1D strictly ascending array of grid ages in years (shape N_age).
            mets_z: 1D strictly ascending array of grid metallicities in mass fraction (shape N_met).
            formed_mass: If True, scale surviving star particle masses back to initial formed masses
                         via M_formed = M_surviving / f_surv(t). If False, bin surviving masses directly.

        Returns:
            2D array of shape (1, N_age * N_met) representing stellar mass in each grid cell.
        """
        from specsynth.sfh import chabrier_surviving_mass_fraction

        star_comp = self.components.get(ParticleType.STAR.value)
        if star_comp is None or len(star_comp.masses_msun) == 0:
            raise ValueError(f"Galaxy '{self.galaxy_id}' has no star particles to extract SFH")
        if star_comp.ages_yr is None or star_comp.metallicities_z is None:
            raise ValueError(f"Star particles in '{self.galaxy_id}' must have ages_yr and metallicities_z")

        p_masses = np.asarray(star_comp.masses_msun, dtype=np.float64)
        p_ages = np.asarray(star_comp.ages_yr, dtype=np.float64)
        p_mets = np.asarray(star_comp.metallicities_z, dtype=np.float64)

        if formed_mass:
            f_surv = np.asarray(chabrier_surviving_mass_fraction(p_ages), dtype=np.float64)
            weights = p_masses / np.maximum(f_surv, 0.45)
        else:
            weights = p_masses.copy()

        n_age = len(ages_yr)
        n_met = len(mets_z)

        # Logarithmic bin edges for age
        log_ages = np.log10(np.maximum(ages_yr, 1.0))
        if n_age == 1:
            age_edges = np.array([ages_yr[0] * 0.5, ages_yr[0] * 1.5], dtype=np.float64)
        else:
            age_edges = np.zeros(n_age + 1, dtype=np.float64)
            age_edges[1:-1] = 10.0 ** (0.5 * (log_ages[:-1] + log_ages[1:]))
            age_edges[0] = 10.0 ** (log_ages[0] - 0.5 * (log_ages[1] - log_ages[0]))
            age_edges[-1] = 10.0 ** (log_ages[-1] + 0.5 * (log_ages[-1] - log_ages[-2]))

        # Logarithmic bin edges for metallicity
        log_mets = np.log10(np.maximum(mets_z, 1e-6))
        if n_met == 1:
            met_edges = np.array([mets_z[0] * 0.5, mets_z[0] * 1.5], dtype=np.float64)
        else:
            met_edges = np.zeros(n_met + 1, dtype=np.float64)
            met_edges[1:-1] = 10.0 ** (0.5 * (log_mets[:-1] + log_mets[1:]))
            met_edges[0] = 10.0 ** (log_mets[0] - 0.5 * (log_mets[1] - log_mets[0]))
            met_edges[-1] = 10.0 ** (log_mets[-1] + 0.5 * (log_mets[-1] - log_mets[-2]))

        # Clamp particles slightly inside bounds so no mass is lost outside the grid
        clamped_ages = np.clip(p_ages, age_edges[0] * 1.00001, age_edges[-1] * 0.99999)
        clamped_mets = np.clip(p_mets, met_edges[0] * 1.00001, met_edges[-1] * 0.99999)

        # 2D weighted histogram: shape (N_age, N_met)
        H, _, _ = np.histogram2d(clamped_ages, clamped_mets, bins=[age_edges, met_edges], weights=weights)

        # Flatten in C order to shape (1, N_age * N_met)
        return H.reshape(1, n_age * n_met).astype(np.float64)

    @classmethod
    def from_particles(
        cls,
        galaxy_id: str,
        redshift: float,
        components: dict[str, ParticleBatchContract],
        geometry_source: GeometrySource = GeometrySource.SIMULATION_DERIVED,
        align_angular_momentum: bool = True,
        provenance: dict[str, Any] | None = None,
    ) -> Galaxy3DContract:
        """
        Factory method to construct a validated Galaxy3DContract from particle batches.
        Automatically handles center-of-mass centering, angular-momentum rotation alignment,
        and half-mass radius calculation.
        """
        from specsynth.transforms import (
            align_to_angular_momentum,
            center_particles,
            compute_half_mass_radius,
            compute_rotation_matrix_to_z,
            compute_angular_momentum,
        )

        # Find primary component for centering (stars preferred, gas fallback)
        primary_key = ParticleType.STAR.value if ParticleType.STAR.value in components else list(components.keys())[0]
        primary = components[primary_key]

        # Shift center of mass
        _, com = center_particles(primary.coordinates_kpc, primary.masses_msun)

        # Apply CoM shift to all components
        shifted_comps: dict[str, ParticleBatchContract] = {}
        for k, comp in components.items():
            c_shifted = comp.coordinates_kpc - com[None, :]
            shifted_comps[k] = ParticleBatchContract(
                particle_type=comp.particle_type,
                coordinates_kpc=c_shifted,
                velocities_km_s=comp.velocities_km_s,
                masses_msun=comp.masses_msun,
                ages_yr=comp.ages_yr,
                metallicities_z=comp.metallicities_z,
                smoothing_lengths_kpc=comp.smoothing_lengths_kpc,
            )

        # Align with angular momentum of stars (or gas)
        if align_angular_momentum:
            prim_shifted = shifted_comps[primary_key]
            j_vec = compute_angular_momentum(
                prim_shifted.coordinates_kpc,
                prim_shifted.velocities_km_s,
                prim_shifted.masses_msun,
            )
            R = compute_rotation_matrix_to_z(j_vec)

            aligned_comps: dict[str, ParticleBatchContract] = {}
            for k, comp in shifted_comps.items():
                c_rot = (comp.coordinates_kpc @ R.T).astype(np.float32)
                v_rot = (comp.velocities_km_s @ R.T).astype(np.float32)
                aligned_comps[k] = ParticleBatchContract(
                    particle_type=comp.particle_type,
                    coordinates_kpc=c_rot,
                    velocities_km_s=v_rot,
                    masses_msun=comp.masses_msun,
                    ages_yr=comp.ages_yr,
                    metallicities_z=comp.metallicities_z,
                    smoothing_lengths_kpc=comp.smoothing_lengths_kpc,
                )
            final_comps = aligned_comps
        else:
            final_comps = shifted_comps

        # Calculate half mass radius for stars
        star_comp = final_comps.get(ParticleType.STAR.value, final_comps[primary_key])
        r_half = compute_half_mass_radius(star_comp.coordinates_kpc, star_comp.masses_msun)

        prov = provenance.copy() if provenance else {}
        prov.setdefault("pipeline", "specsynth.contracts.Galaxy3DContract.from_particles")

        return cls(
            galaxy_id=galaxy_id,
            geometry_source=geometry_source,
            coordinate_frame=CoordinateFrame.PHYSICAL_REST,
            redshift=float(redshift),
            center_of_mass_kpc=(float(com[0]), float(com[1]), float(com[2])),
            half_mass_radius_kpc=float(r_half),
            components=final_comps,
            provenance=prov,
        )
