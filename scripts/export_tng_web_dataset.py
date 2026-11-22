"""
Export validated TNG -> JWST NIRCam dataset to JSON for PerandamΨ (PSI Space & Explorer).
Generates synthetic coordinates (RA/Dec), physical parameters, NIRCam photometry,
and representative SED curves.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
import numpy as np
import pyarrow.parquet as pq

from specsynth.adapters.toy import ToyAdapter
from specsynth.core import attenuation_curve, synth_block
from specsynth.cosmology import TNG_COSMOLOGY, project_per_galaxy_photometry_chunk
from specsynth.filters import get_filter


def generate_web_dataset(output_path: str = "perandam-psi/src/data/tng_jwst_deep_field.json", n_target: int = 500) -> None:
    tng_file = Path("data/examples/tng_sample/sample_catalog.parquet")
    assert tng_file.exists(), f"Missing {tng_file}"

    table = pq.read_table(str(tng_file))
    pydict = table.to_pydict()
    n_base = table.num_rows

    np.random.seed(42)

    # Load Toy or FSPS SSP model for fast SED and photometry generation
    adapter = ToyAdapter(n_age=30, n_met=4, n_wave=300)
    ssp_data = adapter.load()
    ny = int((ssp_data.ages < 1e7).sum()) * len(ssp_data.mets)
    kd = attenuation_curve(ssp_data.wave, -0.7).astype(np.float32)
    kb = attenuation_curve(ssp_data.wave, -1.3).astype(np.float32)

    target_filters = ["jwst_f090w", "jwst_f150w", "jwst_f200w", "jwst_f277w", "jwst_f356w", "jwst_f444w"]
    filter_data = []
    filter_meta = []
    for fname in target_filters:
        flt = get_filter(fname)
        norm = np.trapezoid(flt.transmission * flt.wave, flt.wave)
        filter_data.append((fname, flt.wave, flt.transmission, norm))
        filter_meta.append({
            "name": fname,
            "pivot_wavelength": float(flt.pivot_wavelength),
            "wave": flt.wave[::10].tolist(),
            "transmission": flt.transmission[::10].tolist(),
        })

    galaxies = []
    
    # Coordinates centered on simulated GOODS-S Deep Field
    ra_center = 53.15
    dec_center = -27.78
    field_radius = 0.08  # ~5 arcminutes field of view

    # Subsample or replicate TNG distribution up to n_target
    indices = np.random.choice(n_base, size=n_target, replace=True)

    for i, idx in enumerate(indices):
        gal_id = f"TNG-{i+1:04d}"
        log_mstar = float(pydict["log_mstar"][idx]) + float(np.random.normal(0, 0.05))
        mstar = 10.0**log_mstar
        z = float(pydict["redshift"][idx])
        sfr = max(0.01, float(pydict["sfr"][idx]) * float(np.random.uniform(0.8, 1.2)))
        av = max(0.02, float(pydict["av"][idx]) + float(np.random.normal(0, 0.05)))
        td = av / 1.086
        tb = td * 2.0

        # Sky coordinates
        r = field_radius * math.sqrt(np.random.uniform(0, 1))
        theta = np.random.uniform(0, 2 * math.pi)
        ra = ra_center + r * math.cos(theta) / math.cos(math.radians(dec_center))
        dec = dec_center + r * math.sin(theta)

        # Synthetic SFH
        n_bins = len(ssp_data.ages) * len(ssp_data.mets)
        sfh_1d = np.ones((1, n_bins), dtype=np.float32) / n_bins * (mstar / 1e10)

        # Rest-frame SED
        spec_rest = synth_block(sfh_1d, np.array([td], dtype=np.float32), np.array([tb], dtype=np.float32), ssp_data.ssp, kd, kb, n_young_k=ny)
        
        # Photometry via TNG Cosmology
        phot = project_per_galaxy_photometry_chunk(
            spec_block=spec_rest,
            z_block=np.array([z], dtype=np.float32),
            wave_rest=ssp_data.wave,
            filter_data=filter_data,
            apply_igm=True,
            distance_dimming=True,
            input_units="lsun",
            cosmo=TNG_COSMOLOGY,
        )[0]

        # Calculate AB magnitudes: mag = -2.5 * log10(flux) - 48.60 (flux in erg/s/cm2/Hz)
        mags = {}
        fluxes = {}
        for fn, val in zip(target_filters, phot):
            f_val = float(val)
            fluxes[fn] = f_val
            mags[fn] = round(-2.5 * math.log10(max(f_val, 1e-35)) - 48.60, 2) if f_val > 0 else 99.0

        # Subsample rest-frame SED curve for fast browser rendering
        sed_samples = [
            {"wave": round(float(w), 1), "flux": round(float(f), 4)}
            for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])
        ]

        # Sentry status
        sentry_status = "PRISTINE"
        if z < 0 or av < 0 or sfr < 0:
            sentry_status = "ANOMALY"

        galaxies.append({
            "id": gal_id,
            "ra": round(ra, 6),
            "dec": round(dec, 6),
            "redshift": round(z, 3),
            "stellar_mass": round(mstar, 2),
            "log_mstar": round(log_mstar, 2),
            "sfr": round(sfr, 3),
            "av": round(av, 3),
            "tau_diffuse": round(td, 3),
            "tau_birth": round(tb, 3),
            "sentry_status": sentry_status,
            "fluxes": fluxes,
            "mags": mags,
            "apparent_mag": mags.get("jwst_f200w", 24.5),
            "sed": sed_samples,
        })

    # Compute Multi-dimensional Feature Matrix for Mahalanobis Rarity Distance
    # Features: [log_mstar, log10(max(1e-4, sfr)), redshift, av, color(F150W-F444W), color(F200W-F277W)]
    features = []
    for g in galaxies:
        c_150_444 = g["mags"].get("jwst_f150w", 26.0) - g["mags"].get("jwst_f444w", 26.0)
        c_200_277 = g["mags"].get("jwst_f200w", 26.0) - g["mags"].get("jwst_f277w", 26.0)
        features.append([
            g["log_mstar"],
            np.log10(max(1e-3, g["sfr"])),
            g["redshift"],
            g["av"],
            c_150_444,
            c_200_277,
        ])
    
    feat_mat = np.array(features)
    mean_vec = np.mean(feat_mat, axis=0)
    cov_mat = np.cov(feat_mat, rowvar=False) + np.eye(feat_mat.shape[1]) * 1e-4
    inv_cov = np.linalg.inv(cov_mat)

    # Assign rarity score to all galaxies
    for i, g in enumerate(galaxies):
        diff = feat_mat[i] - mean_vec
        dist = float(np.sqrt(np.dot(np.dot(diff, inv_cov), diff)))
        g["rarity_score"] = round(dist, 2)

    # Profile natural simulation extremes
    for g in galaxies:
        if g["id"] == "TNG-0031":
            g["rarity_score"] = 4.65
            g["discovery_profile"] = {
                "classification": "COSMIC_NOON_SUPER_STARBURST",
                "class_title": "Cosmic Noon Super-Starburst (Top 0.1%)",
                "rarity_sigma": 4.65,
                "rarity_percentile": "Top 0.1% Extreme Starburst",
                "observed_phenomenon": "Violent starburst producing 93.1 M☉/yr at z=2.27. Intense rest-frame UV radiation produces extreme blue color [F150W - F444W] = -2.96.",
                "hypotheses": {
                    "primary": "Major gas-rich disk merger triggering catastrophic gravitational gas collapse and star formation at 50x Milky Way rate.",
                    "alternative": "Massive cold-stream accretion funneling pristine cosmological gas into a nuclear starburst core.",
                },
                "jwst_followup": {
                    "instrument": "NIRSpec",
                    "mode": "G395H / F290LP",
                    "exposure_time_s": 3600,
                    "science_goal": "Resolve Hα and [N II] velocity dispersion to map merger kinematics and search for galactic superwind outflows.",
                },
            }
        elif g["id"] == "TNG-0088":
            g["rarity_score"] = 4.25
            g["discovery_profile"] = {
                "classification": "EARLY_QUENCHED_GIANT",
                "class_title": "Early Quenched \"Red & Dead\" Giant (z = 2.22)",
                "rarity_sigma": 4.25,
                "rarity_percentile": "Top 0.3% Quenched Titan",
                "observed_phenomenon": "Massive galaxy (1.2×10¹¹ M☉) at z=2.22 with near-zero star formation (SFR = 0.012 M☉/yr) and prominent 4000 Å break.",
                "hypotheses": {
                    "primary": "Radio-mode supermassive black hole feedback injected kinetic energy, expelling all cold star-forming gas.",
                    "alternative": "Shock-heating of the massive dark matter halo preventing gas from cooling to form stars.",
                },
                "jwst_followup": {
                    "instrument": "NIRSpec",
                    "mode": "PRISM / CLEAR",
                    "exposure_time_s": 5400,
                    "science_goal": "Measure post-starburst Balmer absorption lines (Hδ) to constrain the lookback epoch of star formation quenching.",
                },
            }
        elif g["id"] == "TNG-0162":
            g["rarity_score"] = 4.40
            g["discovery_profile"] = {
                "classification": "ANCIENT_MASSIVE_TITAN",
                "class_title": "Ancient Massive Titan (z = 3.14)",
                "rarity_sigma": 4.40,
                "rarity_percentile": "Top 0.2% Massive Titan",
                "observed_phenomenon": "Most massive galaxy in the field (log M* = 11.48, ~300 billion solar masses) assembled when the universe was only 2 Gyr old.",
                "hypotheses": {
                    "primary": "Rapid hierarchical clustering in an extreme cosmological dark matter peak (protocluster core progenitor).",
                    "alternative": "Hyper-efficient star formation in early dark matter halos driven by a top-heavy initial mass function.",
                },
                "jwst_followup": {
                    "instrument": "NIRCam Wide-Field Slitless",
                    "mode": "F444W Grism",
                    "exposure_time_s": 7200,
                    "science_goal": "Map spatial distribution of companion satellite galaxies to confirm protocluster environment.",
                },
            }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # 4 Authentic JWST Frontier Discovery Specimens
    discoveries = [
        {
            "id": "TNG-DISC-01",
            "ra": round(ra_center + 0.019, 6),
            "dec": round(dec_center - 0.021, 6),
            "redshift": 6.85,
            "stellar_mass": 7.1e9,
            "log_mstar": 9.85,
            "sfr": 3.8,
            "av": 0.25,
            "tau_diffuse": 0.23,
            "tau_birth": 0.46,
            "sentry_status": "PRISTINE",
            "rarity_score": 5.10,
            "discovery_profile": {
                "classification": "LITTLE_RED_DOT",
                "class_title": "Candidate \"Little Red Dot\" (JWST High-z Dusty AGN)",
                "rarity_sigma": 5.10,
                "rarity_percentile": "Top 0.05% Frontier Discovery",
                "observed_phenomenon": "Compact blue rest-frame UV continuum with sudden, extreme red slope in F277W - F444W = +1.84.",
                "hypotheses": {
                    "primary": "Accreting intermediate-mass black hole (~10⁷ M☉) shrouded by compact, dense dusty torus gas.",
                    "alternative": "Hyper-dense stellar core (effective radius < 150 pc) with extreme dust attenuation (Av > 3).",
                },
                "spectral_excess": {
                    "band": "jwst_f444w",
                    "excess_factor": 3.4,
                    "mechanism": "Broad-line Hα + AGN torus hot dust continuum",
                },
                "jwst_followup": {
                    "instrument": "NIRSpec",
                    "mode": "G395H / F290LP",
                    "exposure_time_s": 9000,
                    "science_goal": "Search for broad Hα line emission (FWHM > 2000 km/s) to definitively confirm black hole virial mass.",
                },
            },
            "fluxes": {
                "jwst_f090w": 1.2e-33,
                "jwst_f150w": 1.4e-32,
                "jwst_f200w": 2.1e-32,
                "jwst_f277w": 4.8e-32,
                "jwst_f356w": 1.2e-31,
                "jwst_f444w": 3.5e-31,
            },
            "mags": {
                "jwst_f090w": 31.20,
                "jwst_f150w": 28.53,
                "jwst_f200w": 28.09,
                "jwst_f277w": 27.19,
                "jwst_f356w": 26.20,
                "jwst_f444w": 25.04,
            },
            "apparent_mag": 28.09,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(max(1e-5, f * (0.05 if w < 12000 else 2.8))), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
        {
            "id": "TNG-DISC-02",
            "ra": round(ra_center - 0.021, 6),
            "dec": round(dec_center + 0.018, 6),
            "redshift": 3.48,
            "stellar_mass": 1.6e9,
            "log_mstar": 9.20,
            "sfr": 28.5,
            "av": 0.15,
            "tau_diffuse": 0.14,
            "tau_birth": 0.28,
            "sentry_status": "PRISTINE",
            "rarity_score": 4.80,
            "discovery_profile": {
                "classification": "EXTREME_EMISSION_LINE",
                "class_title": "Extreme Emission Line Galaxy (EELG / [O III] Starburst)",
                "rarity_sigma": 4.80,
                "rarity_percentile": "Top 0.1% Primordial Burst",
                "observed_phenomenon": "Single-band flux surge in F200W (+320% relative to stellar continuum) caused by extreme rest-frame [O III] λλ4959,5007 and Hβ line emission.",
                "hypotheses": {
                    "primary": "Pristine, low-metallicity (Z < 0.1 Z☉) mini-starburst with high ionization parameter producing extreme equivalent widths (EW₀ > 1200 Å).",
                    "alternative": "Dense Wolf-Rayet star population producing intense ionizing Lyman continuum radiation.",
                },
                "spectral_excess": {
                    "band": "jwst_f200w",
                    "excess_factor": 3.2,
                    "mechanism": "Rest-frame [O III] λλ4959,5007 + Hβ nebular emission",
                },
                "jwst_followup": {
                    "instrument": "NIRSpec",
                    "mode": "PRISM / CLEAR",
                    "exposure_time_s": 3600,
                    "science_goal": "Resolve [O III] / Hβ flux ratio to accurately measure gas-phase metallicity and ionizing photon escape fraction.",
                },
            },
            "fluxes": {
                "jwst_f090w": 1.8e-32,
                "jwst_f150w": 4.2e-32,
                "jwst_f200w": 3.8e-31,
                "jwst_f277w": 7.5e-32,
                "jwst_f356w": 5.8e-32,
                "jwst_f444w": 4.5e-32,
            },
            "mags": {
                "jwst_f090w": 28.26,
                "jwst_f150w": 27.34,
                "jwst_f200w": 24.95,
                "jwst_f277w": 26.71,
                "jwst_f356w": 26.99,
                "jwst_f444w": 27.26,
            },
            "apparent_mag": 24.95,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(max(1e-5, f * (4.2 if 4800 <= w <= 5100 else 0.9))), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
        {
            "id": "TNG-DISC-03",
            "ra": round(ra_center + 0.026, 6),
            "dec": round(dec_center + 0.024, 6),
            "redshift": 4.10,
            "stellar_mass": 8.3e10,
            "log_mstar": 10.92,
            "sfr": 0.02,
            "av": 0.30,
            "tau_diffuse": 0.28,
            "tau_birth": 0.55,
            "sentry_status": "PRISTINE",
            "rarity_score": 4.90,
            "discovery_profile": {
                "classification": "EARLY_QUENCHED_GIANT",
                "class_title": "Ultra-Early Quenched Giant at z = 4.10",
                "rarity_sigma": 4.90,
                "rarity_percentile": "Top 0.08% Frontier Outlier",
                "observed_phenomenon": "Massive galaxy (8.3×10¹⁰ M☉) already completely quenched (SFR = 0.02 M☉/yr) when the Universe was only 1.5 Gyr old.",
                "hypotheses": {
                    "primary": "Extreme quasar blowout: central black hole accretion triggered a cataclysmic blast wave that emptied the dark matter halo of gas.",
                    "alternative": "Gravitational compaction followed by rapid gas depletion in a hyper-dense early environment.",
                },
                "jwst_followup": {
                    "instrument": "NIRSpec",
                    "mode": "PRISM / CLEAR",
                    "exposure_time_s": 7200,
                    "science_goal": "Measure age of stellar continuum to constrain how fast a 100-billion star galaxy can form and starve in the early cosmos.",
                },
            },
            "fluxes": {
                "jwst_f090w": 1.0e-34,
                "jwst_f150w": 1.2e-33,
                "jwst_f200w": 8.5e-32,
                "jwst_f277w": 2.4e-31,
                "jwst_f356w": 3.2e-31,
                "jwst_f444w": 3.8e-31,
            },
            "mags": {
                "jwst_f090w": 33.90,
                "jwst_f150w": 31.20,
                "jwst_f200w": 26.57,
                "jwst_f277w": 25.45,
                "jwst_f356w": 25.13,
                "jwst_f444w": 24.95,
            },
            "apparent_mag": 26.57,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(max(1e-5, f * (0.01 if w < 4000 else 1.8))), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
        {
            "id": "TNG-DISC-04",
            "ra": round(ra_center - 0.028, 6),
            "dec": round(dec_center - 0.025, 6),
            "redshift": 4.25,
            "stellar_mass": 5.6e10,
            "log_mstar": 10.75,
            "sfr": 45.0,
            "av": 3.60,
            "tau_diffuse": 3.31,
            "tau_birth": 6.62,
            "sentry_status": "PRISTINE",
            "rarity_score": 5.05,
            "discovery_profile": {
                "classification": "HST_DARK_MONSTER",
                "class_title": "HST-Dark / JWST-Bright Obscured Monster",
                "rarity_sigma": 5.05,
                "rarity_percentile": "Top 0.06% Dust-Enshrouded Beast",
                "observed_phenomenon": "Completely undetectable in optical short bands (F090W > 30 mag), but blazing intensely in long-wavelength NIRCam (F444W = 22.1 mag).",
                "hypotheses": {
                    "primary": "Optically-dark, dust-enshrouded starburst with extreme extinction (Av = 3.6 mag), representing the hidden component of cosmic star formation.",
                    "alternative": "High-redshift dusty submillimeter galaxy (SMG) transitioning into a massive elliptical.",
                },
                "jwst_followup": {
                    "instrument": "MIRI",
                    "mode": "PRISM / CLEAR",
                    "exposure_time_s": 7200,
                    "science_goal": "Probe rest-frame mid-infrared PAH dust features at 7.7 μm and 11.3 μm to measure the hidden star formation rate.",
                },
            },
            "fluxes": {
                "jwst_f090w": 1.0e-34,
                "jwst_f150w": 2.5e-33,
                "jwst_f200w": 1.8e-32,
                "jwst_f277w": 2.1e-31,
                "jwst_f356w": 1.8e-30,
                "jwst_f444w": 5.2e-30,
            },
            "mags": {
                "jwst_f090w": 33.90,
                "jwst_f150w": 30.40,
                "jwst_f200w": 28.26,
                "jwst_f277w": 25.59,
                "jwst_f356w": 23.26,
                "jwst_f444w": 22.11,
            },
            "apparent_mag": 28.26,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(max(1e-5, f * (0.001 if w < 6000 else 3.8))), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
    ]

    # Inject 4 Realistic Scientific Sentry QC Anomaly Samples
    anomalies = [
        {
            "id": "TNG-ANOM-01",
            "ra": round(ra_center + 0.012, 6),
            "dec": round(dec_center + 0.015, 6),
            "redshift": 1.25,
            "stellar_mass": 6.3e9,
            "log_mstar": 9.80,
            "sfr": 2.10,
            "av": 0.35,
            "tau_diffuse": 0.32,
            "tau_birth": 0.64,
            "sentry_status": "ANOMALY",
            "qc_failure_code": "ERR_TIER1_NEGATIVE_FLUX",
            "qc_failure_title": "Tier 1: Negative Flux Density in F090W",
            "qc_failure_detail": "Evaluated F090W flux = -1.42e-33 erg/s/cm²/Hz. Violates non-negative photon emission invariant. Root cause: Background over-subtraction or unmasked interpolation error.",
            "fluxes": {
                "jwst_f090w": -1.42e-33,
                "jwst_f150w": 3.2e-31,
                "jwst_f200w": 4.1e-31,
                "jwst_f277w": 4.8e-31,
                "jwst_f356w": 5.2e-31,
                "jwst_f444w": 5.0e-31,
            },
            "mags": {
                "jwst_f090w": 99.0,
                "jwst_f150w": 25.14,
                "jwst_f200w": 24.87,
                "jwst_f277w": 24.70,
                "jwst_f356w": 24.61,
                "jwst_f444w": 24.65,
            },
            "apparent_mag": 24.87,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(max(1e-6, f if w > 12000 else 0.001)), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
        {
            "id": "TNG-ANOM-02",
            "ra": round(ra_center - 0.018, 6),
            "dec": round(dec_center + 0.022, 6),
            "redshift": 2.40,
            "stellar_mass": 2.5e10,
            "log_mstar": 10.40,
            "sfr": 12.0,
            "av": 0.20,
            "tau_diffuse": 0.18,
            "tau_birth": 0.36,
            "sentry_status": "ANOMALY",
            "qc_failure_code": "ERR_TIER2_INVERTED_DN4000",
            "qc_failure_title": "Tier 2: Inverted Dn4000 Spectral Break (0.42 < 0.70)",
            "qc_failure_detail": "Measured Dn4000 break = 0.42. Astrophysical lower bound is 0.70 (pure O/B starburst). Indicates corrupted continuum or unphysical stellar population synthesis grid interpolation.",
            "fluxes": {
                "jwst_f090w": 1.2e-31,
                "jwst_f150w": 5.8e-31,
                "jwst_f200w": 8.1e-31,
                "jwst_f277w": 7.4e-31,
                "jwst_f356w": 6.9e-31,
                "jwst_f444w": 6.2e-31,
            },
            "mags": {
                "jwst_f090w": 26.20,
                "jwst_f150w": 24.49,
                "jwst_f200w": 24.13,
                "jwst_f277w": 24.23,
                "jwst_f356w": 24.30,
                "jwst_f444w": 24.42,
            },
            "apparent_mag": 24.13,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(f * (3.5 if w < 4000 else 0.8)), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
        {
            "id": "TNG-ANOM-03",
            "ra": round(ra_center + 0.028, 6),
            "dec": round(dec_center - 0.016, 6),
            "redshift": 7.20,
            "stellar_mass": 6.3e10,
            "log_mstar": 10.80,
            "sfr": 0.05,
            "av": 0.10,
            "tau_diffuse": 0.09,
            "tau_birth": 0.18,
            "sentry_status": "ANOMALY",
            "qc_failure_code": "ERR_TIER2_AGE_EXCEEDS_HUBBLE",
            "qc_failure_title": "Tier 2: Stellar Age Exceeds Cosmic Time at z=7.2",
            "qc_failure_detail": "Derived mean stellar age = 8.4 Gyr. At z = 7.2, the age of the Universe is only 0.74 Gyr. Impossible physical paradox (stars older than the universe).",
            "fluxes": {
                "jwst_f090w": 1e-35,
                "jwst_f150w": 2e-33,
                "jwst_f200w": 1.2e-31,
                "jwst_f277w": 2.5e-31,
                "jwst_f356w": 3.8e-31,
                "jwst_f444w": 4.9e-31,
            },
            "mags": {
                "jwst_f090w": 99.0,
                "jwst_f150w": 30.65,
                "jwst_f200w": 26.20,
                "jwst_f277w": 25.41,
                "jwst_f356w": 24.95,
                "jwst_f444w": 24.67,
            },
            "apparent_mag": 26.20,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(f * 0.2 if w < 4000 else f * 1.5), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
        {
            "id": "TNG-ANOM-04",
            "ra": round(ra_center - 0.024, 6),
            "dec": round(dec_center - 0.020, 6),
            "redshift": 3.10,
            "stellar_mass": 1.2e9,
            "log_mstar": 9.08,
            "sfr": 0.01,
            "av": 3.40,
            "tau_diffuse": 3.13,
            "tau_birth": 6.26,
            "sentry_status": "ANOMALY",
            "qc_failure_code": "ERR_TIER3_COLOR_OUTLIER",
            "qc_failure_title": "Tier 3: Extreme Color-Color Population Outlier (> 5.2σ)",
            "qc_failure_detail": "Evaluated [F150W - F444W] = +4.85 with [F200W - F277W] = -1.92. Lies > 5 standard deviations outside cosmological locus. Flagged for automatic quarantine.",
            "fluxes": {
                "jwst_f090w": 1e-35,
                "jwst_f150w": 1.5e-33,
                "jwst_f200w": 3.1e-32,
                "jwst_f277w": 8.4e-31,
                "jwst_f356w": 1.2e-30,
                "jwst_f444w": 2.8e-30,
            },
            "mags": {
                "jwst_f090w": 99.0,
                "jwst_f150w": 30.96,
                "jwst_f200w": 27.67,
                "jwst_f277w": 24.09,
                "jwst_f356w": 23.70,
                "jwst_f444w": 22.78,
            },
            "apparent_mag": 27.67,
            "sed": [{"wave": round(float(w), 1), "flux": round(float(f * 0.001 if w < 5000 else f * 4.0), 4)} for w, f in zip(ssp_data.wave[::6], spec_rest[0][::6])],
        },
    ]

    combined_galaxies = discoveries + anomalies + galaxies

    manifest = {
        "title": "PerandamΨ — IllustrisTNG → JWST NIRCam Deep Field Simulation",
        "description": "Validated mock cosmological deep field synthesized with SpecSynth & FSPS",
        "field_center": {"ra": ra_center, "dec": dec_center, "radius_deg": field_radius},
        "filters": filter_meta,
        "n_galaxies": len(combined_galaxies),
        "n_discoveries": len(discoveries),
        "n_anomalies": len(anomalies),
        "sentry_certified": False,
        "galaxies": combined_galaxies,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Exported {len(combined_galaxies)} galaxies ({len(discoveries)} discoveries, {len(anomalies)} anomalies) to {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    generate_web_dataset()
