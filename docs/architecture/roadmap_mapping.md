# Roadmap Codebase Mapping & Implementation Status

This document establishes the official trace between the active codebase and the **MUST Delivery Milestones** (P0–P6) defined in Master Issue [#13](https://github.com/SankarGaneshb/specsynth/issues/13).

---

## 1. Traceability Matrix: Roadmap IDs to Source Code

| Roadmap ID | Milestone Title | Primary Modules / Components | Implementation Status | Notes & Blockers |
|---|---|---|---|---|
| **P0** ([#14](https://github.com/SankarGaneshb/specsynth/issues/14)) | **Scope & Architecture Freeze** | `specsynth.contracts`, `specsynth.adapters.base`, `docs/architecture/ADR_001` | **VALIDATED** | Versioned contracts defined for SSP, Simulation, 3D, Photometry, MCP. Dynamic adapter registry active. |
| **P1** ([#15](https://github.com/SankarGaneshb/specsynth/issues/15)) | **Scientific Engine Foundation & Spectra** | `specsynth.sfh`, `specsynth.provenance`, `specsynth.core`, `specsynth.cosmology`, `specsynth.igm`, `specsynth.filters`, `specsynth.adapters.fsps` | **VALIDATED** | Multi-Z grid parsing & export active; SFH mass conservation verified; Astropy reference parity confirmed; Real-galaxy benchmark passing within 0.005 mag. |
| **P2** ([#16](https://github.com/SankarGaneshb/specsynth/issues/16)) | **Simulation-Derived 3D Galaxy Foundation** | `specsynth.catalog`, `specsynth.contracts.galaxy3d`, `scripts/validate_tng_jwst.py`, `perandam-psi/src/components/MilkyWayComparator3D.tsx` | **PROTOTYPE** | TNG particle extraction demonstrated in prototype scripts; needs standard snapshot ingestion pipeline into `Galaxy3DContract` (M3.1-M3.5). |
| **P3** ([#17](https://github.com/SankarGaneshb/specsynth/issues/17)) | **Cosmic-Time & Galaxy Evolution** | `specsynth.cosmology`, `perandam-psi/src/components/LightconeCanvas3D.tsx`, `scripts/validate_tng_jwst.py` | **PROTOTYPE** | Cosmological distance and redshifting validated ($z \in [0.1, 10]$); merger-tree / progenitor lineage data needs live integration (M4.3). |
| **P4** ([#18](https://github.com/SankarGaneshb/specsynth/issues/18)) | **Python and Node MCP Interoperability** | `specsynth.mcp.server`, `specsynth.mcp.bridge`, `perandam-psi/mcp_server.mjs`, `specsynth.contracts.mcp` | **PROTOTYPE** | Dual MCP servers implemented; schema unification and canonical name aliasing (`specsynth_*` vs `psi_*`) in progress (M5.1-M5.5). |
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

2. **Procedural vs Simulation 3D Tagging (Blocker for P2.M3.7)**:
   - *Current State*: `MilkyWayComparator3D.tsx` renders illustrative morphological models alongside TNG statistics.
   - *Action*: Explicitly display `geometry_source: "procedural_illustrative"` badge in UI until live particle snapshots are ingested.

3. **Dual MCP Protocol Aliases (Blocker for P4.M5.4)**:
   - *Current State*: Python server uses `sps_*` tools; Node.js server uses `psi_*` tools.
   - *Action*: Support canonical `specsynth_*` names in both servers while maintaining backward-compatible aliases.
