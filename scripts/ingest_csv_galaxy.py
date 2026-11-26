#!/usr/bin/env python3
"""
Simple 1-Command Galaxy Ingestion Script
=======================================
Reads a plain CSV or text file containing star particles,
automatically centers and aligns the galaxy, and outputs
a 3D model ready for visualization and spectral synthesis.

Usage:
    python scripts/ingest_csv_galaxy.py [csv_path] [--name GALAXY_NAME] [--redshift Z]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Auto-re-exec into .venv if running via global python
if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
    repo_root = Path(__file__).resolve().parent.parent
    venv_python_win = repo_root / ".venv" / "Scripts" / "python.exe"
    venv_python_posix = repo_root / ".venv" / "bin" / "python"
    venv_py = venv_python_win if venv_python_win.exists() else venv_python_posix

    if venv_py.exists() and str(venv_py) != sys.executable:
        os.execv(str(venv_py), [str(venv_py)] + sys.argv)

import numpy as np

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from specsynth.contracts.galaxy3d import (
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
)
from specsynth.simulation import export_galaxy3d_web_json


def ingest_csv_galaxy(csv_path: str, galaxy_name: str = "MyCustomGalaxy", redshift: float = 0.5) -> Path:
    file_path = Path(csv_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"\n[1/3] Reading star particles from: {file_path.name}")

    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        # Filter comments
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        reader = csv.DictReader(lines)
        for r in reader:
            rows.append(r)

    if not rows:
        raise ValueError(f"No data rows found in {file_path}")

    # Helper to find column matching any alias
    def get_val(row, *aliases, default=0.0):
        for a in aliases:
            for k in row:
                if a in k.lower():
                    try:
                        return float(row[k])
                    except (ValueError, TypeError):
                        pass
        return default

    coords_list = []
    masses_list = []
    ages_list = []
    mets_list = []

    for r in rows:
        x = get_val(r, "x_kpc", "x", "pos_x")
        y = get_val(r, "y_kpc", "y", "pos_y")
        z = get_val(r, "z_kpc", "z", "pos_z")
        m = get_val(r, "mass_msun", "mass", "m_star", "m", default=1.0e4)
        age = get_val(r, "age_yr", "age", "t_age", "t", default=2.0e9)
        met = get_val(r, "metallicity_z", "metallicity", "metal", "z_met", default=0.019)

        coords_list.append([x, y, z])
        masses_list.append(m)
        ages_list.append(age)
        mets_list.append(met)

    coords = np.asarray(coords_list, dtype=np.float32)
    masses = np.asarray(masses_list, dtype=np.float32)
    ages = np.asarray(ages_list, dtype=np.float32)
    mets = np.asarray(mets_list, dtype=np.float32)
    vels = np.zeros_like(coords, dtype=np.float32)

    n_particles = len(coords)
    print(f"      Loaded {n_particles:,} star particles.")
    print(f"      Total Mass: {float(np.sum(masses)):.2e} M_sun")

    print("\n[2/3] Processing astrodynamics:")
    print("      - Shifting center of mass to (0, 0, 0) kpc")
    print("      - Computing stellar half-mass radius r_1/2")

    star_batch = ParticleBatchContract(
        particle_type=ParticleType.STAR,
        coordinates_kpc=coords,
        velocities_km_s=vels,
        masses_msun=masses,
        ages_yr=ages,
        metallicities_z=mets,
    )

    galaxy = Galaxy3DContract.from_particles(
        galaxy_id=galaxy_name,
        redshift=redshift,
        components={"star": star_batch},
        geometry_source=GeometrySource.SIMULATION_DERIVED,
        align_angular_momentum=False,  # No velocities required from plain CSV
        provenance={"source_csv": file_path.name},
    )

    print(f"      - Half-mass radius r_1/2: {galaxy.half_mass_radius_kpc:.2f} kpc")

    out_dir = repo_root / "sample_models" / "3d"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{galaxy_name}_web.json"

    print(f"\n[3/3] Exporting 3D WebGL model to: {out_file.relative_to(repo_root)}")
    export_galaxy3d_web_json(galaxy, out_file, max_particles_per_component=5000)

    print("\n[DONE] Successfully ingested and generated 3D galaxy model!")
    print(f"       File ready: {out_file}")
    return out_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a CSV galaxy into Specsynth 3D model")
    parser.add_argument("csv_path", nargs="?", default="sample_models/my_galaxy_template.csv", help="Path to CSV file")
    parser.add_argument("--name", default="MyGalaxy", help="Galaxy Name / ID")
    parser.add_argument("--redshift", type=float, default=0.5, help="Redshift z (default: 0.5)")

    args = parser.parse_args()
    ingest_csv_galaxy(args.csv_path, galaxy_name=args.name, redshift=args.redshift)
