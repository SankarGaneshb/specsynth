# User Guide: Generating JWST NIRCam Photometry

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Primary Filter Sets

`specsynth` includes several pre-defined filter aliases:
- `jwst_nircam_six` or `jwst_nircam6`: The six core wide bands (**F090W, F150W, F200W, F277W, F356W, F444W**).
- `jwst_nircam`: All seven wide bands (including `F115W`).
- Individual band names: e.g. `--filters jwst_f150w,jwst_f200w,jwst_f444w`.

---

## 2. Command Line Flags for Survey Photometry

```bash
python specsynth.py --base run1 synth \
  --filters jwst_nircam_six \
  --per-galaxy-z \
  --distance-dimming \
  --cosmology tng \
  --igm \
  --export-catalog run1/synthetic_photometry.parquet
```

### Flag Explanations:
- `--per-galaxy-z`: Evaluates lightcone forward-modeling using each galaxy's individual `redshift` column.
- `--distance-dimming`: Applies the physical $1 / [4\pi D_L^2(z)]$ inverse-square flux reduction in $\mathrm{cm}^2$.
- `--cosmology tng`: Adopts the Planck 2015 IllustrisTNG cosmology ($H_0 = 67.74$, $\Omega_m = 0.3089$).
- `--igm`: Applies Madau (1995) neutral hydrogen absorption redward and blueward of Ly$\alpha$.
- `--export-catalog <path>`: Exports the standard C09 tabular format (Parquet, CSV, FITS) with AB magnitudes, flux densities in $\mu\mathrm{Jy}$, and Sentry quality flags.
