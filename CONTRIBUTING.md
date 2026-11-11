# Contributing to `specsynth`

Thank you for your interest in contributing to `specsynth`! We welcome bug reports, feature requests, documentation improvements, new SSP library adapters, and performance benchmarks from the astrophysics and high-performance computing communities.

---

## 1. Seeking Support & Asking Questions

If you have questions about running `specsynth`, configuring Dask schedulers on cloud Kubernetes clusters, or integrating custom SSP grids:
- Open a [GitHub Issue](https://github.com/SankarGaneshb/specsynth/issues) using a descriptive title.
- Include your OS, Python version, installed `dask`/`zarr` versions, and the CLI command or snippet you are running.

---

## 2. Reporting Bugs & Issues

When reporting a bug, please include:
1. A concise description of the unexpected behavior vs. expected output.
2. Steps to reproduce (preferably using the built-in `--adapter toy` or a minimal dataset).
3. The full error traceback or log output.
4. Your hardware/environment summary (`python specsynth.py benchmark --n-gal 1000 --output env.json` captures system specs automatically).

---

## 3. Submitting Code Changes (Pull Requests)

To contribute code, adapters, or tests:

1. **Fork & Clone**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/specsynth.git
   cd specsynth
   ```
2. **Set Up a Development Environment**:
   ```bash
   python -m venv .venv
   # Windows: .\.venv\Scripts\Activate.ps1
   # Linux/macOS: source .venv/bin/activate
   pip install -e ".[test,astro]"
   ```
3. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/my-ssp-adapter
   ```
4. **Implement & Add Unit Tests**:
   - Place new tests under `tests/`.
   - Ensure numerical accuracy checks against float64 references pass (`< 5e-4` relative tolerance).
5. **Run the Full Test Suite**:
   ```bash
   pytest -v
   # Or on Windows PowerShell (with automatic cache cleanup):
   .\test.ps1
   ```
6. **Submit a Pull Request**:
   - Push your branch and open a PR against `main`.
   - Ensure all automated tests pass and update `README.md` if CLI flags change.

---

## 4. Code of Conduct

Contributors and maintainers agree to foster an open, welcoming, and harassment-free scientific software community. Respectful, constructive technical feedback is expected in all issues, pull requests, and reviews.
