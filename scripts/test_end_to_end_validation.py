"""
Comprehensive end-to-end integration and scientific validation script
exercising Phase 2 (multi-format catalogs), Phase 3 (external SPS models),
and in-flight synthesis with numerical verification.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], desc: str) -> None:
    print(f"\n[RUNNING] {desc}")
    print(f"  Command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  [ERROR] Command failed with exit code {res.returncode}:")
        if res.stderr:
            print("--- STDERR ---")
            print(res.stderr.strip())
        if res.stdout:
            print("--- STDOUT ---")
            print(res.stdout.strip())
        err_msg = res.stderr.strip() if res.stderr else res.stdout.strip()
        raise RuntimeError(f"Step '{desc}' failed with exit code {res.returncode}:\n{err_msg}")
    print("  [SUCCESS] Completed.")


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    
    # Auto-detect local virtual environment to ensure all packages (zarr, dask, etc.) are available
    venv_py = root / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if venv_py.exists():
        py_bin = str(venv_py)
    else:
        py_bin = sys.executable

    test_base = Path(".tmp_e2e_phases")
    if test_base.exists():
        shutil.rmtree(test_base)
    test_base.mkdir(parents=True, exist_ok=True)

    print("==================================================================")
    print("     SpecSynth End-to-End Validation (Phases 2, 3, and 4)         ")
    print("==================================================================")

    # ------------------------------------------------------------------
    # Step 1: Generate External Sample SPS Models (Phase 3)
    # ------------------------------------------------------------------
    models_dir = test_base / "sample_models"
    run_cmd(
        [py_bin, "scripts/create_sample_models.py", "-o", str(models_dir)],
        "Phase 3: Generate External SPS Models (BC03, E-MILES, FSPS, FITS/HDF5)",
    )

    # Test make-ssp with Analytical Reference Grid
    ssp_analytical = test_base / "ssp_analytical"
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(ssp_analytical), "--scheduler", "sync",
            "make-ssp", "--adapter", "analytical", "--n-age", "30", "--n-met", "4", "--n-wave", "1500"
        ],
        "Phase 3: make-ssp with Analytical Reference Grid",
    )

    # Test make-ssp with BC03 (.ised binary)
    ssp_bc03 = test_base / "ssp_bc03"
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(ssp_bc03), "--scheduler", "sync",
            "make-ssp", "--adapter", "bc03",
            "--input-path", str(models_dir / "bc03" / "bc2003_hr_stelib_chab_ssp.ised")
        ],
        "Phase 3: make-ssp with BC03 (.ised binary)",
    )

    # Test make-ssp with E-MILES (FITS directory)
    ssp_emiles = test_base / "ssp_emiles"
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(ssp_emiles), "--scheduler", "sync",
            "make-ssp", "--adapter", "emiles",
            "--input-path", str(models_dir / "emiles")
        ],
        "Phase 3: make-ssp with E-MILES (FITS directory)",
    )

    # Test make-ssp with FITS 3D Grid
    ssp_fits = test_base / "ssp_fits"
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(ssp_fits), "--scheduler", "sync",
            "make-ssp", "--adapter", "fits",
            "--input-file", str(models_dir / "fits_grid" / "ssp_grid.fits")
        ],
        "Phase 3: make-ssp with 3D FITS grid",
    )

    # ------------------------------------------------------------------
    # Step 2: Generate & Ingest Multi-Format Catalogs (Phase 2)
    # ------------------------------------------------------------------
    catalogs_dir = test_base / "sample_catalogs"
    run_cmd(
        [py_bin, "scripts/generate_sample_catalogs.py", "-o", str(catalogs_dir), "-n", "2000"],
        "Phase 2: Generate Multi-Format Catalogs (Parquet, FITS, HDF5, CSV)",
    )

    # Ingest Parquet
    cat_parquet_base = test_base / "cat_parquet"
    shutil.copytree(ssp_analytical / "ssp.zarr", cat_parquet_base / "ssp.zarr")
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(cat_parquet_base), "--scheduler", "sync",
            "import-catalog", "-i", str(catalogs_dir / "sample_catalog.parquet")
        ],
        "Phase 2: Ingest Parquet Catalog",
    )

    # Ingest FITS
    cat_fits_base = test_base / "cat_fits"
    shutil.copytree(ssp_analytical / "ssp.zarr", cat_fits_base / "ssp.zarr")
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(cat_fits_base), "--scheduler", "sync",
            "import-catalog", "-i", str(catalogs_dir / "sample_catalog.fits")
        ],
        "Phase 2: Ingest FITS Catalog",
    )

    # Ingest CSV with Streaming Mode
    cat_csv_base = test_base / "cat_csv"
    shutil.copytree(ssp_analytical / "ssp.zarr", cat_csv_base / "ssp.zarr")
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(cat_csv_base), "--scheduler", "sync",
            "import-catalog", "-i", str(catalogs_dir / "sample_catalog.csv"),
            "--streaming", "--chunk", "1000"
        ],
        "Phase 2: Ingest CSV Catalog in Streaming Chunk Mode",
    )

    # ------------------------------------------------------------------
    # Step 3: In-Flight Synthesis & Scientific Verification (Phase 4)
    # ------------------------------------------------------------------
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(cat_parquet_base), "--scheduler", "sync",
            "synth", "--chunk", "1000", "--filters", "jwst_nircam", "--redshift", "2.0", "--igm"
        ],
        "Synthesis: In-Flight JWST NIRCam Filter Projection + Madau IGM",
    )

    # Verify numerical accuracy
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(cat_parquet_base), "--scheduler", "sync",
            "verify", "--sample", "100"
        ],
        "Numerical Verification: Compare Distributed Float32 vs Independent Float64 Reference",
    )

    # Run Autonomous Scientific Sentry
    run_cmd(
        [
            py_bin, "specsynth.py", "--base", str(cat_parquet_base),
            "sentry-agent", "--sample", "500",
            "--clean-output", str(test_base / "clean_catalog.parquet"),
            "--output-memo", str(test_base / "sentry_agent_memo.md")
        ],
        "Autonomous Sentry Agent: Anomaly Audit & Remediation",
    )

    print("\n==================================================================")
    print("  ALL END-TO-END VALIDATION PHASES COMPLETED AND VERIFIED!        ")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
