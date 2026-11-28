# Roadmap Codebase Mapping & Implementation Status

This document establishes the official trace between the active codebase, the **MUST Delivery Milestones** (P0–P6) defined in Master Issue [#13](https://github.com/SankarGaneshb/specsynth/issues/13), and GitHub Milestone numbering.

---

## 1. Canonical Milestone & Phase Reconciliation Matrix (P0–P6)

> [!IMPORTANT]
> **Numbering Reconciliation & Disambiguation Standard**:
> - The Master Programme defines **7 MUST delivery phases** designated **P0 through P6** (there is **no P7**; 7 total phases are indexed from 0 to 6).
> - GitHub Milestones are auto-indexed with positive non-zero integers (1 to 7).
> - Therefore: **GitHub Milestone #N corresponds to Roadmap Phase $P_{N-1}$** ($N \in [1, 7]$).
> - To eliminate ambiguity, all code, documentation, verification scripts, and commit messages must use the canonical **`Milestone P<N>`** format (or explicit dual labeling: `Milestone P<N> (GitHub Milestone #<N+1>)`).
> - The pre-roadmap demonstration package (`TNG–JWST Scientific Validation v1.0`, Issue #2) is historically referred to as "Milestone 1 (Demonstration Package)" and predates the Master Programme.

| Roadmap Phase | GitHub Milestone | Master Issue | Follow-Up Workitems | Milestone Title | Primary Modules / Components | Implementation Status |
|:---:|:---:|:---:|:---:|---|---|:---:|
| **P0** | **#1** | [#14](https://github.com/SankarGaneshb/specsynth/issues/14) | [#29](https://github.com/SankarGaneshb/specsynth/issues/29) | **Scope & Architecture Freeze** | `specsynth.contracts`, `specsynth.adapters.base`, `docs/architecture/ADR_001` | **VALIDATED** |
| **P1** | **#2** | [#15](https://github.com/SankarGaneshb/specsynth/issues/15) | [#28](https://github.com/SankarGaneshb/specsynth/issues/28), [#31](https://github.com/SankarGaneshb/specsynth/issues/31) | **Scientific Engine Foundation & Spectra** | `specsynth.sfh`, `specsynth.provenance`, `specsynth.core`, `specsynth.cosmology`, `specsynth.igm`, `specsynth.filters`, `specsynth.adapters.fsps` | **VALIDATED** |
| **P2** | **#3** | [#16](https://github.com/SankarGaneshb/specsynth/issues/16) | [#26](https://github.com/SankarGaneshb/specsynth/issues/26) | **Simulation-Derived 3D Galaxy Foundation** | `specsynth.simulation`, `specsynth.transforms`, `specsynth.contracts.galaxy3d`, `sample_models/3d/`, `perandam-psi/src/components/MilkyWayComparator3D.tsx` | **VALIDATED** |
| **P3** | **#4** | [#17](https://github.com/SankarGaneshb/specsynth/issues/17) | [#27](https://github.com/SankarGaneshb/specsynth/issues/27) | **Cosmic-Time & Galaxy Evolution** | `specsynth.evolution`, `specsynth.contracts.evolution`, `perandam-psi/src/components/LightconeCanvas3D.tsx`, `perandam-psi/src/components/CosmicTimeScrubber.tsx` | **VALIDATED** |
| **P4** | **#5** | [#18](https://github.com/SankarGaneshb/specsynth/issues/18) | [#30](https://github.com/SankarGaneshb/specsynth/issues/30) | **Python and Node MCP Interoperability** | `specsynth.mcp.server`, `specsynth.mcp.bridge`, `perandam-psi/mcp_server.mjs`, `specsynth.contracts.mcp` | **VALIDATED** |
| **P5** | **#6** | [#19](https://github.com/SankarGaneshb/specsynth/issues/19) | [#32](https://github.com/SankarGaneshb/specsynth/issues/32) | **Live PerandamΨ Research Environment** | `perandam-psi/src/App.tsx`, `GalaxyInspector.tsx`, `SedPlot.tsx`, `PhotometryBar.tsx` | **PROTOTYPE** |
| **P6** | **#7** | [#20](https://github.com/SankarGaneshb/specsynth/issues/20) | [#28](https://github.com/SankarGaneshb/specsynth/issues/28), [#29](https://github.com/SankarGaneshb/specsynth/issues/29), [#30](https://github.com/SankarGaneshb/specsynth/issues/30) | **Independent Developer & External Validation** | `tests/test_validation_external.py`, `specsynth.adapters` entry points, `docs/guides/` | **VALIDATED** |

---

## 2. Traceability Matrix: Roadmap IDs to Detailed Evidence

| Roadmap ID | Milestone Title | Primary Verification Scripts | Baseline & Acceptance Notes |
|---|---|---|---|
| **P0** | **Scope & Architecture Freeze** | `scripts/verify_p0_milestone.py`, `scripts/verify_frozen_baseline.py` | Versioned contracts defined for SSP, Simulation, 3D, Photometry, MCP. Dynamic adapter registry active. Immutable Baseline: `8e36648d7bad3959cdd8ed32c0232f0370fec461` (tag `p0-architecture-freeze`). |
| **P1** | **Scientific Engine Foundation & Spectra** | `scripts/verify_p1_scientific_validation.py`, `tests/test_validation_external.py` | Multi-Z grid parsing & export active; SFH mass conservation verified; Astropy reference parity confirmed (< 1.36e-13 rel err); Real-galaxy benchmark passing within 0.005 mag. Non-amplification invariant strictly audited. |
| **P2** | **Simulation-Derived 3D Galaxy Foundation** | `scripts/verify_p2_milestone.py`, `scripts/fetch_tng_cutout.py` | Complete simulation ingestion pipeline (HDF5/JSON); comoving-to-physical, CoM, and angular-momentum alignment; 3D-to-SFH matrix linking; 60 FPS WebGL decimation; Truth in Labeling enforced in PerandamΨ. Real TNG cutout verified fail-closed. |
| **P3** | **Cosmic-Time & Galaxy Evolution** | `scripts/verify_p3_milestone.py`, `scripts/verify_p3_evolution.py` | FLRW cosmological lookback & age verified; `EvolutionaryTrackContract` v1.0.0 enforced; Leitner-Kravtsov (2011) stellar death recycling mass conservation verified; Catmull-Rom 3D spline trajectory generation; live SubLink merger tree verified fail-closed. |
| **P4** | **Python and Node MCP Interoperability** | `scripts/verify_p4_milestone.py`, `scripts/verify_p4_mcp_transport.py` | Complete dual-language protocol parity; canonical `specsynth_*` tool suite (10/10) across Python and Node.js; independent out-of-process stdio transport client fully certified (7/7 criteria); exact FLRW numerical parity verified (< 0.0002% rel error). |
| **P5** | **Live PerandamΨ Research Environment** | `scripts/verify_p5_milestone.py`, Playwright E2E suite | Rich browser UI running with live backend connection (:8000) and standalone cache fallback; simulation-derived vs illustrative labels active. |
| **P6** | **Independent Developer & External Validation** | `scripts/verify_p6_milestone.py`, `scripts/verify_p6_external_engine.py`, `scripts/verify_frozen_baseline.py` | External adapter conformance suite (`CB2026Adapter`) passing; zero-core-modification against frozen P0 baseline audited (0 unauthorized drift); end-to-end synthetic observation workflow certified. |

---

## 2. Component Status Definitions

- **IMPLEMENTED**: Code exists and passes unit tests, but requires external physical validation.
- **PROTOTYPE**: Functional demonstration running in notebooks or frontend components, but not yet wired to production contracts.
- **PLANNED**: Specified in architecture documents and roadmap issues; pending implementation.
- **VALIDATED**: Proven against independent scientific reference data (Astropy/synphot/double-precision) with automated regression gates.

---

## 3. Technical Debt & Blocker Analysis

1. **FSPS Multi-Metallicity Parsing (Resolved in P1)**:
   - *Status*: RESOLVED. `parse_fsps_spec_file` and `FSPSAdapter` support robust age-major and met-major multi-Z headers, layout detection, and `.spec` table export.

2. **Procedural vs Simulation 3D Tagging (Resolved in P2.M3.7)**:
   - *Status*: RESOLVED. `Galaxy3DContract` strictly segregates `simulation_derived` from `procedural_illustrative` geometry. `MilkyWayComparator3D.tsx` renders empirical simulation particles with age-metallicity coloring and prominently displays the `SIMULATION-DERIVED` badge vs `PROVISIONALLY ILLUSTRATIVE` disclaimer in the 3D hologram nameplates and comparative matrix cards.

3. **Dual MCP Protocol Aliases (Resolved in P4.M5)**:
   - *Status*: RESOLVED. Both Python and Node.js MCP servers expose the unified canonical `specsynth_*` suite (10/10 tools) while providing 100% backward compatibility via `sps_*` and `psi_*` alias routing. Cross-language numerical parity on cosmology and evolutionary tracks verified.
