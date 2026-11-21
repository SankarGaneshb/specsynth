# CLI Reference

`specsynth` installs a console entry point (`specsynth`, also runnable via `python specsynth.py`).

## Global Flags

```bash
specsynth [--base PATH_OR_URL] [--scheduler sync|threads|local|tcp://HOST:PORT] \
          [--workers N] [--memory-limit 2GB] <subcommand> [options]
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--base` | `./specsynth_run` | Root directory or `fsspec` URL (`s3://`, `gs://`, `abfs://`) for Zarr stores |
| `--scheduler` | `local` | Execution scheduler (`sync`, `threads`, `local`, or remote `tcp://...`) |
| `--workers` | Auto | Number of local Dask worker processes |
| `--memory-limit` | Auto | Per-worker memory limit (e.g., `2GB`, `512MB`) |

---

## Subcommands

### `make-ssp`
Compile an SSP spectral library into `<base>/ssp.zarr`.

```bash
specsynth --base ./run make-ssp --adapter {toy|bc03|emiles|fsps|bpass|fits} \
    [--input-path DIR_OR_FILE] [--input-file FILE] \
    [--n-age 40] [--n-met 4] [--n-wave 2000] \
    [--resample-wave MIN MAX N]
```

### `make-sfh`
Generate a reproducible synthetic SFH parameter catalog in `<base>/galaxies.zarr`.

```bash
specsynth --base ./run make-sfh --n-gal 50000 --chunk 10000 [--seed 42]
```

### `import-catalog`
Ingest an external galaxy catalog (Parquet, FITS, HDF5, CSV, NPZ) into `<base>/galaxies.zarr`.

```bash
specsynth --base ./run import-catalog -i catalog.parquet [--chunk 20000] [--streaming] [--drop-invalid] \
    [--mass-col COL] [--age-col COL] [--met-col COL] [--tau-d-col COL] [--redshift-col COL]
```

### `synth`
Synthesize full spectra (`spectra.zarr`) or in-flight broadband photometry (`photometry.zarr`).

```bash
specsynth --base ./run synth [--filters jwst_nircam|hst|sdss|CUSTOM] [--bands N] \
    [--redshift Z] [--lightcone] [--igm] [--distance-dimming] \
    [--cosmology concordance|planck2018|planck2015|wmap9] [--h0 H0] [--omega-m OM] \
    [--chunk N] [--batch-chunks B] [--gpu]
```

### `verify`
Cross-check distributed `float32` outputs against an independent `float64` reference calculation.

```bash
specsynth --base ./run verify [--sample 200]
```

### `benchmark`
Run standardized CPU/GPU throughput and memory-boundedness benchmarks and emit a provenance JSON manifest.

```bash
specsynth benchmark --n-gal 50000 --n-runs 5 [--gpu] [--output manifest.json]
```

### `sentry` / `sentry-agent` / `clean-catalog`
Run 4-tier quality audits, cluster anomalies, and export validated catalogs.

```bash
specsynth --base ./run sentry --sample 50000 --output sentry_report.json
specsynth --base ./run clean-catalog --output clean_catalog.parquet
```
