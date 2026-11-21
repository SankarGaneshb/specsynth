# IllustrisTNG 100-Galaxy Demonstration Sample

**Release:** `v1.0-tng-jwst`  
**Simulation Origin:** IllustrisTNG (TNG100-1 / Planck 2015 Cosmology)  
**Sample Count:** 100 Galaxies  
**SHA-256 Checksum:** `5a63fac422b882a77b3d0f5ce83948b7aca31349fcc32d04c541d88a12ec67cd`  

---

## Overview
This quality-controlled dataset provides a diverse distribution of simulated galaxies designed for immediate evaluation in the **10-minute researcher notebook** (`notebooks/tng-jwst/01_tng_jwst_synthetic_photometry.ipynb`).

### Parameter Space Covered:
- **Redshift Range:** $z \in [0.22, 3.88]$
- **Stellar Mass Range:** $\log_{10}(M_* / M_\odot) \in [9.06, 11.46]$
- **Star Formation Rate:** $\mathrm{SFR} \in [5.51e-05, 82.71]\,M_\odot/\mathrm{yr}$
- **Dust Attenuation:** $A_V \in [0.02, 2.5]\,\mathrm{mag}$
- **Metallicity:** $\log_{10}(Z/Z_\odot) \in [-1.5, +0.3]$

### Column Definitions:
| Column | Units | Description |
|:---|:---|:---|
| `galaxy_id` | string | Unique simulation subhalo identifier (`tng100_subhalo_XXXXXX`) |
| `stellar_mass` | $M_\odot$ | Total formed stellar mass |
| `log_mstar` | $\log_{10}(M_\odot)$ | Logarithmic stellar mass |
| `redshift` | dimensionless | Cosmological observation redshift $z$ |
| `t_onset` | Gyr | Time since initial star formation onset |
| `tau` | Gyr | Characteristic star formation timescale |
| `sfr` | $M_\odot/\mathrm{yr}$ | Instantaneous star formation rate |
| `metallicity` | dimensionless | Stellar metallicity $\log_{10}(Z/Z_\odot)$ |
| `tau_diffuse` | dimensionless | Diffuse ISM optical depth $\tau_d = A_V / 1.086$ |
| `tau_birth` | dimensionless | Birth-cloud optical depth $\tau_b = 1.5 \tau_d$ |
| `av` | magnitudes | V-band extinction $A_V$ |
