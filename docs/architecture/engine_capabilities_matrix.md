# Engine Capabilities Matrix

This document provides a comprehensive comparative matrix of Simple Stellar Population (SSP) synthesis engines, simulation data adapters, and external engine extensibility supported in **Specsynth**.

---

## 📊 Comprehensive Engine Comparison

| Feature / Property | FSPS (v3.2) | Bruzual & Charlot (BC03) | BPASS (v2.2.1) | E-MILES | FITS / NPZ Grid | Custom External Engine |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Adapter Class** | `FSPSAdapter` | `BC03Adapter` | `BPASSAdapter` | `EMILESAdapter` | `FITSGridAdapter` | Subclass of `BaseAdapter` |
| **Canonical Identifier** | `fsps` | `bc03` | `bpass` | `emiles` | `fits` | Dynamic identifier |
| **Primary Reference** | Conroy et al. (2009, 2010) | Bruzual & Charlot (2003) | Eldridge et al. (2017) | Vazdekis et al. (2016) | Standard FITS I/O | User Defined |
| **Wavelength Coverage** | $91\,\text{\AA} - 100\,\mu\text{m}$ | $91\,\text{\AA} - 160\,\mu\text{m}$ | $1\,\text{\AA} - 10\,\mu\text{m}$ | $1680\,\text{\AA} - 5\,\mu\text{m}$ | Flexible | Arbitrary (contract bounds: $10\,\text{\AA} - 100\,\mu\text{m}$) |
| **Spectral Resolution** | $R \sim 2000 - 5000$ | $R \sim 2000$ (optical) | $R \sim 1000 - 2000$ | $R \sim 2000 - 4000$ (FWHM $\sim 2.5\,\text{\AA}$) | Arbitrary | User Defined |
| **Stellar Isochrones** | MIST (default), Padova, BaSTI | Padova 1994, Padova 2000 | Custom BPASS tracks | BaSTI, Padova 2000 | Custom | External engine native |
| **IMF Models** | Chabrier, Salpeter, Kroupa, Custom | Chabrier, Salpeter, Kroupa | Kroupa, Salpeter | Chabrier, Salpeter, Kroupa, Bimodal | Pre-computed in grid | External engine native |
| **Binary Evolution** | Single stars | Single stars | Explicit interactive binaries | Single stars | External dependent | User Defined |
| **TP-AGB Treatment** | Calibrated (Marigo 2008) | Vassiliadis & Wood (1993) | Empirical loss models | Empirical stellar libraries | External dependent | User Defined |
| **Nebular Emission** | In-flight Cloudy photoionization | Not integrated | Optional Cloudy grids | Not integrated | Pre-computed | User Defined |
| **Dust Attenuation** | Charlot & Fall (2000), Calzetti | Post-processing required | Post-processing required | Post-processing required | Post-processing required | In-flight via Specsynth dust module |
| **Core Modification Required** | **None** (Built-in) | **None** (Built-in) | **None** (Built-in) | **None** (Built-in) | **None** (Built-in) | **ZERO (Pillar 1)** |

---

## 🌌 Simulation Snapshot & Catalog Support

Specsynth decouples the spectral synthesis engine from the particle simulation source. Any simulation format can be ingested into standard `SimulationGalaxyContract` containers:

| Simulation Suite | Adapter / Method | Native Coordinates | Particle Types Extracted | Morphology Extraction |
| :--- | :--- | :--- | :--- | :--- |
| **IllustrisTNG-100 / 50** | `import_catalog.py` / TNG API | Comoving $\text{ckpc}/h$ | Star particles (PartType4) | Kinematic $\kappa_{\rm rot}$, Sérsic fit, Bulge/Disk |
| **EAGLE** | HDF5 Reader | Comoving $\text{Mpc}$ | Star particles (PartType4) | Angular momentum tensor decomposition |
| **FIRE-2 / FIRE-3** | HDF5 GIZMO Reader | Physical $\text{kpc}$ | Star particles | Half-mass radii, velocity dispersion $\sigma_v$ |
| **Custom Analytical / Mock** | `ToyAdapter` / JSON Mocks | Physical $\text{kpc}$ | Analytical Hernquist + Exponential Disk | Deterministic exponential + de Vaucouleurs |

---

## 📐 Invariant Verification Matrix

All engines (whether built-in or externally authored) pass the exact same mathematical verification contracts:

```
+----------------------------------------------------------------------------------+
|                   16-Point Conformance Suite Requirements                         |
+------------------------------------+---------------------------------------------+
| Check Category                     | Mathematical / Scientific Invariant         |
+------------------------------------+---------------------------------------------+
| 1. Class Inheritance               | issubclass(adapter_cls, BaseAdapter) == True |
| 2. Instantiation Lifecycle         | adapter(**kwargs) completes without error   |
| 3. Required Methods                | Implements load(), validate(), caps()       |
| 4. Coordinate Monotonicity         | np.all(np.diff(ages) > 0)                   |
|                                    | np.all(np.diff(mets) > 0)                   |
|                                    | np.all(np.diff(wave) > 0)                   |
| 5. 2D Memory Layout                | shape == (N_age * N_met, N_wave)            |
| 6. Numerical Integrity             | np.all(np.isfinite(ssp_flux)) == True       |
| 7. Physical Non-Negativity         | np.all(ssp_flux >= -1e-6) == True           |
| 8. Non-Trivial Energy              | np.sum(ssp_flux) > 0                        |
| 9. Resampling Support              | resample_wavelength(target_grid) validated  |
+------------------------------------+---------------------------------------------+
```
