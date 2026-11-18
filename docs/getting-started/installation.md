# Installation

`specsynth` requires **Python 3.10 or newer**.

## Standard Installation (From Source)

Clone the repository and install in editable or standard mode using `pip`:

```bash
git clone https://github.com/SankarGaneshb/specsynth.git
cd specsynth
python -m venv .venv

# Activate virtual environment:
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -e .
```

## Optional Dependency Extras

Install only the extras required for your workflow:

| Extra | Command | Included Packages | Use Case |
| :--- | :--- | :--- | :--- |
| **`astro`** | `pip install -e ".[astro]"` | `astropy`, `h5py`, `pyarrow` | FITS, HDF5, Parquet catalog ingestion & E-MILES/FITS grids |
| **`storage`** | `pip install -e ".[storage]"` | `s3fs`, `gcsfs`, `adlfs` | Cloud object stores (`s3://`, `gs://`, `abfs://`) |
| **`gpu`** | `pip install -e ".[gpu]"` | `cupy-cuda12x` | NVIDIA CUDA GPU GEMM acceleration |
| **`test`** | `pip install -e ".[test]"` | `pytest`, `pytest-cov`, `astropy`, `h5py` | Running the automated scientific test suite |
| **`docs`** | `pip install -e ".[docs]"` | `mkdocs`, `mkdocs-material`, `mkdocstrings[python]` | Building this documentation locally |

Multiple extras can be combined:

```bash
pip install -e ".[astro,storage,test]"
```

### Optional External SPS Libraries (for Live Cross-Validation)

- **`python-fsps`** (requires a Fortran compiler and `SPS_HOME` data files):
  ```bash
  conda install -c conda-forge fsps python-fsps
  ```
- **`dsps`** (JAX-based differentiable SPS, Linux/macOS recommended):
  ```bash
  pip install dsps jax
  ```

> **Note:** `specsynth` does **not** require `python-fsps` or `dsps` to run. Pre-exported BC03 (`.ised`/ASCII), E-MILES (FITS), FSPS (`spstot_*.spec`), and generic FITS/HDF5/NPZ grids are ingested natively.

## Verifying Your Installation

Run the unit and scientific validation test suite:

```bash
pytest -v
```

To verify CLI availability:

```bash
specsynth --help
# or via the standalone entry point:
python specsynth.py --help
```

## Container Image (Docker / Kubernetes)

A multi-stage `Dockerfile` is included for reproducible Linux and Kubernetes Dask deployments:

```bash
docker build -t specsynth:latest .
docker run --rm specsynth:latest specsynth --help
```
