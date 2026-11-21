# Research Brief: TNG → JWST NIRCam Scientific Validation

**Milestone:** `TNG–JWST Scientific Validation v1.0`  
**Target:** Galaxy Evolution & JWST Survey Researchers  
**Date:** November 2026  

---

## Executive Summary

Forward-modeling mock galaxy surveys from cosmological hydrodynamical simulations (such as IllustrisTNG) is fundamental to the scientific interpretation of deep extragalactic observations from the James Webb Space Telescope (JWST). However, traditional spectral synthesis pipelines face three critical challenges:
1. Generating intermediate multi-terabyte full spectra before filter integration creates massive I/O and storage bottlenecks.
2. Inconsistent cosmological parameter conventions (e.g. mismatch between simulation FLRW parameters and synthetic distance dimming) introduce systematic errors of up to 6–7% in flux.
3. Complex, multi-dependency installation environments (Fortran compilers, private API keys, proprietary file formats) hinder external reproducibility.

`specsynth` solves these challenges by combining:
- **In-Flight Matrix Contraction**: Multiplying galaxy star formation histories against pre-compiled Simple Stellar Population (SSP) libraries directly into calibrated instrument filter matrices ($\mathbf{Phot} = \mathbf{SFH} \times \mathbf{SSP} \times \mathbf{M}_{\mathrm{filter}}$) in worker memory without writing multi-gigabyte spectra to disk.
- **Physical Precision**: Verified photon-weighted filter integration matching the official STScI NIRCam instrument throughput curves, Planck 2015 cosmology matching IllustrisTNG, Charlot & Fall (2000) two-component dust, and Madau (1995) IGM attenuation.
- **Immediate Reproducibility**: A 10-minute researcher-facing Jupyter notebook executing out-of-the-box on a laptop CPU.

---

## Key Results & Validation Highlights

1. **Numerical Accuracy**: The distributed `float32` production pipeline reproduces an independent serial `float64` NumPy reference engine to within **$4.77 \times 10^{-8}$ maximum relative error** and **$< 0.0001\,\mathrm{mag}$** photometric residual across all six NIRCam filters.
2. **Photometric Calibration**: Evaluation on a standard $3631\,\mathrm{Jy}$ flat-spectrum source confirms that all six NIRCam wide filters (F090W, F150W, F200W, F277W, F356W, F444W) reproduce the AB magnitude zero point ($m_{\mathrm{AB}} = 0.000\,\mathrm{mag}$) to within $0.0001\,\mathrm{mag}$.
3. **Execution Efficiency**: Generates calibrated 6-band photometry for 100 simulated galaxies in under **$2\,\mathrm{seconds}$** on a standard laptop CPU, and processes over $400\,\mathrm{galaxies/s}$ per worker.
4. **Physical Reliability**: Multi-tier Scientific Sentry anomaly detection certifies a $100\%$ pristine pass rate on the curated IllustrisTNG sample, with zero unphysical colors or negative fluxes.

---

## How to Evaluate

Researchers can evaluate the validation results directly:
1. Run the self-contained notebook: [`notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb`](../../notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb).
2. Inspect the automated validation report: [`docs/science/validation-report.md`](validation-report.md).
3. Review the machine-readable benchmark manifest: [`paper/benchmark_manifest_tng_jwst.json`](../../paper/benchmark_manifest_tng_jwst.json).
