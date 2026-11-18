# Quickstart

This walkthrough runs an end-to-end forward-modeling pipeline—compiling an SSP basis, generating a mock galaxy catalog, synthesizing redshifted JWST NIRCam broadband photometry with Madau (1995) IGM attenuation, and verifying float32 output against an independent float64 reference.

## 1. Command-Line Quickstart

Use `--scheduler sync` (or `threads`) for fast local runs with zero TCP overhead, or omit it to spin up a multi-worker Dask `LocalCluster`:

```bash
# 1. Compile an analytical SSP basis into Zarr (40 ages x 4 metallicities x 2,000 wavelengths)
specsynth --base ./quickstart_run --scheduler sync \
    make-ssp --adapter toy --n-age 40 --n-met 4 --n-wave 2000

# 2. Generate a reproducible 20,000-galaxy SFH parameter catalog in 5,000-galaxy chunks
specsynth --base ./quickstart_run --scheduler sync \
    make-sfh --n-gal 20000 --chunk 5000

# 3. Synthesize JWST NIRCam photometry at z = 2.0 with Madau (1995) IGM attenuation
#    (Intermediate spectra stay in cache and are discarded after projection)
specsynth --base ./quickstart_run --scheduler sync \
    synth --filters jwst_nircam --redshift 2.0 --igm

# 4. Verify numerical accuracy against an independent float64 reference engine
specsynth --base ./quickstart_run --scheduler sync \
    verify --sample 200

# 5. Run the 4-tier Scientific Sentry QA audit
specsynth --base ./quickstart_run \
    sentry --sample 5000 --output ./quickstart_run/sentry_report.json
```

### Expected Output Structure

```text
quickstart_run/
├── ssp.zarr/          # Compiled SSP basis (ages, mets, wave, ssp)
├── galaxies.zarr/     # Chunked galaxy parameters & SFH weights
├── photometry.zarr/   # Synthesized broadband fluxes & AB magnitudes
└── sentry_report.json # Structured Tier 1-4 QA metrics
```

---

## 2. Python API Quickstart

You can also invoke the core synthesis engine directly from Python for custom workflows or notebook exploration:

```python
import numpy as np
from specsynth.adapters import get_adapter
from specsynth.core import attenuation_curve, sfh_from_params, synth_block, _gen_params
from specsynth.cosmology import DEFAULT_COSMOLOGY, redshift_flux
from specsynth.filters import build_filter_projection_matrix, f_lambda_to_f_nu, flux_to_ab_mag
from specsynth.igm import madau_transmission

# 1. Load an SSP basis (swap "toy" for "bc03", "emiles", "fsps", or "fits")
ssp_data = get_adapter("toy", n_age=30, n_met=4, n_wave=1500).load()

# 2. Construct SFH weights for 500 galaxies
params = _gen_params(np.empty((500, 1)), seed=42)
sfh = sfh_from_params(params, ssp_data.ages, ssp_data.mets)
n_young_k = int(np.sum(ssp_data.ages < 1.0e7)) * len(ssp_data.mets)

# 3. Synthesize rest-frame dust-attenuated spectra via dense BLAS GEMM
k_d = attenuation_curve(ssp_data.wave, -0.7)
k_b = attenuation_curve(ssp_data.wave, -1.3)
rest_lum = synth_block(
    sfh,
    tau_d=params[:, 4],
    tau_b=params[:, 5],
    ssp=ssp_data.ssp,
    k_d=k_d,
    k_b=k_b,
    n_young_k=n_young_k,
)

# 4. Shift to z = 2.0, apply Madau IGM absorption, and project onto JWST NIRCam
z = 2.0
wave_obs, flux_obs = redshift_flux(ssp_data.wave, rest_lum, z=z, cosmo=DEFAULT_COSMOLOGY)
flux_obs *= madau_transmission(wave_obs, z=z)[None, :]

proj_mat, names, pivots = build_filter_projection_matrix(wave_obs, "jwst_nircam")
band_flam = flux_obs @ proj_mat
band_fnu = f_lambda_to_f_nu(band_flam, pivots)
ab_mags = flux_to_ab_mag(band_fnu)

print("JWST NIRCam filters:", names)
print("Median F200W AB magnitude:", np.nanmedian(ab_mags[:, names.index("jwst_f200w")]))
```

## 3. Interactive Notebooks

- **Local / Colab Quickstart**: [`notebooks/quickstart.ipynb`](https://github.com/SankarGaneshb/specsynth/blob/main/notebooks/quickstart.ipynb)
- **Cloud NVIDIA Tesla T4 GPU Benchmark**: [Kaggle Notebook](https://www.kaggle.com/code/bsankarganesh/specsynth-gpu-benchmark)
