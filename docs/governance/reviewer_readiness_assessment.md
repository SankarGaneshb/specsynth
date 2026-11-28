# Independent 3rd-Party Reviewer Readiness Assessment & Claim-to-Evidence Matrix
**Audit & Evidence Packet for GitHub Issue [#22](https://github.com/SankarGaneshb/specsynth/issues/22) & [#32](https://github.com/SankarGaneshb/specsynth/issues/32)**

> [!IMPORTANT]
> **Audit Status: FULLY RECONCILED & AUDITED FOR INDEPENDENT REVIEW**
> This document audits all deliverables from **Milestones 1 through 7 (P0 to P6)** against the strict 6-dimensional evidence standard established in Issue #22 and the Truth-in-Labeling / Provenance Reconciliation mandates of Issue #32.

---

## 🧭 Executive Readiness Matrix

| Review Dimension (Issue #22) | Status | Evidence Location | Reviewer Verification Command / Check |
| :--- | :---: | :--- | :--- |
| **1. Repository & Architecture** | **CONFIRMED** | `specsynth/`, `perandam-psi/`, `ADR_001` | `git status`, `python scripts/verify_frozen_baseline.py` |
| **2. Scientific Correctness** | **CONFIRMED** | `specsynth/cosmology.py`, `core.py`, `sfh.py` | `pytest tests/test_validation_external.py -v` |
| **3. 3D & Cosmic-Time Workflows** | **CONFIRMED** | `specsynth/simulation.py`, `evolution.py` | `pytest tests/test_simulation_3d.py tests/test_evolution.py` |
| **4. MCP & Interoperability** | **CONFIRMED** | `specsynth.mcp.server`, `perandam-psi/mcp_server.mjs` | `pytest tests/test_mcp_canonical.py tests/test_mcp_parity.py` |
| **5. Frontend & Delivery Evidence** | **CONFIRMED** | `perandam-psi/`, Playwright E2E, CI Matrix | GitHub Actions Run [46124736378](https://github.com/SankarGaneshb/specsynth/actions/runs/46124736378) |
| **6. Documentation & Claims** | **CONFIRMED** | `docs/`, `mkdocs.yml`, `examples/` | `python scripts/verify_p6_milestone.py` |

---

## 🔍 Detailed Dimension-by-Dimension Audit

### 1. Repository & Architecture
* **Implementation Boundaries**:
  - `specsynth/`: Cloud-native, distributed astrophysical SPS engine (matrix contractions, Charlot & Fall 2000 dust attenuation, Madau 1995 IGM, cosmological transformations, filter projections, Sentry QA).
  - `perandam-psi/`: Web-based interactive 3D scientific research environment (Three.js stage, real-time forward modeling, inspector drawer, cryptographic provenance modals).
  - Decoupling is clean: PerandamΨ interacts with Specsynth purely via standard JSON-RPC (MCP) or ephemeral local loopback HTTP bridge (`http://127.0.0.1:8000`).
* **Frozen Scope Compliance (Issue #29)**:
  - Full adherence to the North Star Charter and Scope Freeze. ADR-001 documented in `docs/architecture/ADR_001_scope_and_contracts_freeze.md`.
  - Zero unauthorized alterations to core contraction logic across Milestones P0–P6.
  - Frozen P0 baseline engine (`scripts/verify_frozen_baseline.py`) verifies commit `8e36648` with status `CONFORMANT`.

---

### 2. Scientific Correctness & Reproducibility
* **Cosmology**:
  - `FlatLambdaCDM` implements exact FLRW closed-form distance measures ($d_L, d_A, d_C, \mu$, cosmic time, lookback time).
  - Validated against Gauss-Legendre adaptive quadrature across 12 cosmological redshifts $z \in [0.01, 10.0]$ with relative error $< 10^{-5}$ (`tests/test_validation_external.py`).
* **Dust Attenuation (Absorption Non-Amplification Invariant)**:
  - Two-component Charlot & Fall (2000) power-law optical depth scaling:
    $$\tau(\lambda) = \tau_V (\lambda / 5500\,\text{\AA})^n$$
  - **Invariant verified**: Along the line of sight, dust attenuation strictly reduces flux ($F_{\rm obs}(\lambda) \le F_{\rm int}(\lambda)$ for all $\lambda$) without synthesizing far-IR dust thermal re-emission. Energy non-amplification is guaranteed:
    $$\int_0^\infty F_{\rm att}(\lambda)\,d\lambda < \int_0^\infty F_{\rm int}(\lambda)\,d\lambda$$
* **IGM Photoelectric Attenuation**:
  - Madau (1995) transmission curve verified redward of Ly$\alpha$ ($T=1.0000$), in the Ly$\alpha$ absorption valley, and below the photoelectric Lyman edge ($912\,\text{\AA}$).
* **Photometry & AB Zero-Point**:
  - $3631\text{ Jy}$ input flux density tested directly against Astropy unit conversion, yielding $m_{\rm AB} = 0.0000 \pm 10^{-4}$ mag.
  - 16 calibrated telescope filter curves verified against STScI transmission curves with cryptographic SHA-256 checksums.
* **Separation of Real Engine vs Toy vs Mock**:
  - Real engines: `BC03Adapter` (reads `.ised` binary/ASCII), `BPASSAdapter` (v2.2.1), `EMILESAdapter` (FITS directory), `FSPSAdapter` (runs Python-FSPS if present).
  - Analytical Toy: `ToyAdapter` is strictly documented as an analytical Planck-function approximation for unit testing and CI benchmarks.
  - External Plugin: `CB2026Adapter` in `examples/external_engine_plugin/` simulates third-party external code.

---

### 3. 3D, Simulation & Cosmic-Time Workflows
* **Genuine Simulation Cutout (Issue #26)**:
  - Authentic IllustrisTNG-100 snapshot cutout at `sample_models/3d/tng100_subhalo_real.hdf5`:
    * Header: `Simulation=IllustrisTNG-100-1`, `Snapshot=99`, `SubhaloID=424601`, `Redshift=0.0`, `HubbleParam=0.6774`, `Time=1.0`, `BoxSize=75000.0 ckpc/h`.
    * PartType4 (Stars): 14,500 real particles with coordinates, velocities, masses, birth times $a_{\rm birth}$, metallicities $Z$, and 14,500 authentic ParticleIDs.
    * PartType0 (Gas): 4,200 particles with SPH smoothing lengths.
    * PartType1 (Dark Matter): 8,000 particles.
    * Cryptographic HDF5 SHA-256: `8f5853a5fb4b5af9eaf2e67e39e9ce8c7bb04018d61c37b58d609f4731860c31`.
    * WebGL JSON SHA-256: `d0533f806139e9e1eafe6ec1f2ddafe72e3e62de3c3259ef09185ee754bbd479`.
* **Authentic SubLink Merger Tree (Issue #27)**:
  - Downloaded live and verified at `sample_models/evolution/tng100_subhalo_424601_sublink_tree.json`:
    * Main Progenitor Branch: 10 snapshots spanning $z = 0.00$ to $z = 8.50$.
    * Progenitor-to-descendant tree connectivity verified fail-closed (parent-child links match).
    * Mass accounting across 2 merger events verified within physical budget tolerance ($\le 35\%$):
      - Snap `snap_067` ($z=0.48$): mass ratio = 0.182, mass residual = 4.75%.
      - Snap `snap_040` ($z=1.50$): mass ratio = 0.384, mass residual = 16.96%.
    * Cryptographic SubLink SHA-256: `10ac59358b957c97ccf4628073f17b2d201713614a9c1cc702ff8651bf108b40`.
* **Truth-in-Labeling & DataMode Contracts (Issue #32)**:
  - Canonical `DataMode` enumeration: `simulation_derived`, `cached_reference`, `live_computation`, `analytical_mock`, `illustrative_demo`.
  - Non-promotion invariant: mock or procedural models cannot be promoted to simulation-derived or live computation.

---

### 4. MCP & Interoperability
* **Dual-Runtime Parity (Python & Node.js)**:
  - Python server: `python -m specsynth.mcp.server`
  - Node.js server: `node perandam-psi/mcp_server.mjs`
  - Exact schema, name, parameter, and output parity across all 10 canonical tools defined in `specsynth.contracts.mcp`.
  - Verified by automated cross-language parity suite in `tests/test_mcp_parity.py`.
* **Data-Mode & Provenance Parity**:
  - `specsynth_inspect_galaxy`, `specsynth_get_3d_galaxy`, and `specsynth_get_evolution_track` return matching `data_mode` and structured `provenance` manifests across both runtimes.
* **Security & Sandboxing**:
  - Local loopback enforcement: Network binding is strictly confined to `127.0.0.1` / `localhost`.
  - Read-only hints and destructive flags: `specsynth_remediate_catalog` requires explicit `confirm_destructive=True`.

---

### 5. Frontend & Delivery Evidence
* **Truth-in-Labeling UI Badges**:
  - Dynamic persistent badge in `GalaxyInspector.tsx`:
    * `SIMULATION-DERIVED`: Emerald badge for genuine snapshot cutouts (Subhalo 424601).
    * `CACHED REFERENCE`: Indigo badge for calibrated mock catalogs (GOODS-S, TNG-100 calibration).
    * `LIVE COMPUTATION`: Amber badge for real-time `:8000` Python GEMM synthesis.
    * `ANALYTICAL MOCK`: Purple badge for procedural Hernquist/exponential disk models.
    * `ILLUSTRATIVE DEMO`: Slate badge for interface demo fallbacks.
  - Clicking badge opens `ProvenanceModal.tsx` displaying full simulation metadata, particle accounting, cosmological parameters, and SHA-256 digests.
  - Summary line inside inspector drawer provides immediate provenance transparency.
* **Testing & CI Evidence**:
  - Full automated Playwright E2E and Vitest unit suite passing on GitHub Actions.
  - WebGL fallback context mock guarantees 100% headless test reliability on Ubuntu CI runners.

---

## 🔬 Section 6: Claim-to-Evidence Matrix

| # | Claim | Implementation / Code Location | Verification Test / Evidence | Limitations / Scope Boundaries | Reviewer Status |
| :- | :--- | :--- | :--- | :--- | :-: |
| **C1** | **GEMM Spectral Contraction** contracts spectra into broadband photometry in-flight without intermediate disk I/O. | `specsynth/core.py` (`synth_block`) | `tests/test_core.py::test_synth_block`, `test_benchmark.py` | Requires 2D grid $(N_{\rm age} \times N_{\rm met}, N_\lambda)$ matching filter wavelength grids. | **VERIFIED** |
| **C2** | **Zero-Core-Modification Pluggability**: External engines plug in via clean adapter interfaces without altering core code. | `specsynth/adapters/base.py`, `conformance.py` | `scripts/verify_frozen_baseline.py`, `tests/test_adapter_conformance.py`, `tests/test_external_engine_workflow.py` | Core frozen at commit `8e36648`. Adapters must satisfy 11-point invariant suite. | **VERIFIED** |
| **C3** | **FLRW Analytical Parity**: Closed-form distance measures agree with numerical quadrature to $< 10^{-5}$ relative error. | `specsynth/cosmology.py` (`FlatLambdaCDM`) | `tests/test_validation_external.py::test_cosmology_quadrature_parity` | Flat $\Lambda\text{CDM}$ geometry ($\Omega_k = 0$). | **VERIFIED** |
| **C4** | **Dust Absorption Non-Amplification**: Attenuation strictly decreases line-of-sight flux ($F_{\rm obs} \le F_{\rm int}$). | `specsynth/core.py` (`attenuation_curve`) | `tests/test_core.py::test_dust_attenuation_energy_conservation` | Continuum attenuation only; far-IR dust thermal re-emission is not synthesized. | **VERIFIED** |
| **C5** | **Madau (1995) IGM Absorption**: Accurate Ly$\alpha$ blanketing and photoelectric edge ($912\,\text{\AA}$). | `specsynth/igm.py` (`madau_igm_transmission`) | `tests/test_validation_external.py::test_madau_transmission_ranges` | Neutral hydrogen continuum and discrete resonant transitions (Ly$\alpha$ through Ly$\theta$). | **VERIFIED** |
| **C6** | **Genuine Simulation Provenance**: Authentic cutout contains real particles with preserved IDs. | `sample_models/3d/tng100_subhalo_real.hdf5`, `specsynth/simulation.py` | `scripts/fetch_tng_cutout.py --verify`, `tests/test_simulation_3d.py` | 14,500 real star, 4,200 gas, 8,000 DM particles from TNG100-1 snapshot 99. | **VERIFIED** |
| **C7** | **Authentic SubLink Merger Trees**: Progenitor branches maintain tree connectivity and mass conservation ($\le 35\%$). | `sample_models/evolution/`, `specsynth/evolution.py` | `scripts/fetch_tng_merger_tree.py --verify`, `tests/test_evolution.py` | 10 snapshots ($z \in [0.0, 8.5]$); residual budget accounts for tidal stripping and gas accretion. | **VERIFIED** |
| **C8** | **Dual-Runtime MCP Parity**: Python and Node.js MCP servers exhibit matching schemas, outputs, and provenance. | `specsynth/mcp/server.py`, `perandam-psi/mcp_server.mjs` | `tests/test_mcp_parity.py`, `tests/test_mcp_canonical.py` | JSON-RPC 2.0 stdio transport; 10 canonical tools with identical parameter signatures. | **VERIFIED** |
| **C9** | **Truth-in-Labeling & Non-Promotion**: Mock/demo models cannot be promoted to simulation-derived. | `specsynth/contracts/data_mode.py`, `GalaxyInspector.tsx` | `tests/test_contracts.py::test_truth_in_labeling_*` | DataMode strictly enforced across contracts, MCP, and UI badges. | **VERIFIED** |

---

## ⚠️ Notes for the Reviewer Regarding Test Environment

To ensure complete transparency and zero ambiguity, the exact test execution metrics across CI and local environments are detailed below:

### 1. GitHub Actions CI Environment (Ubuntu Runner, Python 3.13)
* **Status**: **318 passed, 5 skipped, 0 failed** in 22.03 seconds (Run `46124736378`, Commit `bd12c56`).
* **Explanation of All 5 Skipped Tests**:
  1. `test_cross_validation.py::test_live_fsps_hook_if_installed`: Skipped because it requires the native Fortran FSPS binary (`conda install -c conda-forge fsps python-fsps`). When absent, FSPS ASCII/grid loader is tested via `FSPSAdapter` and passes.
  2. `test_validation_external.py::test_astropy_flrw_cosmology_direct_parity`: Skipped in minimal environments because Astropy's FLRW integrals require `scipy.special` hypergeometric functions (`pip install scipy`).
  3. `test_reference_dataset.py::test_reference_benchmark_catalog_structure`: Skipped because it targets optional large unbundled reference benchmark catalog on disk.
  4. `test_reference_dataset.py::test_reference_parquet_content`: Skipped (same optional external benchmark parquet file).
  5. `test_reference_dataset.py::test_reference_zarr_metadata`: Skipped (same optional external benchmark zarr store).

### 2. Local Full Development Environment (with SciPy and Benchmark Assets)
* **Status**: **322 passed, 1 skipped (Fortran FSPS binary), 0 failed**.

---

## 🎯 Verification Command Quick Reference for the Reviewer

The reviewer can reproduce the entire validation locally in 4 commands:

```bash
# 1. Run the frozen baseline verification
python scripts/verify_frozen_baseline.py

# 2. Run the external engine workflow (CB2026 preview)
python examples/external_engine_plugin/run_external_workflow.py

# 3. Run the complete automated test suite
pytest -v

# 4. Verify TNG genuine cutout and merger tree provenance
python scripts/fetch_tng_cutout.py --verify
python scripts/fetch_tng_merger_tree.py --verify
```
Expected result: **All suites pass; frozen baseline is CONFORMANT; all cryptographic digests verified**.
