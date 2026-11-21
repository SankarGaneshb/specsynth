# Catalogs, Cosmology & Photometric Filters

## 1. Simulation Catalog Ingestion (`import-catalog`)

`specsynth` natively imports mock galaxy catalogs from **Parquet**, **FITS**, **HDF5**, **CSV**, and **NPZ** files and maps physical columns into chunked Zarr parameter arrays (`galaxies.zarr`).

- **Streaming Formats**: Parquet, HDF5, and CSV/TSV (`--streaming`) are read incrementally in blocks of `--chunk` galaxies without loading the entire dataset into memory.
- **In-Memory Formats**: FITS (via `astropy.table`) and NPZ catalogs are read into memory first and then converted to chunked Zarr storage.
- **Data Validation & Sanitization**: For CSV/TSV catalogs, row keys are automatically normalized (case-insensitive, whitespace-trimmed), non-finite or non-positive masses and invalid redshifts are validated, and optional `--drop-invalid` allows dropping malformed or unphysical rows instead of halting.

```bash
# Ingest a Parquet or FITS galaxy catalog
specsynth --base ./run import-catalog -i tng100_subhalos.parquet --chunk 20000

# Streaming ingestion for large CSV/tabular exports that exceed host RAM
specsynth --base ./run import-catalog -i large_catalog.csv --streaming --chunk 10000 --drop-invalid
```

### Custom Column Mapping

If your simulation catalog uses custom column names (such as IllustrisTNG `SubhaloMassType`, `SubhaloStarMetallicity`, or CAMELS exports), pass explicit column mappings:

```bash
specsynth --base ./run import-catalog -i eagle_catalog.hdf5 \
    --mass-col Mstar --age-col t_form --met-col Z_star \
    --tau-d-col Av_diffuse --redshift-col z_obs
```

Supported column alias options:
- `--dust-diffuse-col` (or `--tau-d-col`): Diffuse dust optical depth column. If values represent $V$-band extinction $A_V$ (e.g. column named `Av_diffuse` or `av`), `specsynth` automatically converts $A_V \to \tau_d = A_V / 1.086$.
- `--dust-birth-col` (or `--tau-b-col`): Extra birth-cloud dust optical depth.
- `--redshift-col` (or `--z-col`): Spectroscopic/snapshot redshift column.

See `scripts/cross_validate_sps.py` for an end-to-end example of mapping IllustrisTNG-like subhalo properties (stellar mass, SFR, metallicity, dust scaling, and redshift) into `specsynth`.

---

## 2. Cosmological Modes: Snapshot vs. Lightcone

`specsynth` supports two cosmological forward-modeling modes via `specsynth.cosmology.FlatLambdaCDM`:
- **Default Cosmology**: Concordance flat $\Lambda\mathrm{CDM}$ ($H_0 = 70.0\,\mathrm{km\,s^{-1}\,Mpc^{-1}}$, $\Omega_m = 0.3$).
- **Custom Cosmologies**: Pass `--cosmology planck2018`, `--cosmology planck2015`, `--cosmology wmap9`, or override explicitly with `--h0 <value>` and `--omega-m <value>`.

### Snapshot Mode (Uniform Redshift)
All galaxies sit at a single cosmological snapshot redshift $z$. Wavelengths shift via $\lambda_{\text{obs}} = \lambda_{\text{rest}}(1+z)$, optional luminosity-distance dimming $F_\lambda = L_{\lambda/(1+z)} / [4\pi D_L^2(1+z)]$ is applied when `--distance-dimming` is passed (requiring $z > 0$), and Madau (1995) IGM transmission is evaluated once on the observed grid:

```bash
# Physical observed flux density (erg/s/cm^2/A) with distance dimming and IGM attenuation
specsynth --base ./run synth --filters jwst_nircam --redshift 2.5 --igm --distance-dimming
```

### Lightcone Mode (Per-Galaxy Redshifts)
When `galaxies.zarr` contains a per-galaxy `redshift` array, enable `--lightcone` (supported as an alias for `--per-galaxy-z`) to evaluate per-galaxy wavelength shifts, optional luminosity-distance dimming (`--distance-dimming`), IGM attenuation, and bandpass integration inside each worker chunk:

```bash
specsynth --base ./run synth --filters jwst_nircam,hst --lightcone --igm --distance-dimming
```

---

## 3. Calibrated Photometric Filter Library

`specsynth` bundles 16 calibrated instrument throughput curves (under `specsynth/data/filters/`) with cryptographically verified SHA-256 checksums recorded in `filter_manifest.json`:

| Filter Preset (`--filters`) | Included Bands | Notes |
| :--- | :--- | :--- |
| `jwst_nircam` | `jwst_f090w`, `jwst_f115w`, `jwst_f150w`, `jwst_f200w`, `jwst_f277w`, `jwst_f356w`, `jwst_f444w` | Calibrated STScI NIRCam module-averaged throughputs |
| `hst` | `hst_f435w`, `hst_f606w`, `hst_f814w`, `hst_f160w` | Calibrated ACS (WFC) & WFC3/IR curves |
| `sdss` | `sdss_u`, `sdss_g`, `sdss_r`, `sdss_i`, `sdss_z` | Calibrated SDSS ugriz throughputs |
| Custom combinations | Comma-separated band names, e.g. `jwst_f150w,jwst_f200w,hst_f160w` | Mix across instruments freely |

### Loading Custom Filter Curves in Python

```python
import numpy as np
from specsynth.filters import FilterCurve, build_filter_projection_matrix

custom = FilterCurve(
    name="roman_f158",
    wave=np.linspace(13000.0, 18500.0, 200),
    transmission=np.ones(200),
    is_calibrated=True,
)
print(f"Pivot wavelength: {custom.pivot_wavelength:.1f} A")
```

---

## 4. Madau (1995) IGM Attenuation

Enable `--igm` (or call `specsynth.igm.madau_transmission(wave_obs, z)`) to integrate Lyman-series line blanketing ($\text{Ly}\alpha$ through higher transitions) and photoelectric Lyman-continuum absorption shortward of $911.75(1+z)\text{ \AA}$.
