# Catalogs, Cosmology & Photometric Filters

## 1. Simulation Catalog Ingestion (`import-catalog`)

`specsynth` natively imports mock galaxy catalogs from **Parquet**, **FITS**, **HDF5**, **CSV**, and **NPZ** files and maps physical columns into chunked Zarr parameter arrays (`galaxies.zarr`).

```bash
# Ingest a Parquet or FITS galaxy catalog
specsynth --base ./run import-catalog -i tng100_subhalos.parquet --chunk 20000

# Streaming ingestion for large CSV/tabular exports that exceed host RAM
specsynth --base ./run import-catalog -i large_catalog.csv --streaming --chunk 10000
```

### Custom Column Mapping

If your simulation catalog uses custom column names (such as IllustrisTNG `SubhaloMassType`, `SubhaloStarMetallicity`, or CAMELS exports), pass explicit column mappings:

```bash
specsynth --base ./run import-catalog -i eagle_catalog.hdf5 \
    --mass-col Mstar --age-col t_form --met-col Z_star \
    --tau-d-col Av_diffuse --redshift-col z_obs
```

See `scripts/cross_validate_sps.py` for an end-to-end example of mapping IllustrisTNG-like subhalo properties (stellar mass, SFR, metallicity, dust scaling, and redshift) into `specsynth`.

---

## 2. Cosmological Modes: Snapshot vs. Lightcone

`specsynth` supports two cosmological forward-modeling modes via `specsynth.cosmology.FlatLambdaCDM` (default $H_0 = 70.0\text{ km s}^{-1}\text{ Mpc}^{-1}$, $\Omega_m = 0.3$, or custom cosmologies such as Planck 2018 $H_0 = 67.4$, $\Omega_m = 0.315$):

### Snapshot Mode (Uniform Redshift)
All galaxies sit at a single cosmological snapshot redshift $z$. Wavelengths shift via $\lambda_{\text{obs}} = \lambda_{\text{rest}}(1+z)$, flux scales via luminosity distance $F_\lambda = L_{\lambda/(1+z)} / [4\pi D_L^2(1+z)]$, and Madau (1995) IGM transmission is evaluated once on the observed grid:

```bash
specsynth --base ./run synth --filters jwst_nircam --redshift 2.5 --igm
```

### Lightcone Mode (Per-Galaxy Redshifts)
When `galaxies.zarr` contains a per-galaxy `redshift` array, enable `--lightcone` to apply per-galaxy luminosity distance dimming, wavelength shifting, IGM attenuation, and bandpass integration inside each worker chunk:

```bash
specsynth --base ./run synth --filters jwst_nircam,hst --lightcone --igm
```

---

## 3. Calibrated Photometric Filter Library

`specsynth` bundles calibrated instrument throughput curves (CSV tables under `specsynth/data/filters/`) alongside analytical super-Gaussian approximations (`*_approx`) for rapid exploration:

| Filter Preset (`--filters`) | Included Bands | Notes |
| :--- | :--- | :--- |
| `jwst_nircam` | `jwst_f090w`, `jwst_f115w`, `jwst_f150w`, `jwst_f200w`, `jwst_f277w`, `jwst_f356w`, `jwst_f444w` | Calibrated STScI NIRCam throughputs |
| `hst` | `hst_f435w`, `hst_f606w`, `hst_f814w`, `hst_f160w` | Calibrated ACS & WFC3/IR curves |
| `sdss` | `sdss_u`, `sdss_g`, `sdss_r`, `sdss_i`, `sdss_z` | Calibrated SDSS ugriz curves |
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
