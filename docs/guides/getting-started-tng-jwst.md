# User Guide: Getting Started with TNG → JWST Photometry

**Milestone:** `TNG–JWST Scientific Validation v1.0`  
**Dual-Package Architecture:** Scientific Validation Package & Researcher Demonstration Package  

---

## 1. Executive Overview

To lower adoption friction for astronomers evaluating `specsynth`, the framework separates the deliverable into two complementary packages:

1. **Scientific Validation Package:** Comprehensive 175-test automated verification suite, double-precision numerical benchmarks, physical assumptions audit, and external FLRW/Madau reference tests.
2. **Researcher Demonstration Package:** Fast interactive Jupyter notebook executing in **~2.0 seconds** (interactive in-memory) on CPU without requiring an external Fortran compiler, producing 5 publication-ready figures exported to 300 DPI PNG and vector PDF.

---

## 2. Interactive Jupyter Notebook (Researcher Demonstration Package)

The fastest way to evaluate `specsynth` is through the standalone Jupyter notebook:

```bash
jupyter lab notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb
```

### Benchmark Timing & Execution Conditions
- **Tested Hardware:** Intel64 Family 6 Model 170 (12 physical / 14 logical cores, 16 GB RAM, Windows 11 / Linux compatible).
- **Core Dependencies:** Python 3.10+, NumPy 2.2+, PyArrow 26.0+, Matplotlib 3.10+, Zarr 3.4+.
- **Interactive In-Memory Runtime:** **2.04 seconds** (data loading, spectral synthesis, filter projection, inline figure generation).
- **In-Flight Synthesis Kernel:** **0.066 seconds** for 100 galaxies into 6 NIRCam bands (**1,510 galaxies/second** on a single CPU core).
- **Full Cold-Start Run with Disk Export:** **8.65 seconds** (saving 10 publication files: 5 PNGs at 300 DPI and 5 vector PDFs).
- **Data Assets:** Bundled locally in `data/examples/tng_sample/` and `sample_models/fsps/`, requiring zero external downloads.

### Fortran Compiler & FSPS Transparency
- **Compiler Requirement:** **None.** The demonstration notebook runs in pure Python and NumPy without `gfortran` or `make`.
- **Precomputed SSP Grid:** The bundled grid (`sample_models/fsps/fsps_full_chabrier_mist.spec`) was generated with **FSPS v3.2** (Chabrier 2003 IMF, MIST isochrones, solar metallicity $Z=0.019$, 2,500 wavelengths from $91.2\,\mathrm{\AA}$ to $100{,}000\,\mathrm{\AA}$).
- **Matrix Contraction:** `specsynth` contracts galaxy SFH matrices against this grid in-flight without intermediate spectral disk storage.
- **Dynamic Mode:** If `python-fsps` and a Fortran compiler are available, `specsynth.adapters.FSPSAdapter` can synthesize arbitrary custom IMFs and isochrones on the fly.
- **Parameter Scope:** Users can freely vary galaxy stellar mass, SFH parameters, formation age, $\tau$, Charlot & Fall (2000) dust attenuation ($\tau_d, \tau_b$), redshifts, cosmology, and IGM absorption in pure Python.

---

## 3. The Five Publication-Grade Visual Deliverables

| Deliverable | File Artifacts | Physical / Observational Value |
| :--- | :--- | :--- |
| **Figure 1** | `fig1_nircam_transmission.{png,pdf}` | Calibrated STScI NIRCam wide filter curves (F090W–F444W), module-averaged total system response (OTE + optics + filters + detector QE). |
| **Figure 2** | `fig2_sed_photometry_overlay.{png,pdf}` | SED & synthetic photometry overlay for representative Star-Forming and Quiescent galaxies, distinguishing intrinsic, dust-attenuated, and observed-frame spectra with filter bandwidths. |
| **Figure 3** | `fig3_color_redshift_tracks.{png,pdf}` | $[F150W - F444W]$ and $[F200W - F277W]$ evolution tracks, distinguishing continuous theoretical model tracks across $z \in [0.2, 4.0]$ from discrete TNG simulation sample scatter. |
| **Figure 4** | `fig4_color_color_diagnostic.{png,pdf}` | NIRCam color-color diagnostic ($[F150W - F200W]$ vs. $[F200W - F444W]$) separating star-forming disks from quiescent spheroids with $\mathrm{sSFR} = -11.0\,\mathrm{yr}^{-1}$ classification and dust vectors. |
| **Figure 5** | `fig5_numerical_residuals.{png,pdf}` | 6-panel residual breakdown ($\Delta m = m_{\mathrm{FP32}} - m_{\mathrm{FP64}}$) demonstrating numerical stability across all 100 galaxies against double precision ($|\Delta m| < 5 \times 10^{-4}\,\mathrm{mag}$). |

---

## 4. Production CLI Workflow (3 Commands)

For full batch simulations and cluster deployments:

```bash
# 1. Compile FSPS reference library
python specsynth.py --base my_tng_run make-ssp --adapter fsps --input-file sample_models/fsps/fsps_full_chabrier_mist.spec

# 2. Ingest TNG catalog
python specsynth.py --base my_tng_run import-catalog --input-file data/examples/tng_sample/sample_catalog.parquet

# 3. Synthesize 6-band JWST NIRCam photometry and export standard scientific table
python specsynth.py --base my_tng_run synth \
  --filters jwst_nircam_six \
  --per-galaxy-z \
  --distance-dimming \
  --cosmology tng \
  --igm \
  --export-catalog my_tng_run/synthetic_photometry.parquet
```
