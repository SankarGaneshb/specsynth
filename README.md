# specsynth: Cloud-Native Distributed Infrastructure for Survey-Scale Astrophysical Spectral Synthesis

[![Documentation](https://img.shields.io/badge/Docs-MkDocs%20Material-indigo.svg)](https://sankarganeshb.github.io/specsynth/)
[![CI](https://github.com/SankarGaneshb/specsynth/actions/workflows/ci.yml/badge.svg)](https://github.com/SankarGaneshb/specsynth/actions)
[![codecov](https://codecov.io/gh/SankarGaneshb/specsynth/branch/main/graph/badge.svg)](https://codecov.io/gh/SankarGaneshb/specsynth)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Benchmark%20Dataset-yellow.svg)](https://huggingface.co/datasets/sreeganesh/specsynth-benchmark-100k)
[![DOI: 10.57967/hf/11635](https://img.shields.io/badge/DOI-10.57967%2Fhf%2F11635-blue.svg)](https://doi.org/10.57967/hf/11635)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SankarGaneshb/specsynth/blob/main/notebooks/quickstart.ipynb)
[![Kaggle GPU Benchmark](https://kaggle.com/static/images/open-in-kaggle.svg)](https://www.kaggle.com/code/bsankarganesh/specsynth-gpu-benchmark)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

`specsynth` is an open-source distributed framework for scalable stellar population synthesis (SPS) and in-flight photometric forward-modeling of cosmological galaxy catalogs. By coupling chunked **Zarr** storage via `fsspec` with **Dask** distributed task graphs and optional **CuPy** GPU tensor contractions, `specsynth` streams galaxy star formation histories (SFHs) from local disks or cloud object stores, contracts them against Simple Stellar Population (SSP) spectral grids in worker cache/VRAM, and projects them directly into broadband photometry without materializing multi-terabyte intermediate spectra onto disk.

**Full Documentation & API Reference:** [https://sankarganeshb.github.io/specsynth/](https://sankarganeshb.github.io/specsynth/) (source under [`docs/`](docs/)).

---

## 1. Installation & Quickstart

### Install

```bash
git clone https://github.com/SankarGaneshb/specsynth.git
cd specsynth
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .\.venv\Scripts\Activate.ps1
pip install -e ".[astro,test]"
```

Optional extras: `.[storage]` (`s3fs`, `gcsfs`, `adlfs`), `.[gpu]` (`cupy-cuda12x`), `.[docs]` (`mkdocs`, `mkdocs-material`, `mkdocstrings`). See the [Installation Guide](docs/getting-started/installation.md) for details.

### Run an End-to-End Pipeline

```bash
# 1. Compile an SSP basis into Zarr (swap --adapter toy for bc03, emiles, fsps, or fits)
specsynth --base ./run1 --scheduler sync make-ssp --adapter toy --n-age 40 --n-met 4 --n-wave 2000

# 2. Generate a mock galaxy catalog (or use `import-catalog` for Parquet/FITS/HDF5/CSV)
specsynth --base ./run1 --scheduler sync make-sfh --n-gal 20000 --chunk 5000

# 3. Synthesize JWST NIRCam photometry in-flight at z = 2.0 with Madau (1995) IGM attenuation
specsynth --base ./run1 --scheduler sync synth --filters jwst_nircam --redshift 2.0 --igm

# 4. Verify float32 distributed output against an independent float64 reference
specsynth --base ./run1 --scheduler sync verify --sample 200
```

Run the automated test suite and cross-code astrophysical validation:

```bash
pytest -v
python scripts/cross_validate_sps.py --n-gal 500
```

### TNG → JWST NIRCam Scientific Validation & Demonstration (Milestone 1)

For researchers evaluating synthetic JWST NIRCam photometry from cosmological simulations (IllustrisTNG-100) using FSPS:

- **Interactive Jupyter Notebook (< 5s CPU evaluation)**:
  ```bash
  jupyter lab notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb
  ```
  *Executes in **~2.04 seconds** on a single CPU core without external Fortran compiler prerequisites, generating 5 publication-ready figures.*

- **Automated End-to-End Validation Pipeline**:
  ```bash
  python scripts/validate_tng_jwst.py
  ```
  *Executes all 6 validation stages, validating STScI NIRCam filter checksums, in-flight GEMM synthesis ($1{,}510.5\,\mathrm{gal/s}$ matrix contraction, $896.6\,\mathrm{gal/s}$ full pipeline), C09 scientific catalog export, and double-precision stability ($\max \delta F/F = 4.77 \times 10^{-8}$).*

---

## 2. Interactive Scientific Explorer: PerandamΨ (PSI)

[![E2E & LoAF Passed](https://img.shields.io/badge/E2E%20Browser%20Testing-Chromium%20CDP%20Passed-emerald.svg)](#)
[![LoAF Active](https://img.shields.io/badge/W3C%20LoAF-Monitored%20%26%20Optimized-indigo.svg)](#)
[![UI Parity](https://img.shields.io/badge/Scientific%20Parity-%7C%CE%94m%7C%20%3C%200.004%20mag-cyan.svg)](#)

`specsynth` includes **PerandamΨ (PSI)**, a high-performance interactive web application and scientific engine for survey-scale deep field exploration, real-time cosmological parameter sweeping, and automated JWST observing proposal generation.

<div align="center">
  <img src="assets/perandam_walkthrough.gif" alt="PerandamΨ Interactive Walkthrough" width="100%" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
  <p><em>Recorded Live: Interactive galaxy selection, synthetic JWST NIRCam photometry, reactive in-flight parameter forward-modeling (Redshift z = 1.0 → 4.5, Dust Av = 0.5 → 2.5 mag), and JWST proposal feasibility planning.</em></p>
</div>

### Key Capabilities in PerandamΨ

- **In-Flight Real-Time Forward Modeling**: Drag Redshift ($z \in [0.1, 10.0]$) and Dust Attenuation ($A_V \in [0.0, 3.0]\,\mathrm{mag}$) sliders. The in-browser scientific engine applies cosmological expansion ($\lambda_{\text{obs}} = \lambda_{\text{rest}}(1+z)$), Flat $\Lambda\mathrm{CDM}$ distance dimming ($D_L(z)$), Charlot & Fall (2000) dust extinction, and Madau (1995) IGM attenuation with sub-16ms latency.
- **Calibrated JWST NIRCam Photometry**: Displays synthetic photometry across all 6 core filters (`F090W` to `F444W`) with bandpass flux densities in $\mu\mathrm{Jy}$, AB magnitudes with 10 ks ETC noise errors ($\pm \sigma_m$), and dynamic $S/N$ detection flags (Secure $\ge 5\sigma$, Marginal $3-5\sigma$, Upper Limit $<3\sigma$).
- **Dual-Frame SED Inspection**: 1-click toggle between rest-frame luminosity ($L_\lambda$ in $L_\odot/\mathrm{\AA}$) and observed-frame flux density ($F_\lambda$ in $\mathrm{erg\,s^{-1}\,cm^{-2}\,\AA^{-1}}$) with astrophysical break markers (Lyman Limit 912 Å, Ly$\alpha$ 1216 Å, Balmer Break 3646 Å, $D_n4000$, and H$\alpha$ 6563 Å).
- **Dynamic Color-Color Tracks**: Diagnostic color-redshift evolution tracks ($z \in [0.2, 8.5]$) with diamond waypoints and a live target reticle tracking forward-modeled colors.
- **Frontier Discovery Mining**: Statistical anomaly detection ($D_M, \chi^2_6, p$-value) in 6D NIRCam feature space with peer-reviewed literature citations (*Matthee+24, Labbé+23, Greene+23, Carnall+23*).
- **JWST Observing Feasibility Planning Sheet**: Generates proposal-ready celestial ($\alpha, \delta$) and ecliptic ($\lambda, \beta$) coordinates, GOODS-S annual visibility windows (~190 days/yr), and NIRSpec WATA target acquisition star constraints ($V < 20$ within 2 arcmin).
- **Dual-Dataset Switcher**: Seamless toggle between the **GOODS-S Deep Mock (508 galaxies)** and the curated **TNG-100 Calibration Sample (100 galaxies)**.

### Quickstart: Launching the Explorer

```bash
# Terminal 1: Launch SpecSynth Scientific HTTP Bridge & MCP Server
python -m specsynth.mcp.bridge --port 8000

# Terminal 2: Launch PerandamΨ Web Explorer (Dev Mode)
cd perandam-psi
npm install
npm run dev

# Or visit http://localhost:8000 directly to access the compiled production build!
```

### Automated UI & Headless E2E Browser Testing

```bash
cd perandam-psi

# 1. Run Headless Browser E2E, Core Web Vitals & W3C LoAF Audit
npm run test:e2e

# 2. Run In-Browser Physics & Dataset Unit Tests
npm test
```

---

## 3. System Architecture & Worker Pipeline

`specsynth` decouples offline SSP basis construction (`K x W`) from online streaming matrix contractions (`N_chunk x K` @ `K x W`). Intermediate full spectra stay in CPU cache or GPU VRAM and are projected directly into photometric bandpasses (`W x B`):

```mermaid
flowchart LR
    subgraph Storage ["Cloud / Local Zarr Storage (fsspec)"]
        SSP["ssp.zarr<br/>(K x W SSP Basis)"]
        GAL["galaxies.zarr<br/>(N x K SFH + Dust)"]
    end

    subgraph WorkerTask ["Worker Memory Pipeline (Per Chunk)"]
        GEMM["Dense GEMM<br/>SFH_young @ SSP_young<br/>SFH_old @ SSP_old"]
        Dust["Charlot & Fall (2000)<br/>Two-Component Dust"]
        IGM["Redshift & Madau (1995)<br/>IGM Attenuation"]
        Proj["In-Flight Filter Matrix<br/>Spectra @ M_filter"]
    end

    subgraph Output ["Target Products (Zarr)"]
        Phot["photometry.zarr<br/>(N x B Photometry)"]
    end

    SSP -.->|"broadcast once"| GEMM
    GAL -->|"stream (chunk x K)"| GEMM
    GEMM --> Dust --> IGM --> Proj --> Phot
```

For each galaxy $g$, composite stellar flux is modeled with Charlot & Fall (2000) two-component dust attenuation:

$$F_g(\lambda) = D_g(\lambda) \cdot \left[ \sum_{k \in \text{old}} \text{SFH}[g,k]\,\text{SSP}[k,\lambda] + B_g(\lambda)\sum_{k \in \text{young}} \text{SFH}[g,k]\,\text{SSP}[k,\lambda] \right]$$

---

## 4. Core Capabilities

| Capability | Summary | Documentation |
| :--- | :--- | :--- |
| **SSP Library Adapters** | Bruzual & Charlot (2003) `.ised`/ASCII, E-MILES/MILES FITS, FSPS (`python-fsps` & `spstot_*.spec`), BPASS v2.2+, generic 3D FITS/HDF5/NPZ | [SSP Adapters Guide](docs/guides/adapters.md) |
| **Catalog Ingestion** | Native Parquet, FITS, HDF5, CSV (streaming), and NPZ ingestion for IllustrisTNG, EAGLE, CAMELS, and SAM catalogs | [Catalogs & Photometry](docs/guides/catalogs-and-photometry.md) |
| **Cosmology & Filters** | `FlatLambdaCDM` (default Concordance $H_0=70.0$, $\Omega_m=0.3$, Planck 2018/2015, or custom), Snapshot & Lightcone modes, Madau (1995) IGM, 16 calibrated JWST, HST, and SDSS filters | [Catalogs & Photometry](docs/guides/catalogs-and-photometry.md) |
| **Distributed & GPU Scaling** | Dask (`sync`, `threads`, `local`, Kubernetes), `--batch-chunks` scheduler guard, `s3://`/`gs://`/`abfs://`, CuPy CUDA BLAS | [Distributed & GPU Guide](docs/guides/distributed-and-gpu.md) |
| **Scientific Validation** | Cross-validation against Astropy cosmology, float64 reference, optional live `python-fsps`/`DSPS`, and 4-tier Scientific Sentry QA | [Validation & Benchmarks](docs/guides/validation-and-benchmarks.md) |

---

## 5. Empirical Verification Summary

All headline benchmarks below are empirically measured and recorded in machine-readable JSON manifests under [`paper/`](paper/):

- **Numerical Accuracy**: Max relative spectral error `9.87e-7` (RMSE `2.24e-11`) against an independent `float64` reference (`paper/benchmark_manifest.json`).
- **TNG → JWST NIRCam Scientific Validation**: Max relative error `4.77e-8` (RMSE `5.59e-23`), $0.000\,\mathrm{mag}$ AB zero-point deviation, and throughput of $1{,}510.5\,\mathrm{gal/s}$ for in-memory GEMM contraction ($896.6\,\mathrm{gal/s}$ full end-to-end pipeline on multi-core CPU; $446.2\,\mathrm{gal/s}$ single-core laptop) over the curated 100-galaxy TNG-100 sample (`paper/benchmark_manifest_tng_jwst.json`).
- **Single-Node CPU vs. GPU**: `57,978 gal/s` on a 12-core workstation CPU (`scipy-openblas`). On an NVIDIA Tesla T4 GPU via CuPy, `specsynth` sustains `258,812 gal/s` end-to-end throughput (**4.51x speedup** relative to the paired cloud VM CPU baseline at `57,344 gal/s`, including host-device transfers; `paper/benchmark_manifest_gpu_t4.json`).
- **Memory Boundedness**: Single-process sequential chunk RSS stays flat at `261.5–261.8 MB` (< 0.2% variance) while streaming 100,000 to 1,000,000 galaxies in 20,000-galaxy chunks.
- **Multi-Node Kubernetes**: `53,814 gal/s` on a 3-node OCI OKE cluster backed by in-cluster shared NFS (100,000 galaxies in `1.86 s`, max rel. error `8.16e-7`, `paper/benchmark_manifest_oci_oke_3node.json`).
- **Projected Cluster Scaling**: Analytical scaling models estimate throughput of $> 1.5 \times 10^6\,\mathrm{gal/s}$ across 32 distributed workers ($10^8$ galaxies in $\sim 1.1\,\mathrm{min}$, $\approx \$0.01$ spot compute; clearly distinguished from empirical measurements).

See the full [Validation & Benchmarks Guide](docs/guides/validation-and-benchmarks.md) for reproduction commands and detailed tables, and the [Capability Maturity Matrix](docs/architecture/perandam_space_intelligence.md#4-capability-maturity-matrix) for an audit mapping every architectural claim to its verified codebase implementation and automated tests.

---

## 6. Canonical Reference Benchmark Dataset

A 100,000-galaxy lightcone benchmark catalog ($z \in [0.05, 3.8]$, 16 calibrated JWST/HST/SDSS bands in float64) is archived on Hugging Face with permanent DOI [`10.57967/hf/11635`](https://doi.org/10.57967/hf/11635):

```python
from datasets import load_dataset
ds = load_dataset("sreeganesh/specsynth-benchmark-100k")
```

---

## 7. Contributing, Code of Conduct & License

- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md) and open a [GitHub Issue](https://github.com/SankarGaneshb/specsynth/issues) or Pull Request.
- **Code of Conduct**: Governed by the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).
- **Citation**: See [CITATION.cff](CITATION.cff) for software citation metadata.
- **License**: Released under the [MIT License](LICENSE).
