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


def test_clean_catalog_npz(tmp_path):
    from specsynth.catalog import clean_catalog

    # Create dummy source table
    n_gal = 100
    src_npz = tmp_path / "raw_catalog.npz"
    clean_npz = tmp_path / "clean_catalog.npz"

    np.savez_compressed(
        src_npz,
        mstar=np.linspace(1e8, 1e11, n_gal),
        redshift=np.linspace(0.1, 3.0, n_gal),
        tau_v=np.full(n_gal, 0.5),
    )

    # Prune galaxies 10, 20, 30
    res = clean_catalog(
        source_table_path=src_npz,
        output_path=clean_npz,
        anomalous_indices=[10, 20, 30],
    )

    assert res["total_galaxies"] == 100
    assert res["valid_galaxies"] == 97
    assert res["quarantined_count"] == 3
    assert res["retention_rate_pct"] == 97.0
    assert os.path.exists(clean_npz)

    with np.load(clean_npz) as data:
        assert len(data["mstar"]) == 97
        assert len(data["redshift"]) == 97


def test_clean_catalog_from_sentry_report(tmp_path):
    from specsynth.catalog import clean_catalog

    # Create dummy sentry report JSON
    rep_json = tmp_path / "sentry_report.json"
    rep_content = {
        "anomalies": [
            {"anomaly_id": "ANOM-1", "galaxy_index": 5},
            {"anomaly_id": "ANOM-2", "galaxy_index": 15},
        ]
    }
    with open(rep_json, "w", encoding="utf-8") as f:
        json.dump(rep_content, f)

    src_csv = tmp_path / "raw_catalog.csv"
    clean_csv = tmp_path / "clean_catalog.csv"

    # Write dummy CSV
    with open(src_csv, "w", encoding="utf-8") as f:
        f.write("id,mass,z\n")
        for i in range(20):
            f.write(f"{i},{10.0 + i*0.1},{0.5 + i*0.05}\n")

    res = clean_catalog(
        source_table_path=src_csv,
        sentry_report_path=rep_json,
        output_path=clean_csv,
    )
    assert res["total_galaxies"] == 20
    assert res["valid_galaxies"] == 18
    assert res["quarantined_count"] == 2
    assert os.path.exists(clean_csv)


def test_tools_system_info_and_filters():
    from specsynth.tools import tool_get_system_info, tool_list_available_filters

    info = tool_get_system_info()
    assert "cpu_processor" in info
    assert "total_ram_gb" in info

    filt = tool_list_available_filters()
    assert "jwst_nircam" in filt["filter_sets"]
    assert "rubin" in filt["filter_sets"]
    assert filt["individual_filters_count"] > 10


def test_sentry_input_context_recorded():
    # Verify input_parameters field is correctly captured in AnomalyRecord
    anom = AnomalyRecord(
        anomaly_id="TEST-CTX",
        tier=2,
        category="PHYSICAL_ANOMALY",
        severity="WARNING",
        galaxy_index=123,
        metric_name="d4000_break",
        observed_value=0.72,
        expected_range=[0.95, 2.50],
        input_parameters={
            "total_stellar_mass_msun": 1e10,
            "young_stellar_fraction": 0.99,
            "tau_diffuse": 0.0,
            "tau_birth": 0.0,
        },
        root_cause="Zero dust in young burst",
    )
    assert anom.input_parameters["young_stellar_fraction"] == 0.99
    assert anom.input_parameters["tau_diffuse"] == 0.0


def test_run_sentry_audit_with_anomalies_and_attach_is_valid(monkeypatch, tmp_path):
    class MockStore(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {}
        def create_dataset(self, name, data, overwrite=True):
            self[name] = data

    wave = np.linspace(1000, 10000, 50)
    # 5 galaxies:
    # 0: valid
    # 1: NaN flux (NUMERICAL_FAULT)
    # 2: negative flux (NUMERICAL_FAULT)
    # 3: unphysical flat flux
    # 4: valid
    spec_data = np.ones((5, 50), dtype=np.float32) * 1e-18
    spec_data[1, 10] = np.nan
    spec_data[2, 10] = -1.0

    mock_ssp = MockStore({
        "wave": wave,
        "ages": np.array([1e6, 1e8, 1e10]),
        "mets": np.array([0.02]),
        "ssp": np.ones((3, 50), dtype=np.float32),
    })
    mock_gal = MockStore({
        "sfh": np.ones((5, 3), dtype=np.float32) * 1e9,
        "tau_diffuse": np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32),
        "tau_birth": np.array([0.5, 0.6, 0.7, 0.8, 0.9], dtype=np.float32),
        "params": np.array([[10.0, 1.0, 2.0, -1.9, 0.1, 0.5]] * 5, dtype=np.float32),
    })
    mock_out = MockStore({
        "spectra": spec_data,
        "wave": wave,
    })
    mock_out.attrs["redshift"] = 1.0

    def mock_open(store, mode="r"):
        if "ssp.zarr" in store: return mock_ssp
        if "galaxies.zarr" in store: return mock_gal
        return mock_out

    monkeypatch.setattr("zarr.open_group", mock_open)

    report = run_sentry_audit(
        base=str(tmp_path),
        sample_size=5,
        attach_is_valid=True,
    )

    assert report.status == "CRITICAL_FAILURE"
    assert report.flagged_count >= 2
    assert "is_valid" in mock_out
    assert mock_out["is_valid"][1] == False
    assert mock_out["is_valid"][2] == False
    assert mock_out["is_valid"][0] == True

    # Check input context captured on numerical fault
    anom_1 = next(a for a in report.anomalies if a.galaxy_index == 1)
    assert anom_1.input_parameters is not None
    assert "tau_diffuse" in anom_1.input_parameters
    assert np.isclose(anom_1.input_parameters["tau_diffuse"], 0.2, atol=1e-5)


def test_run_sentry_audit_photometry_magnitude_faults(monkeypatch, tmp_path):
    class MockStore(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {}

    phot_data = np.array([
        [20.0, 21.0, 22.0],  # Valid
        [5.0, 6.0, 7.0],     # Too bright (< min_mag=10)
        [38.0, 39.0, 40.0],  # Too faint (> max_mag=35)
    ], dtype=np.float32)

    mock_ssp = MockStore({
        "wave": np.linspace(1000, 10000, 10),
        "ages": np.array([1e7]),
        "mets": np.array([0.02]),
        "ssp": np.ones((1, 10), dtype=np.float32),
    })
    mock_gal = MockStore({
        "sfh": np.ones((3, 1), dtype=np.float32),
    })
    mock_out = MockStore({
        "photometry": phot_data,
    })

    def mock_open(store, mode="r"):
        if "ssp.zarr" in store: return mock_ssp
        if "galaxies.zarr" in store: return mock_gal
        return mock_out

    monkeypatch.setattr("zarr.open_group", mock_open)

    report = run_sentry_audit(
        base=str(tmp_path),
        sample_size=3,
        min_mag=10.0,
        max_mag=35.0,
    )
    assert report.status in ("WARNING", "CRITICAL_FAILURE")
    mag_anoms = [a for a in report.anomalies if a.metric_name == "ab_magnitude_range"]
    assert len(mag_anoms) == 2


def test_run_sentry_audit_quarantine_unknown_exception(monkeypatch, tmp_path):
    class MockStore(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {}

    def broken_getitem(self, key):
        if key == "spectra":
            raise RuntimeError("Corrupt block header in Zarr!")
        return super().__getitem__(key)

    mock_ssp = MockStore({
        "wave": np.linspace(1000, 10000, 10),
        "ages": np.array([1e7]),
        "mets": np.array([0.02]),
        "ssp": np.ones((1, 10), dtype=np.float32),
    })
    mock_gal = MockStore({
        "sfh": np.ones((2, 1), dtype=np.float32),
    })
    mock_out = MockStore()
    mock_out.__getitem__ = broken_getitem.__get__(mock_out)
    mock_out["wave"] = np.linspace(1000, 10000, 10)

    def mock_open(store, mode="r"):
        if "ssp.zarr" in store: return mock_ssp
        if "galaxies.zarr" in store: return mock_gal
        return mock_out

    monkeypatch.setattr("zarr.open_group", mock_open)

    q_dir = str(tmp_path / "custom_quarantine")
    report = run_sentry_audit(
        base=str(tmp_path),
        sample_size=2,
        quarantine_dir=q_dir,
    )

    assert report.status == "CRITICAL_FAILURE"
    assert len(report.quarantined_files) == 1
    assert os.path.exists(report.quarantined_files[0])
    unk = [a for a in report.anomalies if a.category == "UNKNOWN_EXCEPTION"]
    assert len(unk) == 1


def test_sentry_report_to_markdown_truncation(tmp_path):
    # Test > 25 anomalies produces truncation notice in markdown report
    anoms = [
        AnomalyRecord(
            anomaly_id=f"ANOM-{i}",
            tier=2,
            category="PHYSICAL_ANOMALY",
            severity="WARNING",
            galaxy_index=i,
            metric_name="d4000_break",
            observed_value=0.5,
            expected_range=[0.9, 2.5],
            root_cause="Test anomaly",
        )
        for i in range(30)
    ]
    report = SentryReport(
        timestamp="2026-11-13T00:00:00Z",
        provenance="Test",
        total_galaxies_evaluated=100,
        passed_count=70,
        flagged_count=30,
        pass_rate_pct=70.0,
        status="WARNING",
        anomalies=anoms,
    )
    md_file = tmp_path / "long_report.md"
    report.to_markdown(str(md_file))

    content = md_file.read_text(encoding="utf-8")
    assert "and 5 more anomalies logged" in content


def test_run_sentry_audit_input_schema_fault(monkeypatch, tmp_path):
    class MockStore(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {}

    wave = np.linspace(1000, 10000, 20)
    mock_ssp = MockStore({
        "wave": wave,
        "ages": np.array([1e7]),
        "mets": np.array([0.02]),
        "ssp": np.ones((1, 20), dtype=np.float32),
    })
    # Negative tau_diffuse and negative tau_birth
    mock_gal = MockStore({
        "sfh": np.ones((2, 1), dtype=np.float32),
        "tau_diffuse": np.array([-0.5, 0.2], dtype=np.float32),
        "tau_birth": np.array([0.5, -0.8], dtype=np.float32),
        "params": np.zeros((2, 6), dtype=np.float32),
    })
    mock_out = MockStore({
        "spectra": np.ones((2, 20), dtype=np.float32) * 1e-15,
        "wave": wave,
    })

    def mock_open(store, mode="r"):
        if "ssp.zarr" in store: return mock_ssp
        if "galaxies.zarr" in store: return mock_gal
        return mock_out

    monkeypatch.setattr("zarr.open_group", mock_open)

    report = run_sentry_audit(base=str(tmp_path), sample_size=2)
    assert report.category_summary["INPUT_SCHEMA_FAULT"] >= 2
    assert report.status == "CRITICAL_FAILURE"
    sch_anoms = [a for a in report.anomalies if a.category == "INPUT_SCHEMA_FAULT"]
    assert len(sch_anoms) >= 2


def test_run_sentry_audit_tier3_population_collapse(monkeypatch, tmp_path):
    class MockStore(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {}

    wave = np.linspace(1000, 10000, 10)
    mock_ssp = MockStore({
        "wave": wave,
        "ages": np.array([1e7]),
        "mets": np.array([0.02]),
        "ssp": np.ones((1, 10), dtype=np.float32),
    })
    n_gal = 30
    mock_gal = MockStore({
        "sfh": np.ones((n_gal, 1), dtype=np.float32),
    })
    # Collapsed degenerate colors across 30 galaxies (all identical)
    phot = np.ones((n_gal, 2), dtype=np.float32) * 20.0
    mock_out = MockStore({
        "photometry": phot,
    })

    def mock_open(store, mode="r"):
        if "ssp.zarr" in store: return mock_ssp
        if "galaxies.zarr" in store: return mock_gal
        return mock_out

    monkeypatch.setattr("zarr.open_group", mock_open)

    report = run_sentry_audit(base=str(tmp_path), sample_size=n_gal)
    assert report.tier_summary["tier3_population"] >= 1
    pop_anom = next((a for a in report.anomalies if a.category == "POPULATION_DRIFT"), None)
    assert pop_anom is not None
    assert pop_anom.metric_name == "population_color_dispersion"



