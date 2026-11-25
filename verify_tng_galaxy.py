"""
Reproducible SpecSynth Verification for tng100_subhalo_009873.
Verifies that Python SpecSynth forward projection reproduces the browser display
within |Δm| < 0.05 mag across all 6 JWST NIRCam bands.
"""

from pathlib import Path
import numpy as np

from specsynth.adapters.fsps import FSPSAdapter, find_default_fsps_grid
from specsynth.core import attenuation_curve, sfh_from_params, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
from specsynth.filters import get_filter

# 1. Exact Physical Parameters
log_mstar   = 9.25
redshift    = 0.998
av          = 0.159
sfr         = 0.491  # M☉/yr
t_onset     = 3.130  # Gyr
tau         = 1.624  # Gyr e-folding timescale
metallicity = -0.1594  # log(Z/Z_sun)
tau_d       = 0.146  # Diffuse ISM dust
tau_b       = 0.293  # Birth cloud dust

# 2. Load Reference Grid
grid_path = find_default_fsps_grid()
adapter = FSPSAdapter(filepath=grid_path)
ssp_data = adapter.load()

# 3. Form Delayed-Tau SFH normalized to stellar mass
p = np.array([[log_mstar, t_onset, tau, metallicity]], dtype=np.float32)
sfh = sfh_from_params(p, ssp_data.ages, ssp_data.mets)

# 4. Attenuation Curves (Charlot & Fall 2000)
ny = int((ssp_data.ages < 1e7).sum()) * len(ssp_data.mets)
kd = attenuation_curve(ssp_data.wave, -0.7).astype(np.float32)
kb = attenuation_curve(ssp_data.wave, -1.3).astype(np.float32)

# 5. Contract Rest-frame Spectrum: L_lambda [L☉ / Å]
spec_rest = synth_block(
    sfh,
    np.array([tau_d], dtype=np.float32),
    np.array([tau_b], dtype=np.float32),
    ssp_data.ssp,
    kd,
    kb,
    ny,
)

# 6. In-flight Filter Projection into JWST NIRCam Bands
target_filters = ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]
filter_data = []
for fname in target_filters:
    flt = get_filter(fname)
    norm = np.trapezoid(flt.transmission * flt.wave, flt.wave)
    filter_data.append((fname, flt.wave, flt.transmission, norm))

# Project F_lambda [erg/s/cm2/A] with D_L(z) distance dimming and Madau (1995) IGM
phot = project_per_galaxy_photometry_chunk(
    spec_rest,
    np.array([redshift], dtype=np.float32),
    ssp_data.wave,
    filter_data,
    apply_igm=True,
    distance_dimming=True,
    input_units="lsun",
    cosmo=TNG_COSMOLOGY,
)[0]

# 7. Convert F_lambda to f_nu and AB Magnitudes
c_ang_s = 2.99792458e18
m_ab_dict = {}
print("=" * 70)
print(f"Photometry for tng100_subhalo_009873 (z={redshift:.3f}, Av={av:.3f}):")
print("-" * 70)
for i, fn in enumerate(target_filters):
    flt = get_filter(fn)
    f_nu = phot[i] * (flt.pivot_wavelength ** 2) / c_ang_s
    m_ab = -2.5 * np.log10(f_nu) - 48.60 if f_nu > 0 else 99.0
    m_ab_dict[fn] = float(m_ab)
    print(f"  {fn:<12}: {m_ab:.2f} AB mag (f_nu = {f_nu * 1e29:.2f} μJy)")

# 8. Numerical Parity Validation vs. Web Browser Display (|Δm| < 0.05 mag)
browser_mags = {
    "jwst_f090w": 17.65,
    "jwst_f150w": 17.61,
    "jwst_f200w": 17.81,
    "jwst_f277w": 18.19,
    "jwst_f356w": 18.55,
    "jwst_f444w": 18.92,
}
print("-" * 70)
print("Comparing against Web UI Display values:")
all_passed = True
for fn, m_browser in browser_mags.items():
    if fn in m_ab_dict and m_browser < 90.0 and m_ab_dict[fn] < 90.0:
        delta = abs(m_ab_dict[fn] - m_browser)
        status = "MATCH" if delta < 0.05 else "DIVERGED"
        print(f"  {fn:<12}: SpecSynth={m_ab_dict[fn]:.2f} | Web={m_browser:.2f} | |Δm|={delta:.4f} mag [{status}]")
        if delta >= 0.05:
            all_passed = False

print("=" * 70)
if all_passed:
    print("✓ Parity Verified: In-browser display and Python SpecSynth match perfectly (|Δm| < 0.05 mag).")
else:
    print("✗ Parity Check Failed.")
print("=" * 70)
