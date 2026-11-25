# Validation, Cross-Code Verification & Benchmarks

All empirical performance metrics and numerical validations are backed by reproducible scripts and machine-verified JSON manifests stored under `paper/`.

---

## 1. Numerical Correctness (Distributed `float32` vs. Serial `float64`)

Evaluated across 2,000 galaxies ($K = 60$ SSP templates, $W = 1,200$ wavelength bins; see `paper/benchmark_manifest.json`):

| Correctness Metric | Measured Value | Tolerance | Status |
| :--- | :---: | :---: | :---: |
| **Max Relative Spectral Error** | `9.87e-7` | `< 5.0e-4` | PASS |
| **Mean Relative Spectral Error** | `8.77e-8` | `< 1.0e-5` | PASS |
| **Median Relative Spectral Error** | `7.21e-8` | `< 1.0e-5` | PASS |
| **Root Mean Square Error (RMSE)** | `2.24e-11` | — | PASS |

---

## 2. External Cross-Code Validation (`scripts/cross_validate_sps.py`)

`scripts/cross_validate_sps.py` cross-validates `specsynth` end-to-end on realistic IllustrisTNG-like galaxy populations (star-forming main sequence, quiescent red sequence, and high-$z$ starbursts):

1. **Cosmology vs. Astropy**: Cross-checks `specsynth.cosmology.FlatLambdaCDM` comoving and luminosity distances against `astropy.cosmology.FlatLambdaCDM` across $z \in [0.05, 6.0]$ (tolerance `< 1e-4`).
2. **Photometric Fidelity**: Validates full rest-to-observed Charlot & Fall (2000) dust + Madau (1995) IGM + calibrated JWST NIRCam, HST, and SDSS AB magnitudes against an independent float64 reference integrator (tolerance $|\Delta m_{\text{AB}}| < 10^{-3}\text{ mag}$).
3. **Optional Live `python-fsps` & `DSPS` Cross-Check**: When `fsps` or `dsps` is installed in the environment, automatically compares synthesized SEDs and AB magnitudes directly on identical SSP grids and SFH weights.

Run the cross-validation harness:

```bash
python scripts/cross_validate_sps.py --n-gal 500 --output paper/cross_validation_manifest.json
```

---

## 3. Empirical Hardware Benchmarks

### Single-Node CPU BLAS vs. NVIDIA Tesla T4 GPU
Workload: 50,000 galaxies, $K = 60$, $W = 1,200$ (5 timed runs after 2 warmups; manifests: `paper/benchmark_manifest.json`, `paper/benchmark_manifest_gpu_t4.json`):

| Hardware Environment | Backend | Mean Runtime | Throughput | Compute Rate | Speedup |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Workstation CPU** (Intel 12C/14T) | `scipy-openblas` | 0.8624 s (± 0.0577 s) | 57,978 gal/s | 17.12 GFLOPS | — |
| **Cloud VM CPU** (Linux x86_64, 2C/4T) | `scipy-openblas` | 0.8719 s (± 0.0252 s) | 57,344 gal/s | 16.93 GFLOPS | 1.0x (baseline) |
| **Cloud GPU** (NVIDIA Tesla T4, 15 GB) | CuPy / CUDA | **0.1932 s** (± 0.0040 s) | **258,812 gal/s** | **76.40 GFLOPS** | **4.51x** |

*Note: GPU throughput is measured end-to-end (including host-to-device memory copy, GPU GEMM contractions, dust/IGM attenuation, in-flight filter contraction, and device-to-host transfer). The 4.51x speedup is computed relative to the paired cloud VM CPU baseline.*

#### Kaggle Tesla T4 GPU Benchmark & CI Integration
Because standard GitHub Actions runners provide CPU-only execution, `specsynth` integrates with Kaggle's cloud GPU infrastructure via an automated orchestration pipeline (`scripts/run_kaggle_gpu.py` and `.github/workflows/kaggle-gpu.yml`):

1. **GitHub Actions Workflow (`kaggle-gpu.yml`)**:
   - Triggers on-demand via **Workflow Dispatch** (with configurable `n_galaxies`, `n_runs`, `commit_sha`, and `public` flags), weekly on a scheduled cron, and on published GitHub releases.
   - Requires `KAGGLE_USERNAME` and `KAGGLE_KEY` in GitHub Repository Secrets.
   - Pushes the benchmark kernel to Kaggle, monitors execution, retrieves `gpu_manifest.json`, and records the verified metrics in `$GITHUB_STEP_SUMMARY`.
2. **Local / Developer Execution**:
   ```bash
   # Dry-run validation (tests worker compilation and metadata formatting without hitting Kaggle API):
   python scripts/run_kaggle_gpu.py --dry-run --username <your_kaggle_username>

   # Live Kaggle GPU dispatch:
   python scripts/run_kaggle_gpu.py --username <your_kaggle_username> --n-gal 50000 --n-runs 5
   ```
3. **Public Verified Kaggle Notebook**:
   Explore the live interactive GPU benchmark on Kaggle: [https://www.kaggle.com/code/bsankarganesh/specsynth-gpu-benchmark](https://www.kaggle.com/code/bsankarganesh/specsynth-gpu-benchmark).

### Out-of-Core Memory Boundedness (`psutil` RSS)
Streaming 100k to 1M galaxies sequentially in 20,000-galaxy chunks (measured as single-process sequential chunk RSS, distinguished from client graph overhead or distributed multi-worker memory):

| Streamed Catalog Scale | Single-Process Chunk RSS | Monolithic Unchunked Footprint ($W=4,000$) |
| :--- | :---: | :---: |
| 100,000 Galaxies | 261.5 MB | 1.49 GB |
| 250,000 Galaxies | 261.5 MB | 3.73 GB |
| 500,000 Galaxies | 261.5 MB | 7.45 GB |
| 1,000,000 Galaxies | 261.8 MB | 14.90 GB |

### Multi-Node Cloud Kubernetes Verification
Verified on a 3-node Oracle Container Engine for Kubernetes (OKE) cluster backed by in-cluster shared NFS (`paper/benchmark_manifest_oci_oke_3node.json`): **53,814 galaxies/s** (100,000 galaxies in 1.86 s, max relative error `8.16e-7`).

### Analytical Cluster Scaling Projections (Category 4 Cloud Economics)
*To prevent confusion between empirical benchmarks and theoretical capacity planning, multi-worker projections ($N \ge 10^7$ galaxies) are explicitly modeled via analytical queue-efficiency models rather than single-run empirical captures:*

| Scale | Model Assumptions | Projected Runtime | Estimated Spot Cost (GCP) |
| :--- | :--- | :---: | :---: |
| **10 Million Galaxies** | 8 CPU workers (85% efficiency) | 24.0 seconds | $0.02 |
| **100 Million Galaxies** | 32 CPU workers (82% efficiency) | 63.4 seconds (1.1 min) | $0.25 |
| **1 Billion Galaxies** | 64 CPU workers (75% efficiency) | 336.9 seconds (5.6 min) | $4.20 |

---

---

## 4. TNG → JWST NIRCam Scientific Validation (`paper/benchmark_manifest_tng_jwst.json`)

Evaluated on the curated 100-galaxy IllustrisTNG demonstration sample ($z \in [0.22, 3.88]$) across the 6 calibrated JWST NIRCam wide filters (F090W, F150W, F200W, F277W, F356W, F444W) using FSPS:

| Metric | Measured Value | Scientific Tolerance | Status |
| :--- | :---: | :---: | :---: |
| **Max Relative Flux Error** | `4.77e-08` | `< 5.0e-04` | **PASS** |
| **Mean Relative Flux Error** | `1.03e-08` | `< 1.0e-05` | **PASS** |
| **Photometric RMSE** | `5.59e-23 erg/s/cm^2/A` | — | **PASS** |
| **Max Photometric Residual** | `5.17e-08 mag` | `< 0.005 mag` | **PASS** |
| **Flat $f_\nu$ AB Zero-Point Error** | `0.000 mag` | `< 0.0005 mag` | **PASS** |
| **Synthesis Throughput (Single Core)** | `1,510.5 gal/s` | `> 200 gal/s` | **PASS** |
| **Interactive Notebook Runtime** | `2.04 seconds` | `≤ 5.0 seconds` | **PASS** |
| **Sentry Pristine Fraction** | `100.0%` (100/100) | `> 95%` | **PASS** |

Run the automated validation pipeline:
```bash
python scripts/validate_tng_jwst.py
```
Or launch the interactive demonstration notebook:
```bash
jupyter lab notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb
```

---

## 5. Reproducing Benchmarks & Reference Catalog

```bash
# Run full automated scientific verification suite
pytest -v --cov=specsynth

# Run cross-code astrophysical validation
python scripts/cross_validate_sps.py --n-gal 500

# Run local / GPU hardware throughput benchmark
specsynth benchmark --n-gal 50000 --n-runs 5 --output benchmark_local.json

# Run 1-, 2-, and 3-worker scaling comparison
python scripts/run_cluster_scaling_benchmark.py --workers 1 2 3 --n-gal 60000 --chunk 20000
```

A canonical 100,000-galaxy reference benchmark catalog (Parquet & Zarr, 16 calibrated bands) is publicly archived on Hugging Face with permanent DOI [`10.57967/hf/11635`](https://doi.org/10.57967/hf/11635).
