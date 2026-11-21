# Scientific Charter: IllustrisTNG to JWST NIRCam Validation

**Milestone:** `TNG–JWST Scientific Validation v1.0`  
**Target:** Extragalactic Astronomers, Survey Cosmologists, and Simulation Teams  

---

## 1. Experiment Charter & Scientific Objective

The core objective of this experiment is to demonstrate that `specsynth` forward-models **JWST Near-Infrared Camera (NIRCam)** synthetic photometry from **IllustrisTNG** cosmological hydrodynamical galaxies with verifiable scientific fidelity and numerical rigor.

Synthetic photometry pipelines in astrophysics frequently suffer from "black-box" implementations where stellar population models, dust attenuation curves, filter integration weights, and distance dimming conventions are intermingled or undocumented. This experiment establishes an explicit, independently audited scientific contract.

```
                      [IllustrisTNG Galaxy Properties]
                       * Stellar Mass M* [M_sun]
                       * Star Formation History (SFH)
                       * Stellar Metallicity Z
                       * Cosmological Redshift z
                                    │
                                    ▼
                      [FSPS Simple Stellar Populations]
                       * Chabrier (2003) IMF
                       * MIST Isochrones
                       * MILES + BaSeL Spectral Grid
                       * Continuum Scope (Nebular off in v1)
                                    │
                                    ▼
                      [specsynth In-Flight Contraction]
                       * Charlot & Fall (2000) Dust Attenuation
                       * Madau (1995) IGM Absorption
                       * FlatLambdaCDM Luminosity Distance Dimming
                                    │
                                    ▼
                      [Calibrated JWST NIRCam Photometry]
                       * F090W, F150W, F200W, F277W, F356W, F444W
                       * Photon-Weighted AB Synthetic Flux Densities
                       * Tabular Scientific Catalog Export
```

---

## 2. Target Instrument & Filter Selection

We target the primary wide-band filters of JWST NIRCam, spanning both the Short-Wavelength (SW) and Long-Wavelength (LW) channels:
- **Short-Wavelength Channel (0.6 - 2.3 um):**
  - `F090W`: $\lambda_{\mathrm{piv}} = 0.899\,\mu\mathrm{m}$, $\mathrm{FWHM} = 0.20\,\mu\mathrm{m}$
  - `F150W`: $\lambda_{\mathrm{piv}} = 1.498\,\mu\mathrm{m}$, $\mathrm{FWHM} = 0.30\,\mu\mathrm{m}$
  - `F200W`: $\lambda_{\mathrm{piv}} = 1.983\,\mu\mathrm{m}$, $\mathrm{FWHM} = 0.46\,\mu\mathrm{m}$
- **Long-Wavelength Channel (2.4 - 5.0 um):**
  - `F277W`: $\lambda_{\mathrm{piv}} = 2.755\,\mu\mathrm{m}$, $\mathrm{FWHM} = 0.68\,\mu\mathrm{m}$
  - `F356W`: $\lambda_{\mathrm{piv}} = 3.560\,\mu\mathrm{m}$, $\mathrm{FWHM} = 0.78\,\mu\mathrm{m}$
  - `F444W`: $\lambda_{\mathrm{piv}} = 4.397\,\mu\mathrm{m}$, $\mathrm{FWHM} = 1.02\,\mu\mathrm{m}$

These filters bracket the rest-frame optical/NIR spectral energy distributions of galaxies at redshifts $z \sim 0.5\text{--}3.5$, capturing key features such as the $4000\,\text{\AA}$ break, the Balmer jump, and the $1.6\,\mu\mathrm{m}$ $H^-$ opacity bump.

---

## 3. Scientific Success Gates

1. **Spectral Fidelity**: Direct reproduction of FSPS composite spectra to $< 10^{-4}$ relative flux residual.
2. **Photometric Calibration**: Evaluation of standard $3631\,\mathrm{Jy}$ flat spectrum yields $m_{\mathrm{AB}} = 0.000 \pm 0.005\,\mathrm{mag}$ across all six bands.
3. **Cosmological Accuracy**: Luminosity distance scaling matches high-precision numerical FLRW integration to $< 10^{-5}$ relative tolerance.
4. **Usability**: Complete 100-galaxy experiment executes on a standard laptop CPU in $< 10$ minutes without external dependencies.
