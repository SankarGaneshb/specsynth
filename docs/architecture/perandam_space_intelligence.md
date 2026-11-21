# Perandam Space Intelligence (PSI / PerandamΨ)
## Master Architectural Blueprint & System Specification

> **Organization**: Perandam Space Intelligence (PSI)  
> **Brand & Signature Mark**: PerandamΨ  
> **Tagline**: *AI-Native Computational Astrophysics*  
> **Core Mission**: Lowering the barrier to entry for the next generation of astrophysicists by unifying deterministic stellar population synthesis, real-time visual deep-field exploration, and autonomous agentic intelligence.

---

```
Perandam
└── Perandam Space Intelligence (PSI / PerandamΨ)
    ├── PSI Space      (Stellarium-inspired 60fps WebGL/Canvas interactive deep-field sky view)
    ├── PSI Explorer   (Detailed galaxy inspection card, rest-frame SED, filter footprints, live sliders)
    ├── PSI Atlas      (Mock survey catalogs: TNG, Roman, JWST, Euclid, synthetic deep fields)
    ├── PSI Compute    (SpecSynth in-flight contraction engine: Dask, BLAS, GPU, Zarr streaming)
    ├── PSI Agent      (SentryAgent & Model Context Protocol server for autonomous research reasoning)
    ├── PSI Notebook   (Interactive analytics, reproducible Jupyter notebooks & Python exports)
    └── PSI Publish    (Publication figures, JOSS/ApJ data bundles & reproducibility manifests)
```

---

## 1. Etymology, Physics, and Dual Heritage

### 1.1 The Classical Tamil Cosmological Root: *Perandam* (பேரண்டம்)
- **பேர் / பெரு (*Per / Peru*)**: Great, vast, cosmic, macro, infinite.
- **அண்டம் (*Andam*)**: The celestial egg, galaxy cluster, macrocosm, universe.
- In ancient Tamil cosmology and modern astronomy, **பேரண்டம் (*Perandam*)** denotes the entirety of the physical macrocosm—the infinite expanse containing billions of galaxies.

### 1.2 The Mathematical Physics Foundation: $\Psi$ and $\psi(t)$
In theoretical astrophysics and cosmology, the Greek letter **$\Psi$ / $\psi$** is foundational:
1. **Star Formation History $\psi(t)$**: Across all stellar population synthesis (SPS) literature, the star formation rate over cosmic time is universally denoted by $\psi(t) \equiv \mathrm{SFR}(t)$.
2. **Cosmological Wavefunction $\Psi_{\text{universe}}$**: In quantum cosmology, $\Psi$ represents the state vector describing the geometry and birth of the cosmos.
3. **Visual Geometry**: The symmetrical trident shape of $\Psi$ physically echoes an astronomical telescope dish, a light cone expanding through spacetime, or a diverging spectral beam.

---

## 2. Seven Pillars of the PSI Ecosystem

### 2.1 PSI Space (The Interactive Sky)
A zero-install, GPU-accelerated 2D/WebGL canvas allowing researchers, educators, and students to pan and zoom through simulated cosmic deep fields at a fluid 60 frames per second.
- **Photometric True-Color Composites**: Renders synthetic galaxy points according to real telescope filter bandpasses (e.g. JWST NIRCam RGB: Red = F444W, Green = F200W, Blue = F090W).
- **Celestial Coordinates**: Displays dynamic Right Ascension (RA) and Declination (Dec) coordinate grids with adaptive zoom resolution.
- **Flux Scaling**: Dynamic logarithmic dynamic range compression ($L = \log(1 + I/I_0)$) prevents saturated bright targets from washing out faint, high-$z$ candidates.

### 2.2 PSI Explorer (The Deep Inspector)
When an astronomer clicks any galaxy in PSI Space, the PSI Explorer card slides into view:
- **Physical Metadata**: Stellar mass $M_*$, redshift $z$, instantaneous star formation rate $\psi$, and Charlot & Fall (2000) two-component dust optical depths ($\tau_{\text{diffuse}}, \tau_{\text{birth}}$).
- **Rest-Frame SED Overlay**: Renders composite stellar spectra across rest-frame wavelengths ($\lambda \in [912\,\text{Å}, 50{,}000\,\text{Å}]$) with translucent overlays of active instrument transmission curves.
- **Photometric Distribution**: Bar and point plots of synthetic fluxes across all chosen filter bands.
- **Real-Time Sliders**: Interactive parameter adjustments ($z$ and dust $A_V$) that re-evaluate the observed-frame SED and color coordinates on the fly.
- **Scientific Sentry Badge**: Live certification indicating that the galaxy's physical parameters and colors conform to physical boundary invariants.

### 2.3 PSI Atlas (The Catalog Repository)
A curated library of observational and cosmological simulation datasets:
- **IllustrisTNG**: Hydrodynamic cosmological simulation catalogs mapped directly into synthetic photometry.
- **Roman High-Latitude Survey Mock**: Wide-field cosmological mock catalogs.
- **JWST Deep Fields**: Synthetic deep fields modeled for NIRCam and MIRI surveys.
- **CosmoDC2 / Euclid**: Large-scale structure mock lightcones.

### 2.4 PSI Compute (The SpecSynth Core Engine)
The deterministic, mathematically exact back-end engine:
- In-flight GEMM matrix contraction ($S = \text{SFH} \cdot \text{SSP}$, $F = S \cdot T_{\text{filter}}$).
- Eliminates intermediate full-spectrum disk writes, reducing storage footprint by $250\times$.
- Charlot & Fall (2000) birth cloud and diffuse interstellar dust models.
- Madau (1995) intergalactic medium (IGM) attenuation with redshift-dependent resonant Ly$\alpha$ and photoelectric absorption.
- Flat $\Lambda$CDM cosmological distance dimming.

### 2.5 PSI Agent (Autonomous AI Intelligence)
Driven by the Model Context Protocol (MCP) and SentryAgent:
- **`specsynth-mcp`**: Exposes SPS capabilities, filter projection matrices, SED inspection, and dataset queries via standard JSON-RPC.
- **SentryAgent**: Autonomous 4-tier diagnostic verification agent that detects anomalies (numerical non-finites, unphysical spectral indices like $D_n4000 < 0.5$, population collapses), isolates root causes, and purges corruptions.

### 2.6 PSI Notebook (Interactive Workflows)
- Seamless bridge between the visual GUI and Python code.
- One-click export: click a galaxy in PSI Explorer and copy the exact Python/Dask code snippet required to reproduce its SED and photometry in a local Jupyter environment.

### 2.7 PSI Publish (Publication Artifacts)
- Direct export of publication-ready vector figures (PDF/SVG) matching ApJ/MNRAS style guides.
- Automatic generation of reproduction manifests with SHA-256 filter checksums, adapter version metadata, and system hardware profiling.

---

## 3. Communication & Connectivity Protocol

```mermaid
flowchart LR
    subgraph Browser ["PerandamΨ Frontend (Browser)"]
        SPACE["PSI Space<br/>(WebGL Canvas)"]
        EXP["PSI Explorer<br/>(SED & Sliders)"]
    end

    subgraph Bridge ["Local HTTP Bridge (:8000)"]
        API["FastAPI / HTTP Server<br/>• /api/health<br/>• /api/inspect<br/>• /api/filters<br/>• /api/tng-catalog"]
    end

    subgraph Backend ["PSI Compute & Agent (Python)"]
        MCP["specsynth-mcp<br/>(JSON-RPC stdio)"]
        CORE["specsynth.core<br/>• GEMM Contraction<br/>• Dust & IGM"]
        SENTRY["specsynth.sentry<br/>• 4-Tier Invariants"]
    end

    subgraph Agents ["External AI Agents"]
        CLAUDE["Claude / Cursor / Antigravity"]
    end

    SPACE <--> EXP
    EXP -- REST / JSON --> API
    API --> CORE
    API --> SENTRY
    CLAUDE <--> MCP
    MCP --> CORE
    MCP --> SENTRY
```

1. **Offline Mode (Zero-Install)**: `perandam-psi` packages curated JSON/binary datasets (starting with the validated TNG → JWST NIRCam sample) directly inside the web client.
2. **Live Engine Mode**: When `python -m specsynth.mcp.bridge --port 8000` is active, the web client seamlessly unlocks live on-the-fly synthesis, custom Zarr imports, and real-time Sentry audits.
3. **Agent Mode**: AI coding agents connect directly to `specsynth.mcp.server` via stdio, orchestrating simulations via conversational queries.
