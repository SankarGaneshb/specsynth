# User Guide: Preparing IllustrisTNG Catalogs for Specsynth

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Supported Input Formats
`specsynth` natively ingests:
- **Parquet** (`.parquet`, recommended for survey-scale speed and compression)
- **FITS binary tables** (`.fits`, `.fit`)
- **HDF5 datasets** (`.hdf5`, `.h5`)
- **Delimited ASCII** (`.csv`, `.tsv`)

---

## 2. Required Simulation Columns & Units

| Column Alias | Acceptable Source Names | Physical Units | Description |
|:---|:---|:---|:---|
| **Stellar Mass** | `log_mstar`, `m_star`, `SubhaloMassType`, `mstar` | $M_\odot$ or $\log_{10}(M_\odot)$ | Total stellar mass formed. Linear values $> 100$ are auto-converted to $\log_{10}$. |
| **Redshift** | `redshift`, `z`, `z_spec`, `z_obs` | dimensionless | Applied observation redshift $z$ for lightcone forward modeling. |
| **Onset Time** | `t_onset`, `onset`, `formation_time`, `t_form` | Gyr | Time since onset of initial star formation in the galaxy. |
| **SFH Timescale** | `tau`, `sfh_tau`, `decay_time` | Gyr | Characteristic exponential decay timescale in delayed-$\tau$ models. |
| **Metallicity** | `metallicity`, `log_z`, `SubhaloStarMetallicity`, `Z` | dimensionless | Stellar metallicity. Linear mass fractions $< 0.2$ are auto-converted to $\log_{10}(Z)$. |
| **Diffuse Dust** | `tau_diffuse`, `av`, `Av`, `tau_v` | dimensionless / mag | Diffuse optical depth $\tau_d$. If specified as $A_V$, auto-converted via $\tau_d = A_V / 1.086$. |
| **Birth-Cloud Dust**| `tau_birth`, `av_birth`, `tau_bc` | dimensionless / mag | Birth-cloud optical depth. Defaults to $1.5 \times \tau_d$ (Charlot & Fall 2000). |
| **Galaxy ID** | `galaxy_id`, `subhaloid`, `subfind_id`, `id` | string / int | Simulation identifier preserved in final scientific catalog. |

---

## 3. Explicit Column Mapping

If your simulation table uses custom column names, map them explicitly:
```bash
python specsynth.py --base my_run import-catalog \
  --input-file my_tng_catalog.hdf5 \
  --mass-col SubhaloMassType \
  --age-col SubhaloAge \
  --met-col SubhaloStarMetallicity \
  --redshift-col Redshift
```
