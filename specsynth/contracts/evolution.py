from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProgenitorNode:
    """
    A single snapshot node along a galaxy's evolutionary progenitor branch.
    
    Attributes:
        redshift: Cosmological redshift z (>= 0.0).
        cosmic_time_gyr: Cosmic age of the universe at redshift z in Gyr.
        lookback_time_gyr: Lookback time from z=0 to redshift z in Gyr.
        comoving_coords_mpc: (x, y, z) spatial location in comoving Mpc.
        physical_coords_kpc: (x, y, z) spatial location in physical kpc.
        stellar_mass_msun: Total stellar mass M_* at this epoch in M_sun.
        sfr_msun_per_yr: Instantaneous star formation rate psi(z) in M_sun/yr.
        metallicity_z: Mass-weighted stellar metallicity Z.
        half_mass_radius_kpc: Spherical stellar half-mass radius r_1/2 in physical kpc.
        photometry: Synthetic fluxes (uJy) and AB magnitudes across telescope filters.
        sed: Spectral energy distribution points [{wave: A, flux: ...}].
        snapshot_id: Simulation snapshot index or identifier.
        subhalo_id: Subhalo identifier at this snapshot.
    """
    redshift: float
    cosmic_time_gyr: float
    lookback_time_gyr: float
    comoving_coords_mpc: tuple[float, float, float]
    physical_coords_kpc: tuple[float, float, float]
    stellar_mass_msun: float
    sfr_msun_per_yr: float
    metallicity_z: float
    half_mass_radius_kpc: float
    photometry: dict[str, float] = field(default_factory=dict)
    sed: list[dict[str, float]] = field(default_factory=list)
    snapshot_id: str | int = ""
    subhalo_id: str | int = ""

    def __post_init__(self):
        if self.redshift < 0.0:
            raise ValueError(f"Redshift must be non-negative, got {self.redshift}")
        if self.stellar_mass_msun <= 0.0:
            raise ValueError(f"Stellar mass must be positive, got {self.stellar_mass_msun}")
        if self.sfr_msun_per_yr < 0.0:
            raise ValueError(f"SFR must be non-negative, got {self.sfr_msun_per_yr}")
        if self.half_mass_radius_kpc <= 0.0:
            raise ValueError(f"Half-mass radius must be positive, got {self.half_mass_radius_kpc}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProgenitorNode:
        comov = tuple(data.get("comoving_coords_mpc", (0.0, 0.0, 0.0)))
        phys = tuple(data.get("physical_coords_kpc", (0.0, 0.0, 0.0)))
        return cls(
            redshift=float(data["redshift"]),
            cosmic_time_gyr=float(data["cosmic_time_gyr"]),
            lookback_time_gyr=float(data["lookback_time_gyr"]),
            comoving_coords_mpc=comov,  # type: ignore
            physical_coords_kpc=phys,   # type: ignore
            stellar_mass_msun=float(data["stellar_mass_msun"]),
            sfr_msun_per_yr=float(data["sfr_msun_per_yr"]),
            metallicity_z=float(data.get("metallicity_z", 0.02)),
            half_mass_radius_kpc=float(data.get("half_mass_radius_kpc", 1.0)),
            photometry=dict(data.get("photometry", {})),
            sed=list(data.get("sed", [])),
            snapshot_id=data.get("snapshot_id", ""),
            subhalo_id=data.get("subhalo_id", ""),
        )


@dataclass
class MergerEvent:
    """
    A galaxy merger event detected along the merger tree.
    """
    redshift: float
    lookback_time_gyr: float
    mass_ratio: float
    merger_type: str  # "major" (> 0.25) or "minor" (<= 0.25)
    secondary_galaxy_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergerEvent:
        return cls(
            redshift=float(data["redshift"]),
            lookback_time_gyr=float(data["lookback_time_gyr"]),
            mass_ratio=float(data["mass_ratio"]),
            merger_type=str(data.get("merger_type", "minor")),
            secondary_galaxy_id=str(data.get("secondary_galaxy_id", "")),
        )


@dataclass
class EvolutionaryTrackContract:
    """
    Versioned contract (v1.0.0) representing a galaxy's complete evolutionary history
    across cosmic epochs, including its main progenitor branch, merger ancestry,
    and 3D lightcone trajectory.
    """
    galaxy_id: str
    main_branch: list[ProgenitorNode]
    mergers: list[MergerEvent] = field(default_factory=list)
    spline_trajectory: list[dict[str, float]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        """Validate astrophysical and schema invariants."""
        if not self.galaxy_id:
            raise ValueError("galaxy_id must not be empty")
        if not self.main_branch:
            raise ValueError("main_branch must contain at least one progenitor node")

        # Check monotonic redshift ordering (ascending: z_0 <= z_1 <= ... <= z_N)
        redshifts = [node.redshift for node in self.main_branch]
        for i in range(len(redshifts) - 1):
            if redshifts[i] > redshifts[i + 1]:
                raise ValueError(
                    f"main_branch nodes must be ordered monotonically by redshift. "
                    f"Node {i} (z={redshifts[i]}) > Node {i+1} (z={redshifts[i+1]})"
                )

        # Lookback time must be strictly non-decreasing with redshift
        lookbacks = [node.lookback_time_gyr for node in self.main_branch]
        for i in range(len(lookbacks) - 1):
            if lookbacks[i] > lookbacks[i + 1] + 1e-4:
                raise ValueError(
                    f"Lookback time must increase with redshift. "
                    f"Node {i} (t_L={lookbacks[i]}) > Node {i+1} (t_L={lookbacks[i+1]})"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "galaxy_id": self.galaxy_id,
            "main_branch": [node.to_dict() for node in self.main_branch],
            "mergers": [m.to_dict() for m in self.mergers],
            "spline_trajectory": self.spline_trajectory,
            "provenance": self.provenance,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionaryTrackContract:
        version = data.get("version", "1.0.0")
        if version != "1.0.0":
            raise ValueError(f"Unsupported contract version: {version}")

        main_branch = [ProgenitorNode.from_dict(n) for n in data.get("main_branch", [])]
        mergers = [MergerEvent.from_dict(m) for m in data.get("mergers", [])]
        return cls(
            galaxy_id=data["galaxy_id"],
            main_branch=main_branch,
            mergers=mergers,
            spline_trajectory=data.get("spline_trajectory", []),
            provenance=data.get("provenance", {}),
            version=version,
        )

    @classmethod
    def from_json(cls, json_str: str) -> EvolutionaryTrackContract:
        return cls.from_dict(json.loads(json_str))
