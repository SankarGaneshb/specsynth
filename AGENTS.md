# AGENTS.md — Operational Guide for AI Coding & Research Agents

## 🎯 The North Star Goal & Scope Freeze Charter
> **"An independent astrophysicist should be able to plug their own simulation, galaxy-modelling, or spectral-synthesis engine into the Specsynth ecosystem; generate scientifically reproducible 3D galaxy models and synthetic observations; interactively explore galaxies across cosmic time; and make these capabilities accessible through MCP — without modifying the core framework."**

### Scope Freeze Directive
A strict scope freeze is established around this goal. Every feature, bug fix, experiment, research idea, and architectural decision must contribute directly to achieving it across its four core pillars:
1. **Zero-Core-Modification Pluggability**: Independent researchers can bring external simulations (TNG, EAGLE, FIRE, custom snapshots), galaxy models (SFH, chemical evolution, morphology), or SPS engines (FSPS, BC03, BPASS, EMILES, custom grids) via clean adapters and interfaces without hacking core framework code.
2. **Scientific Reproducibility & Synthetic Observations**: Deterministic, verified generation of 3D galaxy models, SEDs, and synthetic multi-band observations (JWST, HST, Roman, Euclid, Rubin) with strict physical invariants, unit conservation, and provenance.
3. **Interactive Exploration Across Cosmic Time**: Seamless, responsive multi-scale exploration of galaxies across redshift ($z \in [0, 10+]$) and cosmic epochs in 3D (e.g. Perandam PSI 3D lightcones and stage viewers).
4. **First-Class MCP Accessibility**: Expose these capabilities cleanly over Model Context Protocol (MCP) so external AI agents, IDEs, and frontends can drive workflows programmatically.

### Scope Guardian Protocol & Parking Lot
- **Guardian Duty**: The AI agent must act as an active scope guardian. If any request, refactor, or idea diverges from the 4 pillars—even if prompted by the user—the agent must explicitly pause, remind the user of the scope freeze, and route the item to [`PARKING_LOT.md`](PARKING_LOT.md).
- **Parking Lot**: Tangential, exploratory, or non-critical enhancements are cataloged in [`PARKING_LOT.md`](PARKING_LOT.md) without consuming engineering bandwidth.

---

## Project Overview
`specsynth` is an open-source distributed framework for scalable stellar population synthesis (SPS) and in-flight photometric forward-modeling built on Python 3.10+, Dask, Zarr (`fsspec`), NumPy/SciPy BLAS, and optional CuPy GPU acceleration. It eliminates intermediate full-spectrum storage by contracting spectra directly into broadband photometry in-flight.

## Repository Map
- `specsynth.py`: Primary CLI entry point (`make-ssp`, `make-sfh`, `import-catalog`, `synth`, `verify`, `benchmark`, `sentry`, `clean-catalog`, `sentry-agent`).
- `specsynth/`: Core package (matrix contractions, dust attenuation, Madau 1995 IGM, filter projections, `specsynth.adapters`, `specsynth.sentry`, `specsynth.tools`, `specsynth.mcp`, and `specsynth.agent`).
- `perandam-psi/`: Interactive scientific web application (3D Multi-Galaxy Stage, real-time forward modeling, JWST NIRCam photometry, SED inspection).
- `tests/`: Automated `pytest` suite (159 unit & integration tests, 88% coverage, strict tier markers, including `test_validation_external.py`).
- `k8s/`: Kubernetes manifests for Dask Operator cluster deployment (`dask-cluster.yaml`, `synth-job.yaml`).
- `paper/`: JOSS manuscript (`paper/paper.md`) and benchmark verification artifacts.
- `scripts/clean.py`, `test.ps1`, `test.bat`: Cross-platform test runners and workspace cleanup utilities.
- `PARKING_LOT.md`: Registry for ideas and enhancements deferred under the scope freeze.

## Standard Commands
- **Install dependencies:** `pip install -r requirements.txt`
- **Run test suite:** `pytest -v` (or `.\test.ps1` on Windows PowerShell to run tests and clean temporary Zarr caches)
- **End-to-end smoke test:**
  ```bash
  python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB make-ssp --adapter toy --n-age 40 --n-met 4 --n-wave 2000
  python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB make-sfh --n-gal 50000 --chunk 10000
  python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB synth --filters jwst_nircam --redshift 2.5 --igm
  python specsynth.py --base /tmp/run1 verify
  ```
