# User Guide: Configuring the FSPS Adapter

**Milestone:** `TNG–JWST Scientific Validation v1.0`  

---

## 1. Adapter Modes

`specsynth.adapters.FSPSAdapter` operates in two execution modes:

### Mode A: Version-Locked Offline Reference Grid (Default for v1)
Uses the pre-compiled wide-wavelength reference grid `sample_models/fsps/fsps_full_chabrier_mist.spec`.
- **Zero compiler dependencies**: Runs on Windows, macOS, Linux, and air-gapped HPC nodes without Fortran or python-fsps.
- **Bitwise reproducibility**: Guarantees identical outputs across cluster workers.

```bash
python specsynth.py --base run1 make-ssp \
  --adapter fsps \
  --input-file sample_models/fsps/fsps_full_chabrier_mist.spec
```

### Mode B: Dynamic Programmatic FSPS (`python-fsps`)
Generates custom grids on-the-fly using an installed `python-fsps` library:
```bash
python specsynth.py --base run1 make-ssp \
  --adapter fsps \
  --imf chabrier \
  --isochrone mist \
  --nebular
```

---

## 2. Supported Isochrones & IMFs

- **IMF Options**: `chabrier` (default, code 1), `salpeter` (code 0), `kroupa` (code 2).
- **Isochrones**: `mist` (default), `padova`.
- **Nebular Emission**: Controlled via `--nebular` (boolean). Default is disabled in v1 for baseline continuum validation.
