# Parking Lot — Specsynth Scope Freeze

This document captures valuable ideas, prospective features, research explorations, and optimizations that arise during development but **do not directly advance the core Specsynth Goal**.

Per our **Scope Freeze Directive**, these items are parked to preserve engineering focus on the 4 Core Pillars. They will not be worked on until the core goal is fully achieved.

---

## 🎯 The Stated Goal (North Star)
> *"An independent astrophysicist should be able to plug their own simulation, galaxy-modelling, or spectral-synthesis engine into the Specsynth ecosystem; generate scientifically reproducible 3D galaxy models and synthetic observations; interactively explore galaxies across cosmic time; and make these capabilities accessible through MCP — without modifying the core framework."*

---

## 🛑 Scope Evaluation Checklist
Before any item leaves the parking lot or any new task is accepted into active development, it must answer **YES** to at least one of these questions:
1. Does it enable an astrophysicist to plug in their own simulation / galaxy model / SPS engine without touching core code?
2. Does it improve the scientific reproducibility or fidelity of 3D galaxy models and synthetic observations?
3. Does it enhance interactive multi-epoch / cosmic-time exploration for the researcher?
4. Does it expose or harden these capabilities over the Model Context Protocol (MCP)?

If the answer is **NO** to all four, it goes directly to this Parking Lot.

---

## 📋 Parked Initiatives

| ID | Title / Concept | Description | Why Parked (Out of Current Scope) | Trigger for Re-Evaluation |
|---|---|---|---|---|
| *PL-001* | *Non-astronomical / general Dask pipeline optimizations* | Arbitrary micro-benchmarks or generic scheduler tuning not impacting SPS contraction | Does not advance domain-specific SPS / 3D exploration goals | Once end-to-end plugin workflow benchmarks run on survey-scale data |
| *PL-002* | *Native Mobile App for Perandam* | Dedicated iOS/Android wrappers or React Native client | Perandam PSI responsive web app satisfies interactive browser exploration | Post-v1.0 release |
| *PL-003* | *Custom deep learning generative priors for SED fitting* | Training novel VAE/Diffusion models for synthetic galaxy generation | Out-of-scope; Specsynth contracts physical simulations and empirical models | When third-party ML adapters request external integration |
| *PL-004* | *Multi-morphology 3D subhalo benchmark suite (disks, ellipticals, starbursts)* | Curating an extensive multi-morphology library of bundled simulation cutouts beyond the primary reference subhalo | Expanding catalog diversity deferred; primary single-subhalo 3D pipeline fulfills P2 | Post-P6 programme completion |
| *PL-005* | *Material for MkDocs EOL & Zensical Migration* | Material for MkDocs reaches EOL on May 5, 2027; Zensical is its official maintained successor. Upstream warning disabled via `NO_MKDOCS_2_WARNING=1`. | Upstream tooling deprecation does not impact core scientific synthesis, 3D pipelines, or MCP interoperability. | Evaluate migration in late 2026/early 2027 or when Zensical releases stable v1.0. |
| *PL-006* | *Automated Interactive Adapter Linter & Actionable Fix Generator* | Dedicated CLI command (e.g. `specsynth diagnose-adapter --suggest-fixes`) that interactively guides an astrophysicist through complex multi-parameter divergence in external models | 16-point programmatic conformance suite and quick-lookup diagnostics guide in docs fulfill current P6 requirements | Post-P6 adoption feedback from external research groups |

---
*(Add new parked items above as they arise during research or conversation)*
