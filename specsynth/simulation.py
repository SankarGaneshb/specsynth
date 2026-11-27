"""
specsynth.simulation
====================
Simulation snapshot ingestion, HDF5/parquet loader, particle kinematics & coordinate conversions,
and empirical 3D galaxy model generation.
Enforces Milestone 3 (P2.M3.2 & P2.M3.3) standards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union
import numpy as np

from specsynth.contracts.galaxy3d import (
    CoordinateFrame,
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
)
from specsynth.cosmology import (
    FlatLambdaCDM,
    TNG_COSMOLOGY,
    get_cosmology,
)
from specsynth.transforms import (
    comoving_to_physical_kpc,
)


def load_simulation_snapshot(
    source: Union[str, Path, dict[str, Any]],
    sim_type: str = "tng",
    galaxy_id: Optional[str] = None,
    subhalo_id: Optional[Union[int, str]] = None,
    h: Optional[float] = None,
    redshift: Optional[float] = None,
    cosmo: Optional[FlatLambdaCDM] = None,
    align_angular_momentum: bool = True,
) -> Galaxy3DContract:
    """
    Ingest a cosmological simulation snapshot or subhalo cutout into a validated Galaxy3DContract.

    Supports:
      1. HDF5 files (.hdf5, .h5) with standard Gadget/Arepo/TNG/EAGLE particle groups:
         PartType0 (Gas), PartType1 (DM), PartType4 (Stars), PartType5 (Black Holes).
      2. In-memory dictionary representation for testing and custom pipelines.

    Coordinate Transformation Pipeline:
      - Coordinates: comoving ckpc/h -> physical kpc (r_phys = r_comov / ((1 + z) * h)).
      - Velocities: peculiar velocities in km/s (corrected for scale factor sqrt(a) if Gadget).
      - Masses: 10^10 M_sun/h -> solar masses M_sun (mass_msun = mass * 1e10 / h).
      - Star Ages: derived from stellar birth scale factor a_form using exact cosmic time.
      - Center of Mass & Disk Alignment: coordinates shifted to CoM and rotated to align J with +Z.
    """
    cosmology = cosmo or TNG_COSMOLOGY

    if isinstance(source, dict):
        return _parse_snapshot_dict(
            source,
            sim_type=sim_type,
            galaxy_id=galaxy_id or "sim_galaxy_dict",
            subhalo_id=subhalo_id,
            h=h,
            redshift=redshift,
            cosmo=cosmology,
            align_angular_momentum=align_angular_momentum,
        )

    file_path = Path(source)
    if not file_path.exists():
        raise FileNotFoundError(f"Simulation snapshot file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix in [".hdf5", ".h5"]:
        return _load_hdf5_snapshot(
            file_path,
            sim_type=sim_type,
            galaxy_id=galaxy_id or file_path.stem,
            subhalo_id=subhalo_id,
            h=h,
            redshift=redshift,
            cosmo=cosmology,
            align_angular_momentum=align_angular_momentum,
        )
    elif suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _parse_snapshot_dict(
            data,
            sim_type=sim_type,
            galaxy_id=galaxy_id or file_path.stem,
            subhalo_id=subhalo_id,
            h=h,
            redshift=redshift,
            cosmo=cosmology,
            align_angular_momentum=align_angular_momentum,
        )
    else:
        raise ValueError(f"Unsupported snapshot format '{suffix}'. Supported: .hdf5, .h5, .json")


def _load_hdf5_snapshot(
    filepath: Path,
    sim_type: str,
    galaxy_id: str,
    subhalo_id: Optional[Union[int, str]],
    h: Optional[float],
    redshift: Optional[float],
    cosmo: FlatLambdaCDM,
    align_angular_momentum: bool,
) -> Galaxy3DContract:
    """Load and parse an HDF5 simulation snapshot using h5py with strict unit validation."""
    try:
        import h5py
    except ImportError as e:
        raise ImportError(
            "h5py is required to read HDF5 simulation snapshots. "
            "Please install it via 'pip install h5py'."
        ) from e

    with h5py.File(filepath, "r") as f:
        # Read Header metadata
        header = f.get("Header")
        snap_z = float(redshift) if redshift is not None else None
        snap_h = float(h) if h is not None else None
        snap_box = 0.0
        mass_table = None
        datasets_consumed: list[str] = []

        if header is not None:
            attrs = header.attrs
            if "Redshift" in attrs and snap_z is None:
                snap_z = float(attrs["Redshift"])
            if "HubbleParam" in attrs and snap_h is None:
                snap_h = float(attrs["HubbleParam"])
            elif "h" in attrs and snap_h is None:
                snap_h = float(attrs["h"])
            if "BoxSize" in attrs:
                snap_box = float(attrs["BoxSize"])
            if "MassTable" in attrs:
                mass_table = attrs["MassTable"]

        # Reject missing or ambiguous cosmological unit parameters
        if snap_h is None or snap_h <= 0.0:
            raise ValueError(
                f"Missing cosmological parameter 'h' in {filepath.name}. "
                "Hubble parameter h must be present in snapshot Header or explicitly provided."
            )
        if snap_z is None or snap_z < 0.0:
            raise ValueError(
                f"Missing cosmological parameter 'redshift' in {filepath.name}. "
                "Redshift z >= 0 must be present in snapshot Header or explicitly provided."
            )

        # Mapping of HDF5 group names to ParticleType
        type_mapping = {
            "PartType0": (ParticleType.GAS, 0),
            "PartType1": (ParticleType.DARK_MATTER, 1),
            "PartType4": (ParticleType.STAR, 4),
            "PartType5": (ParticleType.BLACK_HOLE, 5),
        }

        components: dict[str, ParticleBatchContract] = {}

        # Scale factor a = 1 / (1 + z)
        a_snap = 1.0 / (1.0 + snap_z)
        t_snap_gyr = cosmo.cosmic_time_gyr(snap_z)

        for p_key, (p_enum, p_idx) in type_mapping.items():
            if p_key not in f:
                continue

            grp = f[p_key]
            if "Coordinates" not in grp:
                continue

            coords_raw = np.asarray(grp["Coordinates"], dtype=np.float32)
            if len(coords_raw) == 0:
                continue
            datasets_consumed.append(f"{p_key}/Coordinates")

            # Convert ckpc/h to physical kpc
            coords_kpc = comoving_to_physical_kpc(coords_raw, redshift=snap_z, h=snap_h)

            # Velocities: in Gadget/TNG, velocities are v_code = v_pec * sqrt(a)
            if "Velocities" in grp:
                vels_raw = np.asarray(grp["Velocities"], dtype=np.float32)
                vels_km_s = (vels_raw * np.sqrt(a_snap)).astype(np.float32)
                datasets_consumed.append(f"{p_key}/Velocities")
            else:
                vels_km_s = np.zeros_like(coords_kpc, dtype=np.float32)

            # Masses: in Gadget/TNG, masses are in 10^10 M_sun / h
            if "Masses" in grp:
                masses_raw = np.asarray(grp["Masses"], dtype=np.float32)
                masses_msun = (masses_raw * (1e10 / snap_h)).astype(np.float32)
                datasets_consumed.append(f"{p_key}/Masses")
            elif mass_table is not None and len(mass_table) > p_idx and mass_table[p_idx] > 0:
                m_code = float(mass_table[p_idx])
                masses_msun = np.full(len(coords_kpc), m_code * (1e10 / snap_h), dtype=np.float32)
                datasets_consumed.append("Header/MassTable")
            else:
                raise ValueError(
                    f"Missing particle mass dataset 'Masses' in {p_key} and no Header MassTable entry."
                )

            # Particle IDs
            p_ids: Optional[np.ndarray] = None
            if "ParticleIDs" in grp:
                p_ids = np.asarray(grp["ParticleIDs"], dtype=np.uint64)
                datasets_consumed.append(f"{p_key}/ParticleIDs")

            ages_yr: Optional[np.ndarray] = None
            mets_z: Optional[np.ndarray] = None
            smoothing_kpc: Optional[np.ndarray] = None

            if p_enum == ParticleType.STAR:
                # GFM_StellarFormationTime is birth scale factor a_birth (positive for real stars, < 0 for wind)
                if "GFM_StellarFormationTime" in grp:
                    a_birth = np.asarray(grp["GFM_StellarFormationTime"], dtype=np.float32)
                    valid_mask = a_birth > 0.0
                    datasets_consumed.append(f"{p_key}/GFM_StellarFormationTime")
                    if not np.all(valid_mask):
                        coords_kpc = coords_kpc[valid_mask]
                        vels_km_s = vels_km_s[valid_mask]
                        masses_msun = masses_msun[valid_mask]
                        a_birth = a_birth[valid_mask]
                        if p_ids is not None:
                            p_ids = p_ids[valid_mask]

                    # Redshift of formation
                    z_birth = np.maximum(0.0, (1.0 / a_birth) - 1.0)
                    t_birth_gyr = cosmo.cosmic_time_gyr(z_birth)
                    # Stellar age = t(z_snap) - t(z_birth)
                    age_gyr = np.maximum(0.001, t_snap_gyr - t_birth_gyr)
                    ages_yr = (age_gyr * 1e9).astype(np.float32)
                else:
                    ages_yr = np.full(len(coords_kpc), 2.0e9, dtype=np.float32)

                if "GFM_Metallicity" in grp:
                    mets_raw = np.asarray(grp["GFM_Metallicity"], dtype=np.float32)
                    mets_z = np.clip(mets_raw, 1e-5, 0.1).astype(np.float32)
                    datasets_consumed.append(f"{p_key}/GFM_Metallicity")
                else:
                    mets_z = np.full(len(coords_kpc), 0.019, dtype=np.float32)

            elif p_enum == ParticleType.GAS:
                if "SmoothingLength" in grp:
                    h_raw = np.asarray(grp["SmoothingLength"], dtype=np.float32)
                    smoothing_kpc = (h_raw / ((1.0 + snap_z) * snap_h)).astype(np.float32)
                    datasets_consumed.append(f"{p_key}/SmoothingLength")

            components[p_enum.value] = ParticleBatchContract(
                particle_type=p_enum,
                coordinates_kpc=coords_kpc,
                velocities_km_s=vels_km_s,
                masses_msun=masses_msun,
                ages_yr=ages_yr,
                metallicities_z=mets_z,
                smoothing_lengths_kpc=smoothing_kpc,
                particle_ids=p_ids,
            )

        provenance = {
            "source_file": str(filepath.name),
            "sim_type": sim_type,
            "subhalo_id": subhalo_id,
            "redshift": snap_z,
            "h": snap_h,
            "box_size_ckpc": snap_box,
            "datasets_consumed": datasets_consumed,
            "particle_ids_preserved": any(c.particle_ids is not None for c in components.values()),
            "geometry_source": GeometrySource.SIMULATION_DERIVED.value,
            "unit_conversions": {
                "coordinates": "comoving ckpc/h -> physical kpc via r_phys = r_comov * a / h",
                "velocities": "v_pec * sqrt(a) -> km/s via v_phys = v_code * sqrt(a)",
                "masses": "10^10 M_sun / h -> M_sun via M_phys = M_code * 1e10 / h",
                "stellar_ages": "cosmic_time(z_snap) - cosmic_time(z_birth) via a_birth",
            },
        }

        return Galaxy3DContract.from_particles(
            galaxy_id=galaxy_id,
            redshift=snap_z,
            components=components,
            geometry_source=GeometrySource.SIMULATION_DERIVED,
            align_angular_momentum=align_angular_momentum,
            provenance=provenance,
        )


def _parse_snapshot_dict(
    data: dict[str, Any],
    sim_type: str,
    galaxy_id: str,
    subhalo_id: Optional[Union[int, str]],
    h: float,
    redshift: Optional[float],
    cosmo: FlatLambdaCDM,
    align_angular_momentum: bool,
) -> Galaxy3DContract:
    """Parse dictionary structure containing components or particle batches."""
    snap_z = float(redshift if redshift is not None else data.get("redshift", 0.0))
    snap_h = float(h if h != 0.6774 else data.get("h", 0.6774))

    components: dict[str, ParticleBatchContract] = {}
    comps_in = data.get("components") or data.get("particles", {})

    for comp_key, comp_data in comps_in.items():
        try:
            ptype = ParticleType(comp_data.get("particle_type", comp_key))
        except ValueError:
            ptype = ParticleType.STAR if "star" in comp_key.lower() else ParticleType.GAS

        coords = np.asarray(comp_data["coordinates_kpc"], dtype=np.float32)
        vels = np.asarray(comp_data.get("velocities_km_s", np.zeros_like(coords)), dtype=np.float32)
        masses = np.asarray(comp_data.get("masses_msun", np.ones(len(coords)) * 1e5), dtype=np.float32)

        ages = np.asarray(comp_data["ages_yr"], dtype=np.float32) if "ages_yr" in comp_data else None
        mets = np.asarray(comp_data["metallicities_z"], dtype=np.float32) if "metallicities_z" in comp_data else None
        smoothing = np.asarray(comp_data["smoothing_lengths_kpc"], dtype=np.float32) if "smoothing_lengths_kpc" in comp_data else None
        p_ids = np.asarray(comp_data["particle_ids"], dtype=np.uint64) if "particle_ids" in comp_data else None

        components[ptype.value] = ParticleBatchContract(
            particle_type=ptype,
            coordinates_kpc=coords,
            velocities_km_s=vels,
            masses_msun=masses,
            ages_yr=ages,
            metallicities_z=mets,
            smoothing_lengths_kpc=smoothing,
            particle_ids=p_ids,
        )

    geom_source_raw = data.get("geometry_source", GeometrySource.SIMULATION_DERIVED.value)
    try:
        geom_source = GeometrySource(geom_source_raw)
    except ValueError:
        geom_source = GeometrySource.SIMULATION_DERIVED

    prov = data.get("provenance", {})
    prov.update({
        "sim_type": sim_type,
        "subhalo_id": subhalo_id or data.get("subhalo_id"),
        "redshift": snap_z,
        "h": snap_h,
        "geometry_source": geom_source.value,
    })

    return Galaxy3DContract.from_particles(
        galaxy_id=galaxy_id or data.get("galaxy_id", "galaxy_3d"),
        redshift=snap_z,
        components=components,
        geometry_source=geom_source,
        align_angular_momentum=align_angular_momentum,
        provenance=prov,
    )


def generate_mock_simulation_snapshot(
    galaxy_id: str = "mock_procedural_specimen",
    redshift: float = 0.0,
    n_stars: int = 8000,
    n_gas: int = 2500,
    n_dm: int = 4000,
    total_stellar_mass_msun: float = 1.8e10,
    seed: int = 42,
) -> Galaxy3DContract:
    """
    Generate an illustrative procedural mock 3D galaxy benchmark model for rapid unit testing,
    visual calibration, and WebGL rendering benchmarking.

    NOTE: This is a procedural mathematical mock (Hernquist bulge + exponential disk + NFW halo)
    and is strictly labeled as GeometrySource.PROCEDURAL_ILLUSTRATIVE. It is not an empirical
    simulation snapshot extraction.
    """
    rng = np.random.default_rng(seed)

    # ---------------- 1. Star Particles ----------------
    n_bulge = int(n_stars * 0.3)
    n_disk = n_stars - n_bulge

    # Bulge: Hernquist profile r = a * sqrt(u) / (1 - sqrt(u))
    a_bulge = 0.8  # kpc
    u_bulge = rng.uniform(0.01, 0.95, size=n_bulge)
    r_bulge = a_bulge * np.sqrt(u_bulge) / (1.0 - np.sqrt(u_bulge))
    costheta_b = rng.uniform(-1.0, 1.0, size=n_bulge)
    phi_b = rng.uniform(0.0, 2.0 * np.pi, size=n_bulge)
    sintheta_b = np.sqrt(1.0 - costheta_b**2)

    x_b = r_bulge * sintheta_b * np.cos(phi_b)
    y_b = r_bulge * sintheta_b * np.sin(phi_b)
    z_b = r_bulge * costheta_b
    coords_b = np.stack([x_b, y_b, z_b], axis=-1)

    # Bulge isotropic velocity dispersion
    sigma_b = 110.0  # km/s
    vels_b = rng.normal(0.0, sigma_b, size=(n_bulge, 3))

    # Bulge ages & metallicities: old & metal-rich
    ages_b = rng.uniform(6.0e9, 10.5e9, size=n_bulge)
    mets_b = np.clip(rng.normal(0.024, 0.004, size=n_bulge), 0.015, 0.04)

    # Disk: Exponential in R, sech^2 in z
    r_disk_scale = 3.2  # kpc
    z_disk_scale = 0.35  # kpc
    r_disk = rng.exponential(scale=r_disk_scale, size=n_disk)
    phi_d = rng.uniform(0.0, 2.0 * np.pi, size=n_disk)
    # sech^2 distribution: z = z_d * atanh(2u - 1)
    u_z = rng.uniform(0.02, 0.98, size=n_disk)
    z_d = z_disk_scale * np.arctanh(2.0 * u_z - 1.0)

    x_d = r_disk * np.cos(phi_d)
    y_d = r_disk * np.sin(phi_d)
    coords_d = np.stack([x_d, y_d, z_d], axis=-1)

    # Disk rotation curve: v_circ = v_max * R / sqrt(R^2 + R_c^2)
    v_max = 210.0  # km/s
    r_core = 1.5  # kpc
    v_circ = v_max * r_disk / np.sqrt(r_disk**2 + r_core**2)
    # Add azimuthal rotation
    vx_d = -v_circ * np.sin(phi_d) + rng.normal(0.0, 22.0, size=n_disk)
    vy_d = v_circ * np.cos(phi_d) + rng.normal(0.0, 22.0, size=n_disk)
    vz_d = rng.normal(0.0, 18.0, size=n_disk)
    vels_d = np.stack([vx_d, vy_d, vz_d], axis=-1)

    # Disk ages & metallicities: younger in disk, radial metallicity gradient
    ages_d = rng.uniform(0.1e9, 5.5e9, size=n_disk)
    # Z(R) = Z_0 * 10^(-0.04 * R)
    z_gradient = 0.022 * (10.0 ** (-0.035 * r_disk))
    mets_d = np.clip(rng.normal(z_gradient, 0.003), 0.004, 0.035)

    # Combine stars
    coords_stars = np.concatenate([coords_b, coords_d], axis=0).astype(np.float32)
    vels_stars = np.concatenate([vels_b, vels_d], axis=0).astype(np.float32)
    ages_stars = np.concatenate([ages_b, ages_d], axis=0).astype(np.float32)
    mets_stars = np.concatenate([mets_b, mets_d], axis=0).astype(np.float32)

    # Masses: equal partition of total stellar mass
    m_star_particle = total_stellar_mass_msun / n_stars
    masses_stars = np.full(n_stars, m_star_particle, dtype=np.float32)

    # ---------------- 2. Gas Particles ----------------
    r_gas = rng.exponential(scale=4.5, size=n_gas)
    phi_g = rng.uniform(0.0, 2.0 * np.pi, size=n_gas)
    z_g = rng.normal(0.0, 0.2, size=n_gas)
    coords_gas = np.stack([r_gas * np.cos(phi_g), r_gas * np.sin(phi_g), z_g], axis=-1).astype(np.float32)

    v_circ_g = v_max * r_gas / np.sqrt(r_gas**2 + r_core**2)
    vx_g = -v_circ_g * np.sin(phi_g) + rng.normal(0.0, 10.0, size=n_gas)
    vy_g = v_circ_g * np.cos(phi_g) + rng.normal(0.0, 10.0, size=n_gas)
    vz_g = rng.normal(0.0, 8.0, size=n_gas)
    vels_gas = np.stack([vx_g, vy_g, vz_g], axis=-1).astype(np.float32)

    mass_gas = (total_stellar_mass_msun * 0.25) / n_gas
    masses_gas = np.full(n_gas, mass_gas, dtype=np.float32)
    smoothing_gas = np.clip(0.3 + 0.1 * r_gas, 0.1, 2.0).astype(np.float32)

    # ---------------- 3. Dark Matter Particles ----------------
    # NFW halo
    r_s = 18.0  # kpc
    u_dm = rng.uniform(0.01, 0.95, size=n_dm)
    r_dm = r_s * (u_dm / (1.0 - u_dm)) ** 0.5
    costheta_dm = rng.uniform(-1.0, 1.0, size=n_dm)
    phi_dm = rng.uniform(0.0, 2.0 * np.pi, size=n_dm)
    sintheta_dm = np.sqrt(1.0 - costheta_dm**2)

    coords_dm = np.stack([
        r_dm * sintheta_dm * np.cos(phi_dm),
        r_dm * sintheta_dm * np.sin(phi_dm),
        r_dm * costheta_dm,
    ], axis=-1).astype(np.float32)
    vels_dm = rng.normal(0.0, 160.0, size=(n_dm, 3)).astype(np.float32)
    mass_dm = (total_stellar_mass_msun * 10.0) / n_dm
    masses_dm = np.full(n_dm, mass_dm, dtype=np.float32)

    # Assemble components
    components = {
        ParticleType.STAR.value: ParticleBatchContract(
            particle_type=ParticleType.STAR,
            coordinates_kpc=coords_stars,
            velocities_km_s=vels_stars,
            masses_msun=masses_stars,
            ages_yr=ages_stars,
            metallicities_z=mets_stars,
        ),
        ParticleType.GAS.value: ParticleBatchContract(
            particle_type=ParticleType.GAS,
            coordinates_kpc=coords_gas,
            velocities_km_s=vels_gas,
            masses_msun=masses_gas,
            smoothing_lengths_kpc=smoothing_gas,
        ),
        ParticleType.DARK_MATTER.value: ParticleBatchContract(
            particle_type=ParticleType.DARK_MATTER,
            coordinates_kpc=coords_dm,
            velocities_km_s=vels_dm,
            masses_msun=masses_dm,
        ),
    }

    provenance = {
        "generator": "specsynth.simulation.generate_mock_simulation_snapshot",
        "model_type": "analytical_hernquist_exponential_disk_nfw_mock",
        "simulation": "Procedural Mock (Not Simulation Derived)",
        "snapshot": None,
        "subhalo_id": None,
        "redshift": float(redshift),
        "total_stellar_mass_msun": float(total_stellar_mass_msun),
        "kinematics": "aligned_angular_momentum",
        "seed": seed,
        "geometry_source": GeometrySource.PROCEDURAL_ILLUSTRATIVE.value,
    }

    return Galaxy3DContract.from_particles(
        galaxy_id=galaxy_id,
        redshift=redshift,
        components=components,
        geometry_source=GeometrySource.PROCEDURAL_ILLUSTRATIVE,
        align_angular_momentum=True,
        provenance=provenance,
    )


def export_galaxy3d_hdf5(galaxy: Galaxy3DContract, filepath: Union[str, Path]) -> Path:
    """
    Export a Galaxy3DContract to standard HDF5 snapshot format compatible with
    astrophysical analysis tools (yt, pynbody, gadget, arepo).
    """
    try:
        import h5py
    except ImportError as e:
        raise ImportError("h5py is required to export HDF5 snapshots.") from e

    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(out_path, "w") as f:
        # Header
        header = f.create_group("Header")
        header.attrs["Redshift"] = float(galaxy.redshift)
        header.attrs["Time"] = 1.0 / (1.0 + float(galaxy.redshift))
        header.attrs["HubbleParam"] = 0.6774
        header.attrs["BoxSize"] = 75000.0
        header.attrs["UnitLength_in_cm"] = 3.085678e21
        header.attrs["UnitMass_in_g"] = 1.989e43
        header.attrs["UnitVelocity_in_cm_per_s"] = 100000.0
        header.attrs["Flag_DoublePrecision"] = 0
        header.attrs["GalaxyID"] = str(galaxy.galaxy_id)
        header.attrs["HalfMassRadiusKpc"] = float(galaxy.half_mass_radius_kpc)
        header.attrs["TotalStellarMassMsun"] = float(galaxy.total_stellar_mass_msun())

        h = 0.6774
        scale_factor = 1.0 / (1.0 + float(galaxy.redshift))

        type_map = {
            ParticleType.GAS.value: "PartType0",
            ParticleType.DARK_MATTER.value: "PartType1",
            ParticleType.STAR.value: "PartType4",
            ParticleType.BLACK_HOLE.value: "PartType5",
        }

        for comp_name, comp_batch in galaxy.components.items():
            grp_name = type_map.get(comp_batch.particle_type.value, "PartType4")
            grp = f.create_group(grp_name)

            # Coordinates in ckpc/h: r_ckpc = r_phys * (1 + z) * h
            coords_ckpc = comp_batch.coordinates_kpc * ((1.0 + galaxy.redshift) * h)
            grp.create_dataset("Coordinates", data=coords_ckpc.astype(np.float32), compression="gzip")

            # Velocities in km/s / sqrt(a)
            vels_gadget = comp_batch.velocities_km_s / np.sqrt(scale_factor)
            grp.create_dataset("Velocities", data=vels_gadget.astype(np.float32), compression="gzip")

            # Masses in 10^10 M_sun / h
            masses_code = comp_batch.masses_msun / (1e10 / h)
            grp.create_dataset("Masses", data=masses_code.astype(np.float32), compression="gzip")

            # Particle IDs
            if comp_batch.particle_ids is not None:
                grp.create_dataset("ParticleIDs", data=comp_batch.particle_ids.astype(np.uint64), compression="gzip")

            if comp_batch.ages_yr is not None:
                # Convert age back to birth scale factor
                cosmo = TNG_COSMOLOGY
                t_snap_gyr = cosmo.cosmic_time_gyr(galaxy.redshift)
                t_birth_gyr = np.maximum(0.001, t_snap_gyr - (comp_batch.ages_yr / 1e9))
                # For Flat Lambda-CDM: z_birth
                # t_birth = (2 / (3 * H0 * sqrt(Ode))) * t_H * arcsinh(...)
                # Invert: a_birth = 1 / (1 + z_birth)
                # Compute lookup inversion
                z_eval = np.linspace(0.0, 20.0, 2000)
                t_eval = cosmo.cosmic_time_gyr(z_eval)
                z_birth = np.interp(t_birth_gyr, t_eval[::-1], z_eval[::-1])
                a_birth = 1.0 / (1.0 + z_birth)
                grp.create_dataset("GFM_StellarFormationTime", data=a_birth.astype(np.float32), compression="gzip")

            if comp_batch.metallicities_z is not None:
                grp.create_dataset("GFM_Metallicity", data=comp_batch.metallicities_z.astype(np.float32), compression="gzip")

            if comp_batch.smoothing_lengths_kpc is not None:
                h_code = comp_batch.smoothing_lengths_kpc * ((1.0 + galaxy.redshift) * h)
                grp.create_dataset("SmoothingLength", data=h_code.astype(np.float32), compression="gzip")

    return out_path


def export_galaxy3d_web_json(
    galaxy: Galaxy3DContract,
    filepath: Union[str, Path],
    max_particles_per_component: int = 5000,
    seed: int = 42,
) -> Path:
    """
    Export decimated 3D galaxy model to JSON for WebGL / PerandamΨ rendering.
    """
    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = galaxy.to_web_json(max_particles_per_component=max_particles_per_component, seed=seed)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)

    return out_path
