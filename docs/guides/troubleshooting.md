# User Guide: Troubleshooting Common Issues

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Zero Overlap Warning Between Wavelength Grid and Filter

### Symptom:
```
UserWarning: Filter 'jwst_f444w' has zero transmission overlap with the provided wavelength grid [1000.0, 10000.0] A.
Synthetic photometry will evaluate to zero flux for this band.
```

### Cause:
The underlying SSP library was compiled with a restricted rest-frame wavelength grid (e.g. optical-only $1{,}000\text{--}10{,}000\,\text{\AA}$). JWST NIRCam long-wavelength filters (F277W, F356W, F444W) operate at $2.4\text{--}5.0\,\mu\mathrm{m}$ ($24{,}000\text{--}50{,}000\,\text{\AA}$), requiring coverage out to $10\,\mu\mathrm{m}$.

### Remediation:
Compile `ssp.zarr` using the full-wavelength FSPS reference grid:
```bash
python specsynth.py --base run1 make-ssp --adapter fsps --input-file sample_models/fsps/fsps_full_chabrier_mist.spec
```

---

## 2. Missing Redshift Column

### Symptom:
```
ValueError: Cannot use --per-galaxy-z: 'redshift' component not found in galaxies.zarr.
```

### Remediation:
1. When importing your catalog, map the redshift column explicitly using `--redshift-col <name>`.
2. Or run in uniform snapshot mode: `--redshift <z_val>` (e.g. `--redshift 2.0`).

---

## 3. High Numerical Relative Error in `verify`

### Symptom:
`verify` reports a relative error around $6\%$ against the float64 reference.

### Cause:
Cosmology mismatch between synthesis and verification (e.g. synthesizing with `--cosmology tng` ($H_0 = 67.74$) but verifying with default Planck 2018 ($H_0 = 70.0$)).

### Remediation:
Pass matching cosmology parameters or let `verify` auto-read the stored cosmology metadata:
```bash
python specsynth.py --base run1 verify --cosmology tng
```
