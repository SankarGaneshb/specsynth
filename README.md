# specsynth: distributed, out-of-core stellar population synthesis

For each galaxy, the model spectrum is a mass-weighted sum of simple stellar populations (SSPs)
with a two-component dust screen:

    F_g(λ) = D_g(λ) · [ Σ_old SFH[g,k]·SSP[k,λ]  +  B_g(λ) · Σ_young SFH[g,k]·SSP[k,λ] ]

Per chunk of galaxies this is two `(n×K)@(K×W)` matrix products plus an `exp()`.
The problem is embarrassingly parallel over galaxies, so it scales out linearly.

## Design

| Concern | Choice |
|---|---|
| Out-of-core | Galaxies are Zarr chunks `(chunk × K)`. Workers stream chunk → compute → write chunk. Nothing bigger than a chunk is held. |
| Multi-node | Dask. `--scheduler tcp://…` for any cluster, or a LocalCluster with no flag. |
| Cloud-native / agnostic | All I/O via fsspec URLs: `file://`, `s3://`, `gs://`, `abfs://`. No shared filesystem. One container image for client, scheduler and workers. |
| SSP library | Read once from storage, then replicated peer-to-peer between workers (`--no-persist-ssp` re-reads per task if the library exceeds cluster RAM; `--wave-chunk` splits the wavelength axis). |
| Reproducibility | Catalogue RNG is seeded per chunk index, so results do not depend on cluster layout. |
| Output | Full spectra, or `--bands N` photometry only. The spectra are streamed through and never stored, which is usually what you want at 10⁸+ galaxies. |

## Quickstart (laptop)

    pip install -r requirements.txt
    S="python specsynth.py --base /tmp/run1 --workers 2 --memory-limit 1GB"
    $S make-ssp --n-age 60 --n-met 6 --n-wave 4000
    $S make-sfh --n-gal 1000000 --chunk 20000
    $S synth --filters jwst_nircam --redshift 1.5   # project onto JWST NIRCam at z=1.5
    $S verify                                      # float64 numpy reference on a random sample

## Cosmological Redshift & Realistic Filter Sets

`specsynth` computes Flat $\Lambda\text{CDM}$ cosmological redshift wavelength shifting ($\lambda_{\text{obs}} = \lambda_{\text{rest}}(1+z)$) and projects spectra onto realistic photon-counting filter transmission curves:

```bash
# JWST NIRCam (F090W, F115W, F150W, F200W, F277W, F356W, F444W) at z=2.0
python specsynth.py --base /tmp/run1 synth --filters jwst_nircam --redshift 2.0

# HST ACS & WFC3 (F435W, F606W, F814W, F160W)
python specsynth.py --base /tmp/run1 synth --filters hst --redshift 0.8

# Rubin / LSST (u, g, r, i, z, y) or SDSS
python specsynth.py --base /tmp/run1 synth --filters rubin --redshift 0.3

# Custom combination
python specsynth.py --base /tmp/run1 synth --filters jwst_f200w,jwst_f444w,hst_f160w
```

## GPU Acceleration (CuPy / cuBLAS)

Speed up the matrix contractions (`(N x K) @ (K x W)`) on NVIDIA GPUs using CuPy and tensor cores:

```bash
python specsynth.py --base /tmp/run1 synth --filters jwst_nircam --gpu
```
*(If no NVIDIA GPU is available, `--gpu` automatically and silently falls back to optimized CPU BLAS).*

## Testing

Run unit tests locally with pytest:

```bash
pytest -v
```

CI runs automatically via GitHub Actions across Python 3.10–3.13.

## Cluster

    docker build -t YOUR_REGISTRY/specsynth . && docker push YOUR_REGISTRY/specsynth
    kubectl apply -f k8s/dask-cluster.yaml     # needs the Dask Kubernetes Operator
    kubectl apply -f k8s/synth-job.yaml        # edit BASE bucket first

Any other Dask deployment works the same way: pass its scheduler address with `--scheduler`.
Use matching Dask/Zarr versions on client and workers.

## Using Real SSP Libraries (`make-ssp --adapter`)

`specsynth` includes built-in adapters (`specsynth.adapters`) to import and normalize standard astrophysical libraries into `ssp.zarr`:

### 1. Bruzual & Charlot 2003 (BC03)
Reads binary `.ised` (Fortran unformatted) or exported ASCII tables directly:
```bash
# Ingest directory containing multiple metallicity files (e.g. m22..m72)
python specsynth.py --base s3://bucket/run1 make-ssp --adapter bc03 --input-path /data/bc03/Padova1994/chabrier/

# Or a single .ised file
python specsynth.py --base s3://bucket/run1 make-ssp --adapter bc03 --input-path /data/bc03/bc2003_lr_m62_chab_ssp.ised
```

### 2. E-MILES & MILES (Vazdekis et al.)
Parses raw directories of individual FITS files (`Ebi1.30Z...T..._baseFe.fits`), reads standard FITS WCS header cards (`CRVAL1`, `CDELT1`), converts $[M/H]$ and $T$ (Gyr) automatically into age-major grids:
```bash
python specsynth.py --base s3://bucket/run1 make-ssp --adapter emiles --input-path /data/emiles/Padova1994/
```
*(No `astropy` installation required—includes a built-in pure Python FITS reader!)*

### 3. FSPS (Flexible Stellar Population Synthesis)
Generates grids dynamically via `python-fsps`, or directly parses raw Fortran FSPS output files:
```bash
# Dynamic generation via python-fsps
python specsynth.py --base s3://bucket/run1 make-ssp --adapter fsps --imf chabrier --isochrone mist

# Or parse raw Fortran FSPS output text files directly
python specsynth.py --base s3://bucket/run1 make-ssp --adapter fsps --input-file /data/fsps/OUTPUTS/spstot_chab.spec
```

### 4. Generic Astronomical Grids (FITS / HDF5 / NPZ)
Ingests multi-dimensional spectral grids from FITS HDUs, HDF5, or NumPy `.npz` datasets (e.g. C3K, POPSTAR):
```bash
python specsynth.py --base s3://bucket/run1 make-ssp --adapter fits --input-file /data/models/custom_grid.fits
```

### 5. Optional Wavelength Re-gridding
Any adapter can resample the wavelength grid uniformly:
```bash
python specsynth.py --base /tmp/run1 make-ssp --adapter bc03 --input-path ./bc03/ --resample-wave 1000 10000 5000
```

## What was tested (sandbox, 1 CPU, 3 GB RAM, local Zarr)

- 50k, 200k and 500k galaxies end to end; `verify` against an independent float64 reference
  gives max relative error ≈ 1e-6 (float32 round-off) in both spectra and photometry modes.
- 500k galaxies → ~1.8 GB of spectra through two workers limited to ~286 MiB each: completes,
  with Dask's pause/resume backpressure engaging.
- **Not tested:** the Docker image build, the Kubernetes manifests, and object-store backends
  (S3/GCS/Azure). They use standard patterns, but treat them as a starting point. Throughput
  numbers from the sandbox are not benchmarks.

## Known simplifications

No redshift/IGM, nebular emission, kinematic broadening, AGN, or mass-loss/remnant accounting;
dust is a simple power-law two-component screen (`--diffuse-index`, `--birth-index`).
Metallicity is a fixed grid with no interpolation. Full-spectrum storage is expensive:
10⁸ galaxies × 8000 λ × 4 B ≈ 3.2 TB. Prefer `--bands`.
