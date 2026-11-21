# FSPS Model Configuration & Stellar Evolution Parameters

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. FSPS Adapter Overview

`specsynth` interfaces with the **Flexible Stellar Population Synthesis (FSPS)** codebase (Conroy et al. 2009, 2010) through `specsynth.adapters.FSPSAdapter`.
It supports:
1. **Dynamic Programmatic Execution**: Invoking `python-fsps` directly when Fortran compilation and `$SPS_HOME` are present.
2. **Version-Locked Offline Reference Grids**: Ingesting ASCII spectrum outputs (`sample_models/fsps/fsps_full_chabrier_mist.spec`) for zero-dependency portability and bitwise reproducible benchmarks.

---

## 2. Configuration Parameters

| Parameter | Selected Value | Scientific Rationale |
|:---|:---|:---|
| **IMF** | Chabrier (2003) (`imf_type=1`) | Matches IllustrisTNG simulation sub-grid stellar physics and observational consensus. |
| **Isochrone System** | MIST (Dotter 2016, Choi et al. 2016) | Modern stellar evolution tracks based on MESA, covering full post-main-sequence phases. |
| **Spectral Library** | MILES ($3525\text{--}7500\,\text{\AA}$) + BaSeL | High-resolution optical empirical library blended with theoretical UV/IR atmospheres. |
| **Wavelength Coverage** | $91.2\,\text{\AA} \text{ to } 100{,}000\,\text{\AA}$ ($10\,\mu\mathrm{m}$) | Fully covers all JWST NIRCam bands (F090W - F444W) from $z=0$ through $z \approx 4$. |
| **Nebular Emission** | Disabled (`add_nebular_emission=False`) | Isolate pure stellar continuum + dust attenuation contracts in v1 before introducing photoionization model uncertainties. |
| **Solar Metallicity Standard** | $Z_\odot = 0.019$ | Standard FSPS photospheric solar metallicity definition. |

---

## 3. Metallicity Transformation

IllustrisTNG tracks individual element mass fractions and total stellar metallicity $Z$.
In `specsynth`, simulation metallicities are converted to the logarithmic solar ratio required by FSPS:
$$\log_{10}(Z / Z_\odot) = \log_{10}\left(\frac{\max(Z, 10^{-5})}{0.019}\right)$$

Singularities arising from zero-metallicity particles in primitive subhalos are bounded with a physical lower floor ($Z \ge 10^{-5}$, corresponding to $[Z/Z_\odot] \ge -3.28$).
