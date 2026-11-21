# User Guide: Interpreting Results, Units, and Quality Flags

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Exported Catalog Schema (Task C09)

When exporting with `--export-catalog` or `specsynth export-catalog`, the resulting catalog contains:

| Column Name | Units | Description |
|:---|:---|:---|
| `galaxy_id` | string | Unique simulation subhalo identifier |
| `redshift` | dimensionless | Applied cosmological observation redshift $z$ |
| `stellar_mass` | $M_\odot$ | Total stellar mass |
| `log_mstar` | $\log_{10}(M_\odot)$ | Base-10 logarithm of formed stellar mass |
| `metallicity` | mass fraction $Z$ | Total stellar metallicity |
| `log_z_solar` | dimensionless | Logarithmic solar metallicity ratio $[Z/Z_\odot]$ relative to $Z_\odot = 0.019$ |
| `sfr` | $M_\odot/\mathrm{yr}$ | Instantaneous star formation rate |
| `F090W` | AB mag | Synthetic apparent magnitude in NIRCam F090W |
| `F090W_flux_uJy` | $\mu\mathrm{Jy}$ | Mean spectral flux density $F_\nu$ in microJanskys |
| `F150W` | AB mag | Synthetic apparent magnitude in NIRCam F150W |
| `F150W_flux_uJy` | $\mu\mathrm{Jy}$ | Mean spectral flux density $F_\nu$ in microJanskys |
| `F200W` | AB mag | Synthetic apparent magnitude in NIRCam F200W |
| `F200W_flux_uJy` | $\mu\mathrm{Jy}$ | Mean spectral flux density $F_\nu$ in microJanskys |
| `F277W` | AB mag | Synthetic apparent magnitude in NIRCam F277W |
| `F277W_flux_uJy` | $\mu\mathrm{Jy}$ | Mean spectral flux density $F_\nu$ in microJanskys |
| `F356W` | AB mag | Synthetic apparent magnitude in NIRCam F356W |
| `F356W_flux_uJy` | $\mu\mathrm{Jy}$ | Mean spectral flux density $F_\nu$ in microJanskys |
| `F444W` | AB mag | Synthetic apparent magnitude in NIRCam F444W |
| `F444W_flux_uJy` | $\mu\mathrm{Jy}$ | Mean spectral flux density $F_\nu$ in microJanskys |
| `quality_flag` | integer | Sentry quality status: `0 = Pristine`, `1 = Warning`, `2 = Anomalous` |
| `model_id` | string | Stellar population model provenance string (e.g. `FSPS_Chabrier_MIST`) |

---

## 2. Quality Flags (Sentry Integration)

- **`quality_flag = 0` (Pristine)**: Passed all physical and numerical tests. Safe for cosmology and mock survey creation.
- **`quality_flag = 1` (Warning)**: Extreme parameter combination (e.g. $A_V > 4\,\mathrm{mag}$ or $z > 8.0$), resulting in faint magnitudes near telescope detection limits ($m_{\mathrm{AB}} > 32$).
- **`quality_flag = 2` (Anomalous)**: Quarantined due to non-physical input or numerical failure (e.g. negative flux, non-finite values). Exclude from downstream observational comparisons.
