# TNG → JWST NIRCam Synthetic Photometry: 10-Minute Researcher Experiment

**Notebook:** [`01_tng_jwst_synthetic_photometry.ipynb`](01_tng_jwst_synthetic_photometry.ipynb)  
**Target Audience:** Astrophysicists, galaxy evolution researchers, JWST observers, and computational cosmologists.  
**Estimated Execution Time:** ~1 to 2 minutes on a standard laptop CPU (Target: $\le 10$ minutes).  

---

## Overview

This notebook provides a complete, self-contained demonstration of forward-modeling **JWST NIRCam synthetic photometry** from **IllustrisTNG** cosmological simulation galaxies using **Flexible Stellar Population Synthesis (FSPS)**.

### Zero Infrastructure Hassle:
- **No Fortran compilation or `$SPS_HOME` configuration required**: Includes a pre-compiled, version-locked wide-wavelength FSPS reference grid (`sample_models/fsps/fsps_full_chabrier_mist.spec`).
- **No external API keys or credentials needed**: Bundles a quality-controlled 100-galaxy sample from IllustrisTNG-100 (`data/examples/tng_sample/sample_catalog.parquet`).
- **No GPU required**: Runs in pure CPU mode using NumPy and SciPy.

---

## 5 Visual Deliverables Produced by the Notebook

1. **Galaxy SEDs (Rest-Frame vs. Observed-Frame)**:
   Contrasts intrinsic stellar emission against cosmologically redshifted, distance-dimmed, and Madau (1995) IGM-attenuated flux density at $z = 1.0$.
2. **NIRCam Throughput Curves**:
   Displays the official transmission curves for all six primary wide filters: **F090W, F150W, F200W, F277W, F356W, and F444W**, marking their pivot wavelengths.
3. **Colour-Colour Diagram**:
   Projects galaxies into $F150W - F200W$ vs. $F277W - F444W$, demonstrating clear separation of star-forming disks and quenched spheroids.
4. **Numerical Validation Residuals**:
   Quantifies the photometric error between `specsynth` production output and a high-precision `float64` serial reference ($|\Delta m| < 0.0005\,\mathrm{mag}$).
5. **Redshift Evolution Tracks**:
   Shows apparent magnitude trends as a function of cosmological redshift ($z \in [0.2, 3.5]$).

---

## Execution Instructions

```bash
# 1. Activate environment
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows

# 2. Launch Jupyter Lab / Notebook
jupyter lab notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb
```

Click **Run All Cells**. The entire pipeline runs sequentially without external network calls.
