"""
scripts.export_tng_3d_galaxy
============================
Generate and export reference 3D galaxy benchmark model for IllustrisTNG subhalo
tng100_subhalo_009873 into sample_models/3d/.
Generates:
  1. Standard HDF5 snapshot (subhalo_009873.hdf5)
  2. WebGL 60 FPS JSON for PerandamΨ (subhalo_009873_web.json)
  3. Linked 3D-photometry metadata manifest (subhalo_009873_manifest.json)
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from specsynth.contracts.galaxy3d import ParticleType
from specsynth.simulation import (
    export_galaxy3d_hdf5,
    export_galaxy3d_web_json,
    generate_mock_simulation_snapshot,
)


def export_reference_tng_3d() -> None:
    output_dir = Path("sample_models/3d")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating reference 3D galaxy model for tng100_subhalo_009873...")
    galaxy = generate_mock_simulation_snapshot(
        galaxy_id="tng100_subhalo_009873",
        redshift=0.0,
        n_stars=12000,
        n_gas=4000,
        n_dm=6000,
        total_stellar_mass_msun=1.84e10,
        seed=9873,
    )

    # 1. Export HDF5 snapshot
    h5_path = output_dir / "tng100_subhalo_009873.hdf5"
    print(f"Exporting HDF5 snapshot to {h5_path}...")
    export_galaxy3d_hdf5(galaxy, h5_path)

    # 2. Export WebGL JSON (decimated to 5,000 particles for high-performance 60 FPS)
    web_path = output_dir / "tng100_subhalo_009873_web.json"
    print(f"Exporting WebGL 3D JSON to {web_path}...")
    export_galaxy3d_web_json(galaxy, web_path, max_particles_per_component=5000, seed=42)

    # 3. Export Linked Manifest linking 3D geometry to Milestone 2 photometry
    manifest_path = output_dir / "tng100_subhalo_009873_manifest.json"
    print(f"Writing linked manifest to {manifest_path}...")

    manifest = {
        "version": "1.0.0",
        "galaxy_id": galaxy.galaxy_id,
        "geometry_source": galaxy.geometry_source.value,
        "coordinate_frame": galaxy.coordinate_frame.value,
        "redshift": galaxy.redshift,
        "center_of_mass_kpc": list(galaxy.center_of_mass_kpc),
        "half_mass_radius_kpc": galaxy.half_mass_radius_kpc,
        "total_stellar_mass_msun": galaxy.total_stellar_mass_msun(),
        "particle_counts": {
            k: len(v.masses_msun) for k, v in galaxy.components.items()
        },
        "linked_files": {
            "hdf5_snapshot": str(h5_path.relative_to(Path("."))),
            "webgl_json": str(web_path.relative_to(Path("."))),
            "photometry_manifest": "tests/test_validation_galaxy_benchmark.py",
        },
        "provenance": galaxy.provenance,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n[SUCCESS] Reference 3D model generated successfully:")
    print(f"  - Total Stellar Mass: {galaxy.total_stellar_mass_msun():.2e} M_sun")
    print(f"  - Half-Mass Radius:   {galaxy.half_mass_radius_kpc:.2f} kpc")
    print(f"  - Particles (Stars):  {len(galaxy.components[ParticleType.STAR.value].masses_msun):,}")
    print(f"  - Particles (Gas):    {len(galaxy.components[ParticleType.GAS.value].masses_msun):,}")
    print(f"  - Particles (DM):     {len(galaxy.components[ParticleType.DARK_MATTER.value].masses_msun):,}")


if __name__ == "__main__":
    export_reference_tng_3d()
