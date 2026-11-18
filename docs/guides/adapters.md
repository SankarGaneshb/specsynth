# SSP Model Adapters

`specsynth` compiles Simple Stellar Population (SSP) spectral libraries into an immutable, Zarr-backed `(K, W)` basis matrix where $K = N_{\text{age}} \times N_Z$ and $W = N_\lambda$. This offline compilation step allows identical streaming execution across any stellar evolution library.

## Built-In Adapters

### 1. Bruzual & Charlot (2003) — `bc03`

Ingests standard GALAXEV/BC03 Fortran unformatted sequential binary `.ised` files or whitespace-delimited ASCII tables. Automatically infers metallicities from standard filename codes (`m22` = 0.0001 through `m72` = 0.05).

```bash
# Single .ised file
specsynth --base ./run make-ssp --adapter bc03 \
    --input-path /data/bc03/bc2003_hr_stelib_chab_ssp.ised

# Directory containing multiple metallicity files (m22..m72)
specsynth --base ./run make-ssp --adapter bc03 \
    --input-path /data/bc03_chabrier/
```

### 2. E-MILES / MILES — `emiles`

Parses Vazdekis et al. FITS spectral files from a directory or single FITS file, automatically handling filename-encoded metallicities (`[M/H]`) and ages (`T`), with wavelength resampling to a common grid and a built-in pure-Python FITS fallback when `astropy` is unavailable.

```bash
specsynth --base ./run make-ssp --adapter emiles \
    --input-path /data/emiles_fits/
```

### 3. Flexible Stellar Population Synthesis — `fsps`

Supports both dynamic grid generation via `python-fsps` and direct ingestion of exported Fortran ASCII output tables (`spstot_*.spec`).

```bash
# Dynamic generation via python-fsps
specsynth --base ./run make-ssp --adapter fsps \
    --imf chabrier --isochrone mist

# Or ingest pre-exported ASCII tables without requiring python-fsps
specsynth --base ./run make-ssp --adapter fsps \
    --input-file /data/fsps/spstot_chabrier.spec
```

### 4. Generic Multi-Dimensional Grids — `fits` / `hdf5` / `npz`

Loads arbitrary 3D `(n_age, n_met, n_wave)` grids from FITS, HDF5, or NumPy `.npz` archives with automatic age-unit detection (linear years, $\log_{10}(\text{yr})$, or Gyr):

```bash
specsynth --base ./run make-ssp --adapter fits \
    --input-file /data/custom_bpass_grid.h5 \
    --wave-key wave --age-key ages --met-key metallicities --flux-key spectra
```

### 5. Analytical Reference Basis — `toy`

Generates a deterministic, smooth Planck blackbody + age/metallicity scaling basis useful for CI tests, scaling benchmarks, and offline exploration without external model downloads:

```bash
specsynth --base ./run make-ssp --adapter toy --n-age 40 --n-met 4 --n-wave 2000
```

---

## Wavelength Resampling

Any adapter output can be resampled to a uniform target wavelength grid during compilation:

```bash
specsynth --base ./run make-ssp --adapter bc03 \
    --input-path /data/bc03/ \
    --resample-wave 900 55000 3000
```

---

## Writing a Custom Adapter

Subclass `specsynth.adapters.base.BaseAdapter` and return an `SSPData` object via `SSPData.from_3d_grid`:

```python
import numpy as np
from specsynth.adapters.base import BaseAdapter, SSPData

class MyCustomSSPAdapter(BaseAdapter):
    def __init__(self, path: str):
        self.path = path

    def load(self) -> SSPData:
        # Load your 1D axes and 3D luminosity grid: (n_age, n_met, n_wave)
        ages = np.logspace(6.0, 10.1, 30)   # years
        mets = np.array([0.004, 0.008, 0.02])  # mass fraction Z
        wave = np.linspace(1000.0, 50000.0, 2000)  # Angstroms
        grid_3d = np.ones((len(ages), len(mets), len(wave)), dtype=np.float32)

        return SSPData.from_3d_grid(
            ages=ages,
            mets=mets,
            wave=wave,
            grid_3d=grid_3d,
            metadata={"model": "CustomSSP", "source": self.path},
        )
```
