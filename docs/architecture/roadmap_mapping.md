# Roadmap Codebase Mapping & Implementation Status

This document establishes the official trace between the active codebase and the **MUST Delivery Milestones** (P0–P6) defined in Master Issue [#13](https://github.com/SankarGaneshb/specsynth/issues/13).

---

## 1. Traceability Matrix: Roadmap IDs to Source Code

| Roadmap ID | Milestone Title | Primary Modules / Components | Implementation Status | Notes & Blockers |
|---|---|---|---|---|
| **P0** ([#14](https://github.com/SankarGaneshb/specsynth/issues/14)) | **Scope & Architecture Freeze** | `specsynth.contracts`, `specsynth.adapters.base`, `docs/architecture/ADR_001` | **VALIDATED** | Versioned contracts defined for SSP, Simulation, 3D, Photometry, MCP. Dynamic adapter registry active. Immutable Baseline: `8e36648d7bad3959cdd8ed32c0232f0370fec461` (tag `p0-architecture-freeze`). |
| **P1** ([#15](https://github.com/SankarGaneshb/specsynth/issues/15)) | **Scientific Engine Foundation & Spectra** | `specsynth.sfh`, `specsynth.provenance`, `specsynth.core`, `specsynth.cosmology`, `specsynth.igm`, `specsynth.filters`, `specsynth.adapters.fsps` | **VALIDATED** | Multi-Z grid parsing & export active; SFH mass conservation verified; Astropy reference parity confirmed; Real-galaxy benchmark passing within 0.005 mag. |
| **P2** ([#16](https://github.com/SankarGaneshb/specsynth/issues/16)) | **Simulation-Derived 3D Galaxy Foundation** | `specsynth.simulation`, `specsynth.transforms`, `specsynth.contracts.galaxy3d`, `sample_models/3d/`, `perandam-psi/src/components/MilkyWayComparator3D.tsx` | **VALIDATED** | Complete simulation ingestion pipeline (HDF5/JSON); comoving-to-physical, CoM, and angular-momentum alignment; 3D-to-SFH matrix linking; 60 FPS WebGL decimation; Truth in Labeling enforced in PerandamΨ. |
| **P3** ([#17](https://github.com/SankarGaneshb/specsynth/issues/17)) | **Cosmic-Time & Galaxy Evolution** | `specsynth.evolution`, `specsynth.contracts.evolution`, `perandam-psi/src/components/LightconeCanvas3D.tsx`, `perandam-psi/src/components/CosmicTimeScrubber.tsx`, `scripts/verify_p3_milestone.py` | **VALIDATED** | FLRW cosmological lookback & age verified; `EvolutionaryTrackContract` v1.0.0 enforced; Leitner-Kravtsov (2011) stellar death recycling mass conservation verified; continuous Catmull-Rom 3D spline trajectory generation; Dual-mode 3D Lightcone rendering (Smooth Spline vs Discrete Steps) and interactive Cosmic Time Scrubber active. |
| **P4** ([#18](https://github.com/SankarGaneshb/specsynth/issues/18)) | **Python and Node MCP Interoperability** | `specsynth.mcp.server`, `specsynth.mcp.bridge`, `perandam-psi/mcp_server.mjs`, `specsynth.contracts.mcp` | **VALIDATED** | Complete dual-language protocol parity; canonical `specsynth_*` tool suite (10/10) implemented across Python and Node.js with seamless `sps_*` and `psi_*` legacy aliasing; exact FLRW numerical parity verified (< 0.05% rel error); HTTP bridge REST endpoints active. |
| **P5** ([#19](https://github.com/SankarGaneshb/specsynth/issues/19)) | **Live PerandamΨ Research Environment** | `perandam-psi/src/App.tsx`, `GalaxyInspector.tsx`, `SedPlot.tsx`, `PhotometryBar.tsx` | **PROTOTYPE** | Rich browser UI running with mock/calibration data; needs live service connection to Python backend and explicit Live/Cached labeling (M6.1). |
| **P6** ([#20](https://github.com/SankarGaneshb/specsynth/issues/20)) | **Independent Developer & External Validation** | `tests/test_validation_external.py`, `specsynth.adapters` entry points, `docs/guides/` | **PLANNED** | Conformance test suite and standalone third-party adapter template to be published. |

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
