from __future__ import annotations

import json
import os
import shutil
import tempfile
import numpy as np
import pytest

from specsynth.sentry import (
    AnomalyRecord,
    SentryReport,
    check_energy_conservation,
    check_finite_positive,
    check_magnitude_bounds,
    check_population_bimodality,
    measure_d4000_break,
    measure_uv_slope,
    run_sentry_audit,
)


def test_check_finite_positive_clean():
    flux = np.array([
        [1.0, 2.0, 3.0],
        [0.5, 1.5, 2.5],
    ], dtype=np.float32)
    valid_mask, bad_idx = check_finite_positive(flux)
    assert np.all(valid_mask)
    assert len(bad_idx) == 0


def test_check_finite_positive_catches_nan_inf_negative():
    flux = np.array([
        [1.0, 2.0, 3.0],          # Valid
        [1.0, np.nan, 3.0],       # NaN
        [1.0, np.inf, 3.0],       # +Inf
        [1.0, -np.inf, 3.0],      # -Inf
        [1.0, 0.0, 3.0],          # Zero
        [1.0, -0.5, 3.0],         # Negative
    ], dtype=np.float32)
    valid_mask, bad_idx = check_finite_positive(flux)
    assert valid_mask[0] == True
    assert not np.any(valid_mask[1:])
    assert np.array_equal(bad_idx, np.array([1, 2, 3, 4, 5], dtype=np.int64))


def test_check_energy_conservation_clean_and_violation():
    # Intrinsic flux: 10 units each
    f_intr = np.ones((4, 50), dtype=np.float32) * 10.0
    
    # 0: Attenuated by 50% (Valid)
    # 1: Dust-free exactly equal (Valid Edge Case)
    # 2: Tiny numerical float32 noise (1e-6 above) (Valid within atol)
    # 3: Unphysical energy amplification (10% higher) (Violation)
    f_att = np.copy(f_intr)
    f_att[0] *= 0.5
    f_att[1] *= 1.0
    f_att[2] *= 1.000001
    f_att[3] *= 1.10

    valid_mask, bad_idx, ratios = check_energy_conservation(f_att, f_intr, atol=1e-5)
    assert valid_mask[0] == True
    assert valid_mask[1] == True
    assert valid_mask[2] == True
    assert valid_mask[3] == False
    assert len(bad_idx) == 1
    assert bad_idx[0] == 3
    assert np.isclose(ratios[0], 0.5)
    assert np.isclose(ratios[1], 1.0)


def test_measure_d4000_break_nominal_and_inverted():
    wave = np.linspace(3500.0, 4500.0, 100)
    
    # Galaxy 0: Passive galaxy (strong 4000A break: red flux ~ 2x blue flux)
    flux_passive = np.where(wave >= 4000.0, 2.0, 1.0) * (3800.0 / wave) ** 2
    
    # Galaxy 1: Flat continuum (D_n4000 ~ 1.0)
    flux_flat = np.ones_like(wave) * (3800.0 / wave) ** 2
    
    # Galaxy 2: Inverted break (blue flux > red flux, impossible stellar atmosphere)
    flux_inverted = np.where(wave >= 4000.0, 0.5, 1.5) * (3800.0 / wave) ** 2
    
    batch = np.stack([flux_passive, flux_flat, flux_inverted], axis=0)
    d4000 = measure_d4000_break(wave, batch)
    
    assert len(d4000) == 3
    assert d4000[0] > 1.8   # Passive
    assert 0.95 <= d4000[1] <= 1.05  # Flat
    assert d4000[2] < 0.8   # Inverted anomaly


def test_measure_uv_slope_nominal_and_extreme():
    wave = np.linspace(1400.0, 2600.0, 120)
    
    # Galaxy 0: Star-forming (beta ~ -2.0)
    f_sf = (wave / 2000.0) ** (-2.0)
    
    # Galaxy 1: Flat in F_lambda (beta ~ 0.0)
    f_flat = np.ones_like(wave)
    
    # Galaxy 2: Super-Rayleigh-Jeans unphysical blue explosion (beta ~ -4.5)
    f_unphys_blue = (wave / 2000.0) ** (-4.5)

    batch = np.stack([f_sf, f_flat, f_unphys_blue], axis=0)
    beta = measure_uv_slope(wave, batch)
    
    assert len(beta) == 3
    assert np.isclose(beta[0], -2.0, atol=0.1)
    assert np.isclose(beta[1], 0.0, atol=0.1)
    assert beta[2] < -4.0  # Anomaly


def test_check_magnitude_bounds():
    mags = np.array([
        [18.5, 19.2, 20.1],  # Valid
        [28.0, 29.5, 30.1],  # Faint valid edge case
        [4.2, 5.1, 4.8],     # Absurdly bright star-like (anomaly)
        [45.0, 48.0, 52.0],  # Numerical underflow to dark (anomaly)
    ])
    valid_mask, bad_idx = check_magnitude_bounds(mags, min_mag=10.0, max_mag=35.0)
    assert valid_mask[0] == True
    assert valid_mask[1] == True
    assert valid_mask[2] == False
    assert valid_mask[3] == False
    assert np.array_equal(bad_idx, np.array([2, 3], dtype=np.int64))


def test_check_population_bimodality():
    # Normal diverse color distribution
    colors_normal = np.random.default_rng(42).normal(1.5, 0.4, size=1000)
    rep_normal = check_population_bimodality(colors_normal)
    assert rep_normal["status"] == "OK"
    assert rep_normal["bimodal_dispersion_ok"] == True
    assert rep_normal["std"] > 0.1

    # Degenerate collapsed distribution (all same constant color)
    colors_collapsed = np.full(1000, 1.25)
    rep_collapsed = check_population_bimodality(colors_collapsed)
    assert rep_collapsed["status"] == "COLLAPSED"
    assert rep_collapsed["bimodal_dispersion_ok"] == False
    assert rep_collapsed["variance"] < 1e-5


def test_sentry_report_serialization():
    rep = SentryReport(
        timestamp="2026-11-13T02:00:00Z",
        provenance="Test Audit",
        total_galaxies_evaluated=100,
        passed_count=98,
        flagged_count=2,
        pass_rate_pct=98.0,
        status="WARNING",
        category_summary={"PHYSICAL_ANOMALY": 2},
        anomalies=[
            AnomalyRecord(
                anomaly_id="TEST-01",
                tier=2,
                category="PHYSICAL_ANOMALY",
                severity="WARNING",
                galaxy_index=42,
                metric_name="d4000_break",
                observed_value=0.72,
                expected_range=[0.95, 2.5],
                root_cause="Inverted break",
                remediation="Check SFH",
            )
        ],
    )
    with tempfile.TemporaryDirectory() as td:
        json_path = os.path.join(td, "report.json")
        md_path = os.path.join(td, "report.md")
        
        rep.to_json(json_path)
        rep.to_markdown(md_path)
        
        assert os.path.exists(json_path)
        assert os.path.exists(md_path)
        
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["passed_count"] == 98
            assert len(data["anomalies"]) == 1

        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            assert "Scientific Sentry Quality Assurance Audit Report" in md_text
            assert "#42" in md_text


def test_int64_large_indices():
    # Verify indices exceeding 32-bit int bounds (2^31 - 1 = 2147483647)
    large_idx = np.int64(3_000_000_000)
    anom = AnomalyRecord(
        anomaly_id="LARGE-01",
        tier=1,
        category="NUMERICAL_FAULT",
        severity="CRITICAL",
        galaxy_index=int(large_idx),
        metric_name="finite",
    )
    assert anom.galaxy_index == 3_000_000_000
    assert anom.galaxy_index > 2**31 - 1


def test_run_sentry_audit_with_mocked_store(monkeypatch):
    from unittest.mock import MagicMock
    from specsynth import build_toy_ssp
    from specsynth.core import N_PARAM, _gen_params, sfh_from_params, synth_block

    # 1. Build toy data
    n_age, n_met, n_wave = 5, 2, 80
    ages, mets, wave, ssp = build_toy_ssp(n_age, n_met, n_wave)
    n_gal = 20
    dummy = np.empty((n_gal, N_PARAM), dtype=np.float32)
    params = _gen_params(dummy, 42)
    sfh = sfh_from_params(params, ages, mets)
    td_arr = np.full(n_gal, 0.5, dtype=np.float32)
    tb_arr = np.full(n_gal, 1.0, dtype=np.float32)

    ny = int((ages < 1e7).sum()) * len(mets)
    from specsynth.core import attenuation_curve
    kd = attenuation_curve(wave, -0.7)
    kb = attenuation_curve(wave, -1.3)
    spectra = synth_block(sfh, td_arr, tb_arr, ssp, kd, kb, ny)

    # Mock Zarr groups
    mock_ssp = {
        "ssp": ssp,
        "wave": wave,
        "ages": ages,
        "mets": mets,
    }
    mock_gal = {
        "sfh": sfh,
        "tau_diffuse": td_arr,
        "tau_birth": tb_arr,
    }
    mock_out = {
        "spectra": spectra,
    }

    class MockGroup:
        def __init__(self, data_dict, attrs=None):
            self.data = data_dict
            self.attrs = attrs or {}

        def __getitem__(self, key):
            val = self.data[key]
            mock_arr = MagicMock()
            mock_arr.shape = val.shape
            mock_arr.__getitem__.side_effect = lambda idx: val[idx] if idx != slice(None) else val
            return mock_arr

        def __contains__(self, key):
            return key in self.data

    def mock_open_group(store, mode="r"):
        s = str(store)
        if "ssp" in s:
            return MockGroup(mock_ssp)
        elif "gal" in s:
            return MockGroup(mock_gal)
        else:
            return MockGroup(mock_out, attrs={"redshift": 0.0})

    import zarr
    monkeypatch.setattr(zarr, "open_group", mock_open_group)

    rep = run_sentry_audit(
        base="mock://run1",
        sample_size=20,
        max_anomaly_rate=0.01,
    )
    assert rep.status == "PASSED"
    assert rep.total_galaxies_evaluated == 20
    assert rep.passed_count == 20
    assert rep.flagged_count == 0
    assert rep.pass_rate_pct == 100.0

