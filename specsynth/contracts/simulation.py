"""
Versioned Simulation Galaxy Catalog Contract (v1.0.0).
Defines standard schema, physical units, and coordinate conventions for simulation galaxy data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SimulationGalaxyContract:
    """
    Standard schema and physical invariant validator for an individual simulation galaxy.

    Attributes:
        galaxy_id: Unique string identifier (e.g. 'TNG100-1-Subhalo-424601').
        simulation_name: Simulation identifier (e.g. 'IllustrisTNG-100', 'FIRE-2', 'EAGLE').
        snapshot: Snapshot number / index in the simulation sequence.
        redshift: Cosmological redshift z >= 0.
        stellar_mass_msun: Total stellar mass in M_sun (linear, not log).
        sfr_msun_per_yr: Star formation rate in M_sun / yr.
        metallicity_mass_fraction: Stellar metallicity mass fraction Z (solar Z_sun ~ 0.0142).
        tau_diffuse: Diffuse ISM optical depth (Charlot & Fall 2000, A_V / 1.086).
        tau_birth: Birth cloud optical depth (Charlot & Fall 2000).
        sfh_onset_gyr: Lookback time in Gyr when star formation began.
        sfh_tau_gyr: Exponential e-folding time tau in Gyr.
        version: Schema version string.
        coordinates_physical_kpc: Center of mass position (x, y, z) in physical kpc.
        coordinates_comoving_ckpc: Center of mass position (x, y, z) in comoving kpc / h.
        celestial_coordinates_deg: Sky position (Right Ascension, Declination) in degrees.
        parent_halo_id: Optional parent friends-of-friends halo ID.
        progenitor_id: Optional main progenitor subhalo ID from merger tree.
        descendant_id: Optional descendant subhalo ID from merger tree.
        metadata: Arbitrary metadata for simulation-specific properties (e.g. gas fraction, BH mass).
    """
    galaxy_id: str
    simulation_name: str
    snapshot: int
    redshift: float
    stellar_mass_msun: float
    sfr_msun_per_yr: float
    metallicity_mass_fraction: float
    tau_diffuse: float
    tau_birth: float
    sfh_onset_gyr: float
    sfh_tau_gyr: float
    version: str = "1.0.0"
    coordinates_physical_kpc: Optional[tuple[float, float, float]] = None
    coordinates_comoving_ckpc: Optional[tuple[float, float, float]] = None
    celestial_coordinates_deg: Optional[tuple[float, float]] = None
    parent_halo_id: Optional[str] = None
    progenitor_id: Optional[str] = None
    descendant_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate physical ranges and invariants."""
        if not self.galaxy_id or not isinstance(self.galaxy_id, str):
            raise ValueError(f"galaxy_id must be a non-empty string, got {self.galaxy_id!r}")
        if self.redshift < 0.0:
            raise ValueError(f"redshift must be non-negative, got {self.redshift}")
        if self.stellar_mass_msun <= 0.0:
            raise ValueError(f"stellar_mass_msun must be positive, got {self.stellar_mass_msun}")
        if self.sfr_msun_per_yr < 0.0:
            raise ValueError(f"sfr_msun_per_yr cannot be negative, got {self.sfr_msun_per_yr}")
        if self.metallicity_mass_fraction <= 0.0:
            raise ValueError(f"metallicity_mass_fraction must be positive, got {self.metallicity_mass_fraction}")
        if self.tau_diffuse < 0.0:
            raise ValueError(f"tau_diffuse cannot be negative, got {self.tau_diffuse}")
        if self.tau_birth < 0.0:
            raise ValueError(f"tau_birth cannot be negative, got {self.tau_birth}")
        if self.sfh_onset_gyr <= 0.0:
            raise ValueError(f"sfh_onset_gyr must be positive, got {self.sfh_onset_gyr}")
        if self.sfh_tau_gyr <= 0.0:
            raise ValueError(f"sfh_tau_gyr must be positive, got {self.sfh_tau_gyr}")

        if self.celestial_coordinates_deg is not None:
            ra, dec = self.celestial_coordinates_deg
            if not (0.0 <= ra <= 360.0):
                raise ValueError(f"RA must be in [0, 360] degrees, got {ra}")
            if not (-90.0 <= dec <= 90.0):
                raise ValueError(f"Dec must be in [-90, 90] degrees, got {dec}")

    def to_dict(self) -> dict[str, Any]:
        """Convert contract to serializable dictionary."""
        return {
            "version": self.version,
            "galaxy_id": self.galaxy_id,
            "simulation_name": self.simulation_name,
            "snapshot": self.snapshot,
            "redshift": self.redshift,
            "stellar_mass_msun": self.stellar_mass_msun,
            "sfr_msun_per_yr": self.sfr_msun_per_yr,
            "metallicity_mass_fraction": self.metallicity_mass_fraction,
            "tau_diffuse": self.tau_diffuse,
            "tau_birth": self.tau_birth,
            "sfh_onset_gyr": self.sfh_onset_gyr,
            "sfh_tau_gyr": self.sfh_tau_gyr,
            "coordinates_physical_kpc": self.coordinates_physical_kpc,
            "coordinates_comoving_ckpc": self.coordinates_comoving_ckpc,
            "celestial_coordinates_deg": self.celestial_coordinates_deg,
            "parent_halo_id": self.parent_halo_id,
            "progenitor_id": self.progenitor_id,
            "descendant_id": self.descendant_id,
            "metadata": self.metadata,
        }
