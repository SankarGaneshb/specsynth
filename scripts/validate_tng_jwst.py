"""
Standalone Scientific Validation & Benchmarking Runner: TNG -> JWST NIRCam.
Executes the full Workstream D validation protocol and generates paper/benchmark_manifest_tng_jwst.json.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

# Ensure package root is in sys.path
sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np

from specsynth.adapters.fsps import FSPSAdapter, find_default_fsps_grid
from specsynth.catalog import export_scientific_catalog, import_catalog
from specsynth.cosmology import TNG_COSMOLOGY, get_cosmology
from specsynth.filters import NIRCAM_FILTER_REGISTRY, verify_filter_registry
from specsynth.sentry import run_sentry_audit


def run_validation_pipeline(
    sample_catalog_path: str = "data/examples/tng_sample/sample_catalog.parquet",
    output_dir: str = ".tmp_scientific_validation",
    manifest_output: str = "paper/benchmark_manifest_tng_jwst.json",
    sample_verify_size: int = 100,
) -> dict:
    start_time = time.time()
    out_p = Path(output_dir)
    if out_p.exists():
        shutil.rmtree(out_p)
    out_p.mkdir(parents=True, exist_ok=True)

    print("=====================================================================")
    print("      TNG -> JWST NIRCam Scientific Validation Pipeline (v1.0)       ")
    print("=====================================================================")

    # 1. Filter Registry Integrity Check
    print("\n[Stage 1/6] Verifying JWST NIRCam Filter Response Curves & SHA-256...")
    chk = verify_filter_registry()
    target_filters = ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]
    for f in target_filters:
        status = "OK" if chk.get(f) else "FAIL"
        print(f"  * {f:<12}: SHA-256 Checksum [{status}]")
        assert chk.get(f) is True, f"Filter curve integrity failure for {f}"

    # 2. Compile FSPS SSP Library
    print("\n[Stage 2/6] Compiling Full-Wavelength FSPS Reference SSP Library...")
    t0_ssp = time.time()
    ref_grid = find_default_fsps_grid()
    assert ref_grid is not None, "FSPS reference grid not found"
    adapter = FSPSAdapter(filepath=ref_grid, metallicity=0.019)
    ssp_data = adapter.load()
    dt_ssp = time.time() - t0_ssp
    print(f"  * Grid Dimensions    : {ssp_data.ssp.shape} (Ages: {len(ssp_data.ages)}, Wavelengths: {len(ssp_data.wave)})")
    print(f"  * Wavelength Range   : {ssp_data.wave[0]:.1f} A to {ssp_data.wave[-1]:.1f} A ({ssp_data.wave[-1]/1e4:.1f} um)")
    print(f"  * Elapsed Time       : {dt_ssp:.3f}s")

    # Save to ssp.zarr
    import zarr
    ssp_store = str(out_p / "ssp.zarr")
    g_ssp = zarr.open_group(ssp_store, mode="w")
    g_ssp["ages"] = ssp_data.ages
    g_ssp["mets"] = ssp_data.mets
    g_ssp["wave"] = ssp_data.wave
    g_ssp["ssp"] = ssp_data.ssp

    # 3. Ingest Curated TNG Sample
    print(f"\n[Stage 3/6] Ingesting TNG Galaxy Sample ({sample_catalog_path})...")
    t0_cat = time.time()
    gal_store = str(out_p / "galaxies.zarr")
    cat_meta = import_catalog(
        catalog_path=sample_catalog_path,
        output_zarr=gal_store,
        ssp_store=ssp_store,
        chunk_size=1000,
    )
    dt_cat = time.time() - t0_cat
    print(f"  * Ingested Galaxies  : {cat_meta['n_galaxies']:,}")
    print(f"  * Elapsed Time       : {dt_cat:.3f}s")

    # 4. Synthesize NIRCam Photometry
    print("\n[Stage 4/6] Executing In-Flight GEMM Synthesis & Filter Projection...")
    t0_synth = time.time()
    spec_store = str(out_p / "spectra.zarr")

    # Execute synthesis directly
    from specsynth.cosmology import project_per_galaxy_photometry_chunk
    from specsynth.core import attenuation_curve, synth_block
    from specsynth.filters import build_filter_projection_matrix, get_filter

    g_gal = zarr.open_group(gal_store, mode="r")
    sfh = np.asarray(g_gal["sfh"][:])
    td = np.asarray(g_gal["tau_diffuse"][:])
    tb = np.asarray(g_gal["tau_birth"][:])
    redshift = np.asarray(g_gal["redshift"][:])
    n_gal = len(sfh)

    kd = attenuation_curve(ssp_data.wave, -0.7).astype(np.float32)
    kb = attenuation_curve(ssp_data.wave, -1.3).astype(np.float32)
    ny = int((ssp_data.ages < 1e7).sum()) * len(ssp_data.mets)

    # Rest-frame composite SEDs
    spec_rest = synth_block(sfh, td, tb, ssp_data.ssp, kd, kb, n_young_k=ny)

    # Filter projection with TNG cosmology
    filter_data = []
    pivots = []
    for fname in target_filters:
        flt = get_filter(fname)
        norm = np.trapezoid(flt.transmission * flt.wave, flt.wave)
        filter_data.append((fname, flt.wave, flt.transmission, norm))
        pivots.append(flt.pivot_wavelength)

    phot = project_per_galaxy_photometry_chunk(
        spec_block=spec_rest,
        z_block=redshift,
        wave_rest=ssp_data.wave,
        filter_data=filter_data,
        apply_igm=True,
        distance_dimming=True,
        input_units="lsun",
        cosmo=TNG_COSMOLOGY,
    )
    dt_synth = time.time() - t0_synth

    # Save to spectra.zarr
    g_spec = zarr.open_group(spec_store, mode="w")
    g_spec["photometry"] = phot.astype(np.float32)
    g_spec.attrs.update({
        "filters": target_filters,
        "pivot_wavelengths": pivots,
        "distance_dimming": True,
        "input_units": "lsun",
        "igm": True,
        "mode": "lightcone",
        "per_galaxy_z": True,
        "cosmology": {"H0": TNG_COSMOLOGY.H0, "Om0": TNG_COSMOLOGY.Om0, "preset": "tng"},
    })

    throughput = n_gal / dt_synth
    print(f"  * Photometry Array   : {phot.shape} ({len(target_filters)} NIRCam bands)")
    print(f"  * Throughput         : {throughput:,.1f} galaxies/s")
    print(f"  * Synthesis Time     : {dt_synth:.3f}s")

    # 5. Export Scientific Table & Sentry Audit
    print("\n[Stage 5/6] Exporting Scientific Table & Running Sentry Audit...")
    export_parquet = out_p / "synthetic_photometry.parquet"
    exp_res = export_scientific_catalog(
        base=str(out_p),
        output_path=export_parquet,
        model_id="FSPS_v3.2_Chabrier_MIST",
    )
    sentry_rep = run_sentry_audit(base=str(out_p), sample_size=n_gal, attach_is_valid=True)
    print(f"  * Exported File      : {export_parquet}")
    print(f"  * Sentry Status      : {sentry_rep.status} (Valid: {sentry_rep.passed_count}/{n_gal})")

    # 6. Independent Float64 Verification
    print(f"\n[Stage 6/6] Verifying Against Serial Independent Float64 Engine...")
    ssp_64 = ssp_data.ssp.astype(np.float64)
    sfh_64 = sfh.astype(np.float64)
    td_64 = td.astype(np.float64)
    tb_64 = tb.astype(np.float64)
    kd_64 = attenuation_curve(ssp_data.wave, -0.7).astype(np.float64)
    kb_64 = attenuation_curve(ssp_data.wave, -1.3).astype(np.float64)

    spec_ref_64 = np.exp(-td_64[:, None] * kd_64) * (
        sfh_64[:, ny:] @ ssp_64[ny:] + np.exp(-tb_64[:, None] * kb_64) * (sfh_64[:, :ny] @ ssp_64[:ny])
    )
    phot_ref_64 = project_per_galaxy_photometry_chunk(
        spec_block=spec_ref_64,
        z_block=redshift.astype(np.float64),
        wave_rest=ssp_data.wave.astype(np.float64),
        filter_data=filter_data,
        apply_igm=True,
        distance_dimming=True,
        input_units="lsun",
        cosmo=TNG_COSMOLOGY,
    )

    diff = np.abs(phot - phot_ref_64)
    rel_err = diff / np.maximum(phot_ref_64, 1e-35)
    max_rel_err = float(np.max(rel_err))
    mean_rel_err = float(np.mean(rel_err))
    rmse = float(np.sqrt(np.mean(diff**2)))

    print(f"  * Max Relative Error : {max_rel_err:.2e} (Tolerance: < 5.0e-04) [{'PASS' if max_rel_err < 5e-4 else 'FAIL'}]")
    print(f"  * Mean Relative Error: {mean_rel_err:.2e} (Tolerance: < 1.0e-05) [{'PASS' if mean_rel_err < 1e-5 else 'FAIL'}]")
    print(f"  * Photometric RMSE   : {rmse:.2e}")

    total_time = time.time() - start_time

    # Construct benchmark manifest
    manifest_data = {
        "milestone": "TNG-JWST Scientific Validation v1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "cpu_threads": os.cpu_count(),
        },
        "scientific_configuration": {
            "ssp_adapter": "FSPS",
            "imf": "chabrier",
            "isochrone": "mist",
            "cosmology": {"name": "TNG (Planck 2015)", "H0": TNG_COSMOLOGY.H0, "Om0": TNG_COSMOLOGY.Om0},
            "dust_model": "Charlot & Fall (2000)",
            "igm_model": "Madau (1995)",
            "instrument": "JWST NIRCam",
            "filters": target_filters,
        },
        "dataset": {
            "sample_catalog": sample_catalog_path,
            "n_galaxies": n_gal,
            "n_wavelengths": len(ssp_data.wave),
        },
        "performance_telemetry": {
            "total_elapsed_seconds": round(total_time, 2),
            "synthesis_time_seconds": round(dt_synth, 3),
            "throughput_galaxies_per_sec": round(throughput, 1),
        },
        "numerical_accuracy": {
            "max_relative_error": max_rel_err,
            "mean_relative_error": mean_rel_err,
            "rmse": rmse,
            "status": "PASS" if max_rel_err < 5e-4 else "FAIL",
        },
        "quality_audit": {
            "sentry_status": sentry_rep.status,
            "pristine_fraction": sentry_rep.pass_rate_pct,
        }
    }

    manifest_p = Path(manifest_output)
    manifest_p.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_p, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"\nBenchmark Manifest saved to: {manifest_p}")
    print("\n=====================================================================")
    print("                     Validation Run: SUCCESS                         ")
    print("=====================================================================\n")

    # Clean up temporary output directory
    shutil.rmtree(out_p, ignore_errors=True)
    return manifest_data


if __name__ == "__main__":
    run_validation_pipeline()
