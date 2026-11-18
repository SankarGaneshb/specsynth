# Contributing to `specsynth`

Contributions from the astrophysics, cosmology, and scientific computing communities are warmly welcomed—including bug reports, new SSP library adapters, calibrated survey filter sets, cross-code validation benchmarks, and documentation improvements.

## How to Contribute

1. **Questions & Support**: Open a [GitHub Issue](https://github.com/SankarGaneshb/specsynth/issues) describing your environment, command, and scientific use case.
2. **Bug Reports**: Use the Bug Report issue template and include a minimal reproducible snippet (ideally using `--adapter toy`).
3. **Pull Requests**:
   - Fork the repository and create a feature branch from `main`.
   - Install development dependencies: `pip install -e ".[test,astro,docs]"`.
   - Add unit tests under `tests/` and verify the full test suite passes (`pytest -v`).
   - Verify documentation builds cleanly (`mkdocs build --strict`).
   - Open a Pull Request describing the scientific or engineering rationale.

## Code of Conduct

All community interactions are governed by the [Contributor Covenant Code of Conduct](https://github.com/SankarGaneshb/specsynth/blob/main/CODE_OF_CONDUCT.md).
