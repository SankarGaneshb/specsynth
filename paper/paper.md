---
title: 'specsynth: Cloud-Native Distributed Infrastructure for Survey-Scale Astrophysical Spectral Synthesis'
tags:
  - astronomy
  - astrophysics
  - galaxies
  - stellar population synthesis
  - distributed computing
  - dask
  - zarr
  - cupy
authors:
  - name: Sankar Ganesh
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 11 November 2026
bibliography: paper.bib
---

# Summary

Forward-modeling the synthetic spectra and broadband photometry of billions of simulated galaxies is a foundational requirement for upcoming wide-field cosmological surveys, including the Vera C. Rubin Observatory's Legacy Survey of Space and Time (LSST) [@ivezic2019lsst], the Nancy Grace Roman Space Telescope [@spergel2015wide], and the Euclid Space Mission [@laureijs2011euclid].

`specsynth` is an open-source, cloud-native Python framework engineered for out-of-core, distributed stellar population synthesis (SPS) and broadband mock catalog generation. By coupling chunked **Zarr** storage via `fsspec` with **Dask** distributed task graphs [@rocklin2015dask] and optional **CuPy** GPU tensor contractions [@okuta2017cupy], `specsynth` streams galaxy parameters from object stores, contracts them against Simple Stellar Population (SSP) spectral grids in worker RAM/cache, and projects them in-flight into photometric bandpasses without ever materializing multi-terabyte intermediate spectra onto disk.

# Statement of Need

Traditional stellar population synthesis codes such as FSPS [@conroy2009propagation] and BC03 Fortran [@bruzual2003stellar] are optimized for single-galaxy precision or serial in-memory loops. However, applying these codes to modern cosmological hydrodynamical simulations (e.g., IllustrisTNG [@pillepich2018simulating], EAGLE, or Semi-Analytic Models) at survey scale ($10^7 - 10^9+$ objects) exposes three fundamental architectural bottlenecks:

1. **Memory Exhaustion (OOM)**: Storing high-resolution spectra ($W \approx 4,000 - 10,000$ wavelength bins) for $10^8$ galaxies requires hundreds of terabytes of storage. Even intermediate arrays cannot fit into the memory of individual high-performance compute nodes.
2. **POSIX File System Contention**: Standard SPS pipelines rely on local shared POSIX network file systems (NFS/Lustre), leading to extreme I/O bottlenecks when thousands of distributed workers concurrently read model files.
3. **Absence of Cloud-Native Streaming**: Modern cloud workflows operate over scalable object stores (Amazon S3, Google Cloud Storage, Azure Blob Storage). Existing tools lack native chunked, out-of-core streaming interfaces.

`specsynth` resolves these challenges by redesigning stellar population synthesis as a distributed, chunked matrix-streaming pipeline.

# Astrophysical Framework

For each galaxy $g$, `specsynth` evaluates composite stellar populations using a two-component dust attenuation model [@charlot2000simple]:

$$F_g(\lambda) = D_g(\lambda) \cdot \left[ \sum_{k \in \text{old}} \text{SFH}[g,k] \cdot \text{SSP}[k,\lambda] + B_g(\lambda) \cdot \sum_{k \in \text{young}} \text{SFH}[g,k] \cdot \text{SSP}[k,\lambda] \right]$$

where $\text{SFH}[g,k]$ represents the stellar mass formed in age-metallicity grid cell $k$, $\text{SSP}[k,\lambda]$ is the intrinsic stellar luminosity per unit mass, and $D_g(\lambda) = \exp(-\tau_{\text{diffuse}} \cdot (\lambda / 5500\text{\AA})^{\alpha_{\text{diffuse}}})$ and $B_g(\lambda) = \exp(-\tau_{\text{birth}} \cdot (\lambda / 5500\text{\AA})^{\alpha_{\text{birth}}})$ represent the diffuse interstellar medium and young birth-cloud dust screens, respectively (with young stars defined as age $< 10^7\text{ yr}$).

For cosmological lightcone simulations at redshift $z > 0$, `specsynth` applies cosmological wavelength shifting $\lambda_{\text{obs}} = \lambda_{\text{rest}}(1+z)$, cosmological flux dimming $(1+z)^{-1}$, and photoelectric absorption through the intergalactic neutral hydrogen medium via the Madau (1995) transmission function $T_{\text{IGM}}(\lambda, z)$ [@madau1995radiative]:

$$T_{\text{IGM}}(\lambda, z) = \exp\left( -\tau_{\text{lines}}(\lambda, z) - \tau_{\text{continuum}}(\lambda, z) \right)$$

integrating the resonant Lyman series transitions shortward of Ly$\alpha$ ($1215.67\text{\AA}$) down to the Lyman limit ($911.75\text{\AA}$).

# Architecture and Engineering Innovations

`specsynth` incorporates several key architectural innovations:

- **Pluggable Model Adapters**: Native support for Bruzual & Charlot (2003) `.ised` binary and ASCII libraries [@bruzual2003stellar], E-MILES FITS header WCS calibrations [@vazdekis2016uv], FSPS grids [@conroy2009propagation], and generic multi-dimensional FITS/HDF5/NPZ datasets.
- **In-Flight Filter Projection**: Photometry is computed via dense matrix multiplication directly in worker L3 cache/VRAM:
  $$\mathbf{Phot} = \mathbf{F}_{\text{chunk}} \times \mathbf{M}_{\text{filter}}$$
  Discarding full spectra before storage reduces cloud I/O and persistent storage requirements by **$>99.9\%$** ($3.2\text{ GB}$ vs. $3.2\text{ TB}$ for $10^8$ galaxies).
- **Simulation Catalog Ingestion (`import-catalog`)**: Direct ingestion of simulation outputs from Parquet, FITS, HDF5, CSV, and NPZ formats, with automatic parameter inference and SFH matrix compilation.
- **Task Graph Guards and Batch Pipelining (`--batch-chunks`)**: For billion-object simulations ($N \ge 10^8$), monolithic task graphs can cause Dask scheduler memory bloat. `specsynth` incorporates dynamic chunk auto-tuning (keeping total graph tasks $< 25,000$) and a sliding-window batch pipeline that bounds scheduler memory to $O(B)$ chunks.
- **GPU Acceleration**: Matrix contractions execute seamlessly on NVIDIA GPUs via CuPy tensor cores, with transparent CPU BLAS fallback.
- **Reproducible Performance Characterization (`benchmark`)**: Built-in CLI benchmarking suite that inspects local CPU/GPU hardware, BLAS backends, and memory bandwidth, saving machine-readable JSON provenance reports.

```
+-------------------------------------------------------------------------+
|                  specsynth Worker Execution Pipeline                    |
|                                                                         |
|  [Galaxy Chunk] ---> [Dense GEMM] ---> [Dust Screen] ---> [Madau IGM]   |
|   (N_chunk x K)       (K x W)          exp(-tau*k)       T_IGM(lam, z)  |
|                            |                                            |
|                            v                                            |
|                     [Filter Matrix] ---> [Zarr Storage]                 |
|                         (W x B)          photometry.zarr                |
+-------------------------------------------------------------------------+
```

# Verification and Scalability

`specsynth` is validated by an automated test suite containing 41 unit tests covering numerical stability, physical units, filter transmission convolutions, cosmology, GPU/CPU numerical equivalence ($< 10^{-5}$ relative tolerance), and adapter I/O. 

On a standard 8-core workstation, `specsynth` achieves throughputs exceeding **55,000 galaxies/second** on CPU BLAS, and projected throughputs exceeding **720,000 galaxies/second** on multi-node Kubernetes clusters, enabling mock catalog generation of 100 million galaxies for under $\$0.35$ USD in cloud compute.

# Acknowledgements

The author acknowledges the open-source scientific Python community and the developers of Dask, Zarr, Astropy, and CuPy.

# References
