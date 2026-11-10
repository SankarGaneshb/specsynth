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
    $S synth                  # add --bands 8 for photometry only
    $S verify                 # float64 numpy reference on a random sample

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

## Using a real SSP library

`build_toy_ssp()` is a **toy** (blackbody + age-dependent break), included so the pipeline runs
standalone. For science, write an adapter that fills `ages` (yr, ascending), `mets` (Z),
`wave` (Å) and `ssp[k, λ]` with `k = i_age * n_met + i_met` (BC03, FSPS, E-MILES, …) and
writes them to `ssp.zarr` with the same component names. Nothing else changes.

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
