"""
specsynth.provenance
====================
Cryptographic provenance manifests, SHA-256 checksum tracking, and deterministic
reproducibility workflows for synthetic astrophysical observations.
Enforces P1.M2.8 and P1.M2.9 scientific reproducibility standards.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Mapping
import numpy as np


def hash_file(filepath: str | Path) -> str:
    """Compute the hexadecimal SHA-256 digest of a local file."""
    p = Path(filepath)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def hash_array(arr: np.ndarray) -> str:
    """Compute the hexadecimal SHA-256 digest of a contiguous NumPy array buffer."""
    contiguous = np.ascontiguousarray(arr)
    return hashlib.sha256(contiguous.view(np.uint8)).hexdigest()


def get_git_commit(repo_root: Path | None = None) -> str:
    """Retrieve the current Git commit SHA, or return 'unknown'."""
    try:
        root = repo_root or Path(__file__).resolve().parents[1]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out
    except Exception:
        return "unknown"


def generate_provenance_manifest(
    galaxy_id: str,
    simulation_name: str,
    redshift: float,
    physical_parameters: dict[str, float],
    engine_name: str,
    engine_version: str,
    grid_path: str | Path | None = None,
    is_genuine_engine: bool = True,
    dust_model: str = "charlot_fall_2000",
    igm_model: str = "madau_1995",
    cosmology: dict[str, float] | None = None,
    filter_checksums: dict[str, str] | None = None,
    photometry_results: dict[str, float] | None = None,
    dataset_type: str = "empirical_simulation",
) -> dict[str, Any]:
    """
    Construct a complete, cryptographically verifiable provenance manifest.

    Args:
        galaxy_id: Subhalo or galaxy identifier.
        simulation_name: Simulation dataset name (e.g. 'IllustrisTNG-100').
        redshift: Cosmological redshift z.
        physical_parameters: Dictionary of galaxy parameters (mass, sfr, metallicity, tau_d, tau_b).
        engine_name: SPS engine identifier (e.g. 'FSPS', 'BC03').
        engine_version: Version of the SPS engine.
        grid_path: Optional path to the raw input SSP grid file.
        is_genuine_engine: True if genuine SPS code; False if analytical proxy.
        dust_model: Dust attenuation prescription.
        igm_model: IGM transmission model.
        cosmology: Cosmological parameters (H0, Om0, Ol0).
        filter_checksums: Dict of {filter_name: sha256_hash}.
        photometry_results: Dict of {filter_name: ab_magnitude}.
        dataset_type: 'empirical_simulation' or 'analytical_mock'.

    Returns:
        Structured provenance dictionary conforming to Specsynth reproducibility standards.
    """
    grid_sha256 = hash_file(grid_path) if grid_path else ""
    git_sha = get_git_commit()
    cosmo = cosmology or {"H0": 67.74, "Om0": 0.3089, "Ol0": 0.6911}

    # Generate reproducible Python code snippet
    repro_code = f"""# SpecSynth Deterministic Reproduction Script
# Galaxy: {galaxy_id} (z = {redshift:.4f})
from specsynth.adapters.fsps import FSPSAdapter
from specsynth.cosmology import FlatLambdaCDM
from specsynth.contracts.photometry import SyntheticObservationContract

# 1. Cosmology
cosmo = FlatLambdaCDM(H0={cosmo['H0']}, Om0={cosmo['Om0']})

# 2. Physics & Engine: {engine_name} {engine_version}
# Input grid SHA-256: {grid_sha256}
print("Target Galaxy: {galaxy_id}, Log(M*/Msun) = {physical_parameters.get('log_mstar', 'N/A')}")
"""

    return {
        "manifest_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_sha,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "system": platform.system(),
        },
        "target": {
            "galaxy_id": galaxy_id,
            "simulation_name": simulation_name,
            "dataset_type": dataset_type,
            "redshift": redshift,
            "parameters": physical_parameters,
        },
        "sps_engine": {
            "name": engine_name,
            "version": engine_version,
            "is_genuine": is_genuine_engine,
            "grid_file": str(grid_path) if grid_path else None,
            "grid_sha256": grid_sha256,
        },
        "physics": {
            "dust_model": dust_model,
            "igm_model": igm_model,
            "cosmology": cosmo,
        },
        "filters": {
            "checksums": filter_checksums or {},
        },
        "photometry_summary": photometry_results or {},
        "reproducibility": {
            "code_snippet": repro_code,
        },
    }


def validate_provenance_manifest(manifest: dict[str, Any]) -> bool:
    """Verify that a provenance manifest contains all mandatory reproducibility fields."""
    mandatory_sections = ["manifest_version", "target", "sps_engine", "physics", "reproducibility"]
    for s in mandatory_sections:
        if s not in manifest:
            raise ValueError(f"Provenance manifest missing required section: '{s}'")

    target = manifest["target"]
    if not target.get("galaxy_id"):
        raise ValueError("Target galaxy_id cannot be empty in provenance manifest")

    return True
