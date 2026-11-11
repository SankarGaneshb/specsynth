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

`specsynth` is an open-source, cloud-native Python framework engineered for out-of-core, distributed stellar population synthesis (SPS) and broadband mock catalog generation. By coupling chunked **Zarr** storage via `fsspec` with **Dask** distributed task graphs [@rocklin2015dask] and optional **CuPy** GPU tensor contractions [@okuta2017cupy], `specsynth` streams galaxy parameters from cloud object stores, contracts them against Simple Stellar Population (SSP) spectral grids in worker RAM/cache, and projects them in-flight into photometric bandpasses without ever materializing multi-terabyte intermediate spectra onto disk.

# Statement of Need and Comparison with Alternative Architectures

Generating mock catalogs for modern cosmological hydrodynamical simulations (e.g., IllustrisTNG [@pillepich2018simulating], EAGLE, or Semi-Analytic Models) requires synthesizing SEDs for $10^7 - 10^9+$ objects. Existing computational approaches suffer from fundamental architectural limitations:

1. **Standalone SPS Wrappers (e.g., FSPS + MPI or Dask Bags)**: Codes such as FSPS [@conroy2009propagation] and BC03 [@bruzual2003stellar] were designed for single-galaxy precision. Wrapping them in parallel loops (e.g., via `mpi4py` or `dask.bag.map`) requires shipping complex C/Fortran state to worker processes. Because these integrators re-evaluate stellar evolutionary tracks and interpolate isochrones per galaxy, they incur severe worker initialization latency, high per-worker memory footprints, and redundant computations.
2. **General-Purpose Big Data Engines (Apache Spark, Ray)**: Distributed engines such as Apache Spark [@zaharia2016apache] and Ray [@moritz2018ray] are optimized for tabular relational joins, row-level transformations, and distributed machine learning. However, they lack native zero-copy integration with high-performance BLAS/CuPy tensor contractions, introduce substantial JVM-Python serialization overhead when transferring large dense spectral arrays, and lack direct chunked streaming from Zarr without POSIX filesystem mounts.
3. **In-Memory Array Processing (NumPy, SciPy)**: Standard scientific Python workflows [@harris2020array] rely on allocating monolithic arrays in RAM. Storing high-resolution spectra ($W \approx 4,000 - 10,000$ wavelength bins) for $10^8$ galaxies requires hundreds of terabytes of memory, inevitably triggering out-of-memory (OOM) crashes or exhausting local scratch disks.

`specsynth` resolves these challenges by reformulating stellar population synthesis as a **cloud-native, linear matrix-streaming pipeline**:

| Architectural Dimension | Standalone SPS Wrappers (FSPS + MPI) | General Big Data (Spark / Ray) | **`specsynth` (This Work)** |
| :--- | :--- | :--- | :--- |
| **Physics vs. Execution** | Coupled (integrates per galaxy) | Agnostic | **Decoupled (Offline $K \times W$ basis, online streaming GEMM)** |
| **Storage Architecture** | POSIX filesystem (NFS / Lustre) | HDFS / Object store (JVM partitioned) | **Cloud object storage (`s3://`, `gs://`, `abfs://`) via Zarr/fsspec** |
| **Memory Footprint** | Large (stateful models per core) | High (JVM serialization & shuffle) | **Bounded strictly to one chunk ($O(N_{\text{chunk}})$)** |
| **In-Flight Filter Projection** | ❌ (Must write or retain spectra) | ⚠️ (Requires custom pipeline stages) | **✅ (Streams spectra in L3 cache/VRAM, writes only photometry)** |
| **GPU Tensor Cores** | ❌ (CPU only) | ⚠️ (Requires specialized plugins) | **✅ (CuPy GEMM with transparent CPU BLAS fallback)** |

# Astrophysical Framework

For each galaxy $g$, `specsynth` evaluates composite stellar populations using a two-component dust attenuation model [@charlot2000simple]:

$$F_g(\lambda) = D_g(\lambda) \cdot \left[ \sum_{k \in \text{old}} \text{SFH}[g,k] \cdot \text{SSP}[k,\lambda] + B_g(\lambda) \cdot \sum_{k \in \text{young}} \text{SFH}[g,k] \cdot \text{SSP}[k,\lambda] \right]$$

where $\text{SFH}[g,k]$ represents the stellar mass formed in the age-metallicity grid cell $k$, and $\text{SSP}[k,\lambda]$ is the intrinsic stellar luminosity per unit mass. Stars younger than $10^7\text{ yr}$ sit inside birth clouds. The dust attenuation screens for the diffuse interstellar medium ($D_g$) and young birth clouds ($B_g$) are parameterized as power laws:

$$D_g(\lambda) = \exp\left(-\tau_{\text{diffuse}} \cdot \left(\frac{\lambda}{5500\text{ \AA}}\right)^{\alpha_{\text{diffuse}}}\right)$$

$$B_g(\lambda) = \exp\left(-\tau_{\text{birth}} \cdot \left(\frac{\lambda}{5500\text{ \AA}}\right)^{\alpha_{\text{birth}}}\right)$$

For cosmological simulations at redshift $z > 0$, `specsynth` shifts wavelengths according to $\lambda_{\text{obs}} = \lambda_{\text{rest}}(1+z)$, applies $(1+z)^{-1}$ flux dimming, and integrates photoelectric absorption through the intergalactic neutral hydrogen medium via the Madau (1995) transmission function $T_{\text{IGM}}(\lambda, z)$ [@madau1995radiative]:

$$T_{\text{IGM}}(\lambda, z) = \exp\left( -\tau_{\text{lines}}(\lambda, z) - \tau_{\text{continuum}}(\lambda, z) \right)$$

integrating the resonant Lyman series transitions shortward of Ly$\alpha$ ($1215.67\text{ \AA}$) down to the Lyman limit ($911.75\text{ \AA}$).

# Architecture and Engineering Implementation

The core execution path is designed around dense matrix multiplication (GEMM) over chunked arrays:

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

1. **Pluggable Model Adapters**: Standardized adapters convert raw spectral libraries into immutable Zarr basis matrices ($K \times W$), supporting Bruzual & Charlot (2003) `.ised` binary/ASCII tables [@bruzual2003stellar], E-MILES FITS headers [@vazdekis2016uv], FSPS grids [@conroy2009propagation], and generic multi-dimensional FITS/HDF5/NPZ datasets.
2. **In-Flight Filter Projection**: When broadband photometry is requested (`--filters` or `--bands`), the intermediate spectrum $\mathbf{F}_{\text{chunk}}$ is projected in-flight into $B$ photometric bands:
   $$\mathbf{Phot} = \mathbf{F}_{\text{chunk}} \times \mathbf{M}_{\text{filter}}$$
   Full spectra are streamed through worker cache/VRAM and discarded, reducing persistent cloud storage by **$>99.9\%$** ($3.2\text{ GB}$ vs. $3.2\text{ TB}$ for $10^8$ galaxies).
3. **Simulation Catalog Ingestion (`import-catalog`)**: Native ingestion of cosmological simulation catalogs from Parquet, FITS, HDF5, CSV, and NPZ formats, automatically mapping physical columns (mass, age, metallicity, dust) to SFH parameter matrices.
4. **Task Graph Guard and Batch Pipelining (`--batch-chunks`)**: For billion-object simulations ($N \ge 10^8$), submitting millions of chunk tasks bloats the centralized Dask scheduler memory. `specsynth` enforces an automatic task graph guard (keeping total graph tasks $< 25,000$) and provides a sliding-window batch pipeline (`--batch-chunks`) that bounds scheduler memory strictly to $O(B)$ chunks.

# Performance, Scalability, and Reproducibility

To maintain strict scientific and engineering rigor, `specsynth` evaluates four performance dimensions independently:

### 1. Numerical Correctness
Distributed production execution (float32 Dask / Zarr streaming) is verified against an independent serial reference engine evaluated in full **float64 precision** over 10,000 galaxies ($K = 128$ SSP templates, $W = 8,000$ wavelength bins):

| Correctness Metric | Value | Numerical Tolerance | Status |
| :--- | :---: | :---: | :---: |
| **Max Relative Spectral Error** | **$9.87 \times 10^{-7}$** | $< 5.0 \times 10^{-4}$ | **PASS** |
| **Mean Relative Spectral Error** | **$8.77 \times 10^{-8}$** | $< 1.0 \times 10^{-5}$ | **PASS** |
| **Photometry Integrated Error** | **$2.15 \times 10^{-7}\text{ mag}$** | $< 1.0 \times 10^{-4}\text{ mag}$ | **PASS** |
| **Root Mean Square Error (RMSE)** | **$2.24 \times 10^{-11}$** | -- | **PASS** |

### 2. Single-Node Performance and Hardware Acceleration
Evaluated on a standardized workload: 10M galaxies, $K = 240$ age-metallicity bins ($40 \times 6$), $W = 4,000$ wavelength bins, projected in-flight to 8 broadband filters ($N_{\text{chunk}} = 20,000$):

| Compute Backend | Processor / Device | Workers / Threads | Throughput | Compute Rate | Speedup |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **CPU (OpenBLAS)** | Intel Core i7-13700H | 2 workers | **14,500 gal/s** | 4.6 GFLOPS | 1.0x (Baseline) |
| **CPU (High-Core BLAS)** | AMD Ryzen 9 7950X (16C) | 8 workers | **56,000 gal/s** | 17.8 GFLOPS | 3.9x |
| **GPU (CuPy / Tensor Cores)**| NVIDIA A10G (24 GB VRAM) | 1 GPU worker | **340,000 gal/s** | 108.2 GFLOPS | **23.4x / 6.1x** |

When the SSP spectral library exceeds worker RAM, the `--wave-chunk` option partitions the wavelength axis, enabling successful synthesis of libraries up to $4\times$ worker RAM with only a $+11.2\%$ runtime overhead.

### 3. Distributed Scaling and Memory Boundedness
Because chunks are statistically independent and the SSP grid is broadcast peer-to-peer once via `client.persist(ssp)`, `specsynth` exhibits near-ideal parallel scaling:

- **Strong Scaling (Fixed 10M Galaxies)**:
  - 1 Worker: $714.2\text{ s}$ ($14,000\text{ gal/s}$, efficiency $1.00$)
  - 2 Workers: $364.9\text{ s}$ ($27,400\text{ gal/s}$, efficiency $0.98$)
  - 4 Workers: $186.0\text{ s}$ ($53,760\text{ gal/s}$, efficiency $0.96$)
  - 8 Workers: $95.8\text{ s}$ ($104,380\text{ gal/s}$, efficiency $0.93$)
  - 16 Workers (Analytical Weak-Scaling Model): $51.5\text{ s}$ ($194,170\text{ gal/s}$, efficiency $0.87$)
  - 32 Workers (Analytical Weak-Scaling Model): $27.6\text{ s}$ ($362,300\text{ gal/s}$, efficiency $0.81$)
- **Weak Scaling (Fixed 500k Galaxies / Worker)**:
  - Runtime remains constant across cluster expansion ($35.7\text{ s}$ at 1 worker to $41.2\text{ s}$ at 32 workers, retaining $>87\%$ parallel efficiency).
- **Out-of-Core Memory Boundedness**:
  - Across catalog sizes varying from $1\text{M}$, $5\text{M}$, $20\text{M}$, to $100\text{M}$ galaxies on a single worker with an 8 GB memory limit, peak RAM remains strictly bounded between $380 - 420\text{ MiB}$ ($O(N_{\text{chunk}})$), with **zero disk spill**.

### 4. Cloud Economics and End-to-End Science
`specsynth` enables extreme cloud cost efficiency on standard Spot compute ($0.088/\text{hr per 8 vCPUs}$):
- **10 Million Galaxies**: ~51 seconds ($0.02\text{ USD}$)
- **100 Million Galaxies**: ~8.4 minutes ($0.25\text{ USD}$)
- **1 Billion Galaxies**: ~75 minutes ($4.20\text{ USD}$)

In an end-to-end scientific test importing an IllustrisTNG-100 catalog (100,000 galaxies), `import-catalog` executed in $3.2\text{ s}$ and synthesized full JWST NIRCam photometry ($z = 2.0$, Madau IGM) in $1.8\text{ s}$, reducing output disk footprint from $3.2\text{ GB}$ (full spectra) to $3.2\text{ MB}$ (photometry).

### Reproducibility Stack
`specsynth` includes an automated benchmarking CLI (`specsynth benchmark`) that profiles host CPU/GPU hardware, RAM, BLAS library (`OpenBLAS`, `MKL`), and CuPy runtime, exporting complete machine-readable provenance reports in JSON format. The automated test suite contains 41 unit tests covering numerical stability, physical units, filter transmission convolutions, cosmology, GPU/CPU numerical equivalence ($< 10^{-5}$ relative tolerance), and catalog ingestion.

# Acknowledgements

The author acknowledges the open-source scientific Python community and the developers of Dask, Zarr, Astropy, and CuPy.

# References
