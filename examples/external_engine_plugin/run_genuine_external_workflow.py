"""
End-to-End Genuine External SPS Engine Conformance & Forward-Modeling Workflow.
==============================================================================
Demonstrates the full scientific journey of an external astrophysicist plugging
an authentic SPS engine (Flexible Stellar Population Synthesis - FSPS v3.2)
into Specsynth with ZERO CORE MODIFICATIONS.

Scientific Pipeline:
1. Engine Discovery & Registration (Pillar 1: Entry points / runtime registry)
2. 11-Point Architectural & Scientific Conformance Certification
3. Canonical SSPGridContract (v1.0.0) Schema Verification
4. Delayed-Tau SFH Synthesis & Charlot & Fall (2000) Dust Attenuation
5. Cosmological Redshifting & FlatLambdaCDM Distance Dimming (z = 1.5)
6. Madau (1995) IGM Absorption across Rest-Frame Lyman Series & Continuum
7. Bandpass Contraction into 6 Calibrated JWST NIRCam Photometric Filters
8. Direct Parity Verification Against Independent Float64 Reference Integrator
9. Machine-Readable Provenance Manifest & Reproducibility Certification

NO CORE SPECSYNTH FILES ARE MODIFIED.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

# Ensure local plugin directory is on sys.path
current_dir = Path(__file__).parent.resolve()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

repo_root = current_dir.parents[1].resolve()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import numpy as np

# Specsynth public API
from specsynth.adapters import (
    assert_adapter_conforms,
    get_adapter,
    list_adapters,
    SSPData,
)
from specsynth.contracts import (
    PhotometryPointContract,
    SSPGridContract,
    SyntheticObservationContract,
)
from specsynth.core import attenuation_curve, sfh_from_params, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
from specsynth.filters import get_filter
from specsynth.igm import madau_transmission
from specsynth.provenance import generate_provenance_manifest

# Import external adapter (triggers dynamic registration)
from fsps_external_adapter import FSPSExternalAdapter

C_ANG_S = 2.99792458e18    # Speed of light in Angstrom / s
L_SUN_ERG_S = 3.828e33     # Solar luminosity in erg / s
TARGET_FILTERS = [
    "jwst_f090w",
    "jwst_f150w",
    "jwst_f200w",
    "jwst_f277w",
    "jwst_f356w",
    "jwst_f444w",
]


def run_genuine_conformance_workflow(
    galaxy_id: str = "EXT-FSPS-GALAXY-001",
    redshift: float = 1.5,
    log_mstar: float = 10.5,
    tau_gyr: float = 1.5,
    t_onset_gyr: float = 10.0,
    metallicity_z: float = 0.019,
    tau_diffuse: float = 0.3,
    tau_birth: float = 0.7,
    tolerance_mag: float = 0.005,
    manifest_output_path: Path | None = None,
) -> dict[str, Any]:
    """
    Execute full end-to-end scientific forward-modeling pipeline and verify
    photometric parity against an independent float64 reference integrator.
    """
    print("=" * 78)
    print("Specsynth Genuine External SPS Engine Conformance Workflow")
    print("Engine: Flexible Stellar Population Synthesis (FSPS v3.2)")
    print("North Star Pillars: P1 (Zero-Core Pluggability) & P2 (Scientific Reproducibility)")
    print("=" * 78)

    # -------------------------------------------------------------------------
    # 1. Verify Dynamic Registration & Zero-Core Modifications
    # -------------------------------------------------------------------------
    print(f"\n[Step 1] Verifying Dynamic Discovery & Registry Inspection...")
    if "fsps_external" not in list_adapters():
        from specsynth.adapters import discover_entry_point_adapters
        discover_entry_point_adapters()
    registered = list_adapters()
    assert "fsps_external" in registered, "FSPSExternalAdapter failed to register dynamically!"
    print(f"  ✓ External engine 'fsps_external' discovered in runtime registry.")

    adapter = get_adapter("fsps_external")
    caps = adapter.get_capabilities()
    print(f"  Engine Name : {caps.get('full_name')}")
    print(f"  Provenance  : {caps.get('provenance_badge')}")
    print(f"  Data Mode   : {caps.get('data_mode')} (is_mock={caps.get('is_mock')})")
    assert caps.get("is_mock") is False, "External engine must not be a mock fixture!"
    assert caps.get("data_mode") == "genuine_external_engine"

    # -------------------------------------------------------------------------
    # 2. Execute 11-Point Programmatic Conformance Suite
    # -------------------------------------------------------------------------
    print(f"\n[Step 2] Executing 11-Point Architectural & Scientific Conformance Suite...")
    conf_result = assert_adapter_conforms(FSPSExternalAdapter, verbose=False)
    assert conf_result.passed, f"Conformance checks failed: {conf_result.errors}"
    print("  ✓ FSPSExternalAdapter mathematically certified across all 11 scientific invariants.")

    # -------------------------------------------------------------------------
    # 3. Load Authentic SSP Grid & Validate SSPGridContract
    # -------------------------------------------------------------------------
    print(f"\n[Step 3] Loading Authentic FSPS Grid and Validating SSPGridContract...")
    ssp_data = adapter.load()
    print(f"  Ages         : {len(ssp_data.ages)} steps ({ssp_data.ages[0]:.2e} to {ssp_data.ages[-1]:.2e} yr)")
    print(f"  Metallicities: {len(ssp_data.mets)} steps ({ssp_data.mets[0]} to {ssp_data.mets[-1]})")
    print(f"  Wavelengths  : {len(ssp_data.wave)} points ({ssp_data.wave[0]:.1f} to {ssp_data.wave[-1]:.1f} Å)")
    print(f"  2D Matrix    : {ssp_data.ssp.shape} (dtype: {ssp_data.ssp.dtype}, Age-Major)")

    grid_contract = SSPGridContract(
        source_engine="fsps",
        engine_version="3.2",
        imf=caps.get("imf", "chabrier"),
        isochrones=caps.get("isochrones", "mist_v1.2"),
        ages_yr=ssp_data.ages,
        mets_z=ssp_data.mets,
        wave_angstrom=ssp_data.wave,
        ssp_flux_2d=ssp_data.ssp,
        metadata={
            "engine_label": caps.get("provenance_badge"),
            "data_mode": "genuine_external_engine",
            "source": "Conroy et al. (FSPS v3.2)",
            "provenance": "external_fsps_plugin",
        },
    )
    grid_contract.validate()
    print("  ✓ Canonical SSPGridContract (v1.0.0) strictly validated.")

    # -------------------------------------------------------------------------
    # 4. Form SFH & Synthesize Rest-Frame SED with Two-Component Dust
    # -------------------------------------------------------------------------
    print(f"\n[Step 4] Synthesizing Galaxy SED with Delayed-Tau SFH & Dust Attenuation...")
    wave_rest = ssp_data.wave
    ny = int((ssp_data.ages < 1e7).sum()) * len(ssp_data.mets)
    kd_full = attenuation_curve(wave_rest, -0.7).astype(np.float32)
    kb_full = attenuation_curve(wave_rest, -1.3).astype(np.float32)

    params = np.array([[log_mstar, t_onset_gyr, tau_gyr, metallicity_z]], dtype=np.float32)
    sfh = sfh_from_params(params, ssp_data.ages, ssp_data.mets)

    spec_rest = synth_block(
        sfh,
        np.array([tau_diffuse], dtype=np.float32),
        np.array([tau_birth], dtype=np.float32),
        ssp_data.ssp,
        kd_full,
        kb_full,
        ny,
    )[0]  # Shape: (N_wave,) [L_sun / Angstrom]

    print(f"  Stellar Mass : 10^{log_mstar:.2f} M_sun ({10.0**log_mstar:.2e} M_sun)")
    print(f"  Dust Params  : tau_diffuse = {tau_diffuse:.2f}, tau_birth = {tau_birth:.2f}")
    print(f"  Rest Luminosity @ 5500 Å: {float(np.interp(5500.0, wave_rest, spec_rest)):.4e} L_sun / Å")

    # -------------------------------------------------------------------------
    # 5. Specsynth In-Flight Photometric Projection
    # -------------------------------------------------------------------------
    print(f"\n[Step 5] Contracting Photometry across 6 JWST NIRCam Bands (z = {redshift:.2f})...")
    filter_data = []
    filter_pivots = {}
    filter_checksums = {}
    for fname in TARGET_FILTERS:
        flt = get_filter(fname)
        norm = np.trapezoid(flt.transmission * flt.wave, flt.wave)
        filter_data.append((fname, flt.wave, flt.transmission, norm))
        filter_pivots[fname] = float(flt.pivot_wavelength)
        filter_checksums[fname] = flt.sha256

    specsynth_phot = project_per_galaxy_photometry_chunk(
        spec_rest[None, :],
        np.array([redshift], dtype=np.float32),
        wave_rest,
        filter_data,
        apply_igm=True,
        distance_dimming=True,
        input_units="lsun",
        cosmo=TNG_COSMOLOGY,
    )[0]

    specsynth_mags: dict[str, float] = {}
    specsynth_fnu_ujy: dict[str, float] = {}
    for i, fname in enumerate(TARGET_FILTERS):
        f_lam = float(specsynth_phot[i])
        pivot = filter_pivots[fname]
        f_nu = f_lam * (pivot ** 2) / C_ANG_S  # erg/s/cm2/Hz
        mag = -2.5 * math.log10(f_nu) - 48.60 if f_nu > 0 else 99.0
        specsynth_mags[fname] = round(mag, 4)
        specsynth_fnu_ujy[fname] = round(f_nu * 1e29, 3)

    # -------------------------------------------------------------------------
    # 6. Independent Float64 Reference Quadrature Path
    # -------------------------------------------------------------------------
    print(f"\n[Step 6] Running Independent Float64 Reference Quadrature...")
    wave_obs = wave_rest.astype(np.float64) * (1.0 + redshift)
    t_igm = madau_transmission(wave_obs, redshift)
    d_l_cm = float(TNG_COSMOLOGY.luminosity_distance_cm(redshift))
    dimming_factor = (1.0 / (1.0 + redshift)) / (4.0 * math.pi * (d_l_cm ** 2)) * L_SUN_ERG_S

    f_lam_obs_full = spec_rest.astype(np.float64) * dimming_factor * t_igm

    ref_mags: dict[str, float] = {}
    ref_fnu_ujy: dict[str, float] = {}
    delta_mags: dict[str, float] = {}

    for fname in TARGET_FILTERS:
        flt = get_filter(fname)
        f_lam_interp = np.interp(flt.wave, wave_obs, f_lam_obs_full, left=0.0, right=0.0)

        # Photon-weighted AB integration
        num = np.trapezoid(f_lam_interp * flt.transmission * flt.wave, flt.wave)
        denom = np.trapezoid(flt.transmission / flt.wave, flt.wave) * C_ANG_S
        f_nu_ref = num / denom if denom > 0 else 0.0

        mag_ref = -2.5 * math.log10(f_nu_ref) - 48.60 if f_nu_ref > 0 else 99.0
        ref_mags[fname] = round(mag_ref, 4)
        ref_fnu_ujy[fname] = round(f_nu_ref * 1e29, 3)

        delta = abs(specsynth_mags[fname] - ref_mags[fname])
        delta_mags[fname] = round(delta, 4)

    # -------------------------------------------------------------------------
    # 7. Print Comparative Parity Table
    # -------------------------------------------------------------------------
    print("-" * 78)
    print(f"{'Filter Band':<14} {'Specsynth (AB)':<16} {'Reference (AB)':<16} {'|Δm| (mag)':<12} {'Status'}")
    print("-" * 78)
    for fname in TARGET_FILTERS:
        sm = specsynth_mags[fname]
        rm = ref_mags[fname]
        dm = delta_mags[fname]
        status = f"PASS (<{tolerance_mag:.3f})" if dm < tolerance_mag else "FAIL"
        print(f"{fname:<14} {sm:<16.3f} {rm:<16.3f} {dm:<12.4f} {status}")
    print("-" * 78)

    max_delta = max(delta_mags.values())
    parity_passed = max_delta < tolerance_mag
    print(f"Max Absolute Divergence : {max_delta:.4f} mag")
    print(f"Scientifically Justified : |Δm| < {tolerance_mag:.4f} mag")
    print(f"Parity Certification   : {'PASSED' if parity_passed else 'FAILED'}")
    assert parity_passed, f"Photometric parity failed! Max divergence {max_delta:.4f} >= {tolerance_mag}"

    # -------------------------------------------------------------------------
    # 8. Package Contracts & Provenance Manifest
    # -------------------------------------------------------------------------
    print(f"\n[Step 7] Packaging SyntheticObservationContract & Provenance Manifest...")
    phot_points = [
        PhotometryPointContract(
            filter_name=fname,
            pivot_wavelength_angstrom=filter_pivots[fname],
            flux_density_ujy=specsynth_fnu_ujy[fname],
            ab_magnitude=specsynth_mags[fname],
            ab_mag_error=0.01,
            snr=100.0,
            transmission_sha256=filter_checksums[fname],
        )
        for fname in TARGET_FILTERS
    ]

    obs_contract = SyntheticObservationContract(
        galaxy_id=galaxy_id,
        redshift=redshift,
        cosmology={"H0": TNG_COSMOLOGY.H0, "Om0": TNG_COSMOLOGY.Om0, "Ol0": TNG_COSMOLOGY.Ode0},
        dust_model="charlot_fall_2000",
        igm_model="madau_1995",
        ssp_model=caps.get("provenance_badge"),
        photometry=phot_points,
        sed_wave_angstrom=wave_obs,
        sed_flux_obs_cgs=f_lam_obs_full.astype(np.float32),
        sed_flux_rest_lsun_angstrom=spec_rest.astype(np.float32),
        provenance={
            "engine": "FSPS",
            "version": "3.2",
            "is_genuine": True,
            "zero_core_mod": True,
            "plugin": "specsynth-external-engine-plugin",
        },
    )
    obs_contract.validate()
    print("  ✓ SyntheticObservationContract validated successfully.")

    manifest = generate_provenance_manifest(
        galaxy_id=galaxy_id,
        simulation_name="GenuineExternalEngine_FSPS",
        redshift=redshift,
        physical_parameters={
            "log_mstar": log_mstar,
            "stellar_mass_msun": 10.0 ** log_mstar,
            "tau_gyr": tau_gyr,
            "t_onset_gyr": t_onset_gyr,
            "metallicity_z": metallicity_z,
            "tau_diffuse": tau_diffuse,
            "tau_birth": tau_birth,
        },
        engine_name="FSPS v3.2",
        engine_version="3.2",
        grid_path=adapter.filepath,
        is_genuine_engine=True,
        cosmology={"H0": TNG_COSMOLOGY.H0, "Om0": TNG_COSMOLOGY.Om0, "Ol0": TNG_COSMOLOGY.Ode0},
        filter_checksums=filter_checksums,
        photometry_results=specsynth_mags,
    )

    if manifest_output_path is not None:
        with open(manifest_output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  Provenance Manifest written to: {manifest_output_path.resolve()}")

    print("\n" + "=" * 78)
    print("SUCCESS: Genuine external SPS engine executed with ZERO core modifications!")
    print("=" * 78)

    return {
        "galaxy_id": galaxy_id,
        "redshift": redshift,
        "specsynth_mags": specsynth_mags,
        "specsynth_fnu_ujy": specsynth_fnu_ujy,
        "ref_mags": ref_mags,
        "ref_fnu_ujy": ref_fnu_ujy,
        "delta_mags": delta_mags,
        "max_delta_mag": max_delta,
        "tolerance_mag": tolerance_mag,
        "parity_passed": parity_passed,
        "observation_contract": obs_contract,
        "provenance_manifest": manifest,
    }


if __name__ == "__main__":
    out_file = Path("benchmark_external_engine_manifest.json")
    run_genuine_conformance_workflow(manifest_output_path=out_file)
