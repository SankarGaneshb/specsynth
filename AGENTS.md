# AGENTS.md — Operational Guide for AI Coding & Research Agents

## Project Overview
`specsynth` is an open-source distributed framework for scalable stellar population synthesis (SPS) and in-flight photometric forward-modeling built on Python 3.10+, Dask, Zarr (`fsspec`), NumPy/SciPy BLAS, and optional CuPy GPU acceleration. It eliminates intermediate full-spectrum storage by contracting spectra directly into broadband photometry in-flight.

## Repository Map
- `specsynth.py`: Primary CLI entry point (`make-ssp`, `make-sfh`, `import-catalog`, `synth`, `verify`, `benchmark`, `sentry`, `clean-catalog`, `sentry-agent`).
- `specsynth/`: Core package (matrix contractions, dust attenuation, Madau 1995 IGM, filter projections, `specsynth.adapters`, `specsynth.sentry`, `specsynth.tools`, and `specsynth.agent`).
- `tests/`: Automated `pytest` suite (143 unit & integration tests, 88% coverage, strict tier markers, including `test_validation_external.py`).
- `k8s/`: Kubernetes manifests for Dask Operator cluster deployment (`dask-cluster.yaml`, `synth-job.yaml`).
- `paper/`: JOSS manuscript (`paper/paper.md`) and benchmark verification artifacts.
- `scripts/clean.py`, `test.ps1`, `test.bat`: Cross-platform test runners and workspace cleanup utilities.

## Standard Commands
- **Install dependencies:** `pip install -r requirements.txt`
- **Run test suite:** `pytest -v` (or `.\test.ps1` on Windows PowerShell to run tests and clean temporary Zarr caches)
- **End-to-end smoke test:**
  ```bash
  python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB make-ssp --adapter toy --n-age 40 --n-met 4 --n-wave 2000
  python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB make-sfh --n-gal 50000 --chunk 10000
  python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB synth --filters jwst_nircam --redshift 2.5 --igm
  python specsynth.py --base /tmp/run1 verify
