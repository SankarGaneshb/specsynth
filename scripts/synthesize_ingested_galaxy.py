#!/usr/bin/env python3
"""
scripts.synthesize_ingested_galaxy
==================================
Path C: Synthesize spectra and predict JWST NIRCam photometry for any ingested galaxy.
Links the 3D star particles directly to the FSPS stellar population synthesis matrix (S = SFH . SSP).

Usage:
    python scripts/synthesize_ingested_galaxy.py [--name GALAXY_NAME] [--redshift Z]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

# Auto-re-exec into .venv if run with system python
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

from specsynth.adapters.fsps import FSPSAdapter
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
from specsynth.filters import get_filter
from specsynth.simulation import load_simulation_snapshot

C_ANG_S = 2.99792458e18  # Speed of light in Angstrom / s
TARGET_FILTERS = [
    "jwst_f090w",
    "jwst_f150w",
    "jwst_f200w",
    "jwst_f277w",
    "jwst_f356w",
    "jwst_f444w",
]


def synthesize_galaxy(galaxy_name: str = "MyGalaxy", redshift: float = 0.5) -> None:
    print(f"\n{'=' * 75}")
    print(f"  Specsynth Spectral Synthesis (Path C) for '{galaxy_name}'")
    print(f"{'=' * 75}")

    model_path = repo_root / "sample_models" / "3d" / f"{galaxy_name}_web.json"
    if not model_path.exists():
        # Fallback to TNG reference subhalo
        model_path = repo_root / "sample_models" / "3d" / "tng100_subhalo_009873_web.json"
        galaxy_name = "tng100_subhalo_009873"

    print(f"[1/4] Loading 3D galaxy particles from: {model_path.name}")
    galaxy = load_simulation_snapshot(model_path, galaxy_id=galaxy_name, redshift=redshift)
    m_star = galaxy.total_stellar_mass_msun()
    print(f"      Total Stellar Mass: {m_star:.2e} M_sun")
    print(f"      Half-Mass Radius  : {galaxy.half_mass_radius_kpc:.2f} kpc")
    print(f"      Cosmic Redshift z : {redshift:.3f}")

    print("\n[2/4] Loading FSPS Stellar Population Synthesis (SSP) Grid:")
    fsps_path = repo_root / "sample_models" / "fsps" / "fsps_full_chabrier_mist.spec"
    adapter = FSPSAdapter(filepath=fsps_path)
    ssp_contract = adapter.to_contract()
    print(f"      Source Engine     : {ssp_contract.source_engine} ({ssp_contract.imf}, {ssp_contract.isochrones})")
    print(f"      Ages x Mets       : {len(ssp_contract.ages_yr)} ages x {len(ssp_contract.mets_z)} metallicities ({len(ssp_contract.ages_yr) * len(ssp_contract.mets_z)} grid points)")
    print(f"      Wavelength Bins   : {len(ssp_contract.wave_angstrom):,} bins ({ssp_contract.wave_angstrom[0]:.0f} Å to {ssp_contract.wave_angstrom[-1]:.0f} Å)")

    print("\n[3/4] Binning 3D star particles into Non-Parametric SFH Matrix:")
    sfh = galaxy.extract_non_parametric_sfh(ssp_contract.ages_yr, ssp_contract.mets_z, formed_mass=True)
    m_formed = float(np.sum(sfh))
    print(f"      Formed Stellar Mass: {m_formed:.2e} M_sun (accounting for stellar evolution mass loss)")
    print(f"      Surviving Fraction : {m_star / m_formed:.1%}")

    print("\n[4/4] Matrix Contraction (S = SFH · SSP) & JWST Filter Projection:")
    # Matrix contraction: S = SFH @ SSP_grid
    spec_rest = (sfh @ ssp_contract.ssp_flux_2d)[0]  # Shape: (N_wave,) in L_sun / Å

    # Load 6 JWST NIRCam filter bandpasses
    filter_data = []
    filter_pivots = {}
    for fname in TARGET_FILTERS:
        flt = get_filter(fname)
        norm = np.trapezoid(flt.transmission * flt.wave, flt.wave)
        filter_data.append((fname, flt.wave, flt.transmission, norm))
        filter_pivots[fname] = float(flt.pivot_wavelength)

    # Project rest-frame spectrum through cosmology, IGM, and filters
    phot_chunk = project_per_galaxy_photometry_chunk(
        spec_rest[None, :],
        np.array([redshift], dtype=np.float32),
        ssp_contract.wave_angstrom,
        filter_data,
        apply_igm=True,
        distance_dimming=True,
        input_units="lsun",
        cosmo=TNG_COSMOLOGY,
    )[0]

    # Display results table
    print(f"\n{'-' * 75}")
    print(f"  JWST NIRCam Synthetic Photometry for '{galaxy_name}' at z = {redshift:.2f}")
    print(f"{'-' * 75}")
    print(f"  {'Filter Band':<16} {'Pivot λ (Å)':<14} {'Flux (μJy)':<16} {'AB Magnitude':<14}")
    print(f"{'-' * 75}")

    for i, fname in enumerate(TARGET_FILTERS):
        f_lam = float(phot_chunk[i])
        pivot = filter_pivots[fname]
        f_nu = f_lam * (pivot ** 2) / C_ANG_S  # erg / s / cm^2 / Hz
        f_ujy = f_nu * 1e29                    # microJanskys
        mag = -2.5 * math.log10(f_nu) - 48.60 if f_nu > 0 else 99.0
        print(f"  {fname:<16} {pivot:<14.1f} {f_ujy:<16.3f} {mag:<14.3f}")

    print(f"{'-' * 75}")
    print("\n[SUCCESS] 3D star particles successfully synthesized into observable JWST photometry!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthesize SED and JWST photometry from ingested 3D galaxy")
    parser.add_argument("--name", default="MyGalaxy", help="Galaxy Name / ID (default: MyGalaxy)")
    parser.add_argument("--redshift", type=float, default=0.5, help="Redshift z (default: 0.5)")

    args = parser.parse_args()
    synthesize_galaxy(galaxy_name=args.name, redshift=args.redshift)
