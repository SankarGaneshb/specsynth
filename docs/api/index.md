# Python API Reference

All public modules in `specsynth` expose typed Python functions and classes documented with NumPy-style docstrings.

| Module | Purpose |
| :--- | :--- |
| [`specsynth.core`](core.md) | Chunked GEMM synthesis (`synth_block`), SFH construction, dust attenuation curves, adaptive chunking, and batched Zarr I/O |
| [`specsynth.gpu`](core.md#gpu-acceleration) | CuPy CUDA detection and GPU synthesis kernels |
| [`specsynth.adapters`](adapters.md) | `BaseAdapter`, `SSPData`, `BC03Adapter`, `EMILESAdapter`, `FSPSAdapter`, `FITSGridAdapter`, `ToyAdapter` |
| [`specsynth.cosmology`](physics.md#cosmology) | `FlatLambdaCDM` distances, observer-frame flux dimming, snapshot & lightcone chunk transforms |
| [`specsynth.filters`](physics.md#photometric-filters) | `FilterCurve`, calibrated JWST/HST/SDSS loader, projection matrices, and AB magnitude conversions |
| [`specsynth.igm`](physics.md#igm-attenuation) | Madau (1995) Lyman-series and Lyman-continuum IGM transmission |
| [`specsynth.catalog`](catalog-and-benchmark.md#catalog-ingestion) | Multi-format simulation catalog ingestion (`import_catalog`, `clean_catalog`) |
| [`specsynth.benchmark`](catalog-and-benchmark.md#benchmarking) | Automated throughput, memory, and hardware provenance benchmarking |
| [`specsynth.sentry`](sentry.md) | Four-tier numerical and astrophysical quality assurance checks |
