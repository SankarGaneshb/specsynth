from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from specsynth.sentry import AnomalyRecord, SentryReport
from specsynth.tools import (
    tool_clean_catalog,
    tool_get_anomaly_details,
    tool_get_system_info,
    tool_inspect_anomaly,
    tool_inspect_galaxy,
    tool_list_available_filters,
    tool_run_sentry_audit,
)


def test_tool_get_system_info():
    info = tool_get_system_info()
    assert isinstance(info, dict)
    assert "cpu_arch" in info
    assert "cpu_count_logical" in info
    assert "total_ram_gb" in info


def test_tool_list_available_filters():
    res = tool_list_available_filters()
    assert "filter_sets" in res
    assert "individual_filters_count" in res
    assert "available_filters" in res
    assert "jwst_nircam" in res["filter_sets"]
    assert res["individual_filters_count"] > 0


def test_tool_inspect_anomaly_missing_file(tmp_path):
    res = tool_inspect_anomaly(base=str(tmp_path), anomaly_id="ANOM-123")
    assert "error" in res


def test_tool_inspect_anomaly_found_and_not_found(tmp_path):
    report_file = tmp_path / "sentry_report.json"
    data = {
        "anomalies": [
            {
                "anomaly_id": "ANOM-D4K-00042",
                "galaxy_index": 42,
                "metric_name": "D4000_break",
                "observed_value": 0.5,
                "expected_range": [0.8, 3.0],
            }
        ]
    }
    report_file.write_text(json.dumps(data), encoding="utf-8")

    # Match exact or substring
    found = tool_inspect_anomaly(report_path=str(report_file), anomaly_id="ANOM-D4K-00042")
    assert found["found"] is True
    assert found["anomaly"]["galaxy_index"] == 42

    # Substring match
    found_sub = tool_get_anomaly_details(report_path=str(report_file), anomaly_id="00042")
    assert found_sub["found"] is True

    # Not found
    not_found = tool_inspect_anomaly(report_path=str(report_file), anomaly_id="UNKNOWN")
    assert not_found["found"] is False


def test_tool_run_sentry_audit(tmp_path, monkeypatch):
    mock_rep = SentryReport(
        timestamp="2026-11-13T00:00:00Z",
        provenance="Test",
        total_galaxies_evaluated=10,
        passed_count=10,
        flagged_count=0,
        pass_rate_pct=100.0,
        status="PASSED",
    )
    monkeypatch.setattr("specsynth.tools.run_sentry_audit", MagicMock(return_value=mock_rep))

    json_out = str(tmp_path / "audit.json")
    md_out = str(tmp_path / "audit.md")

    res = tool_run_sentry_audit(
        base=str(tmp_path),
        sample_size=100,
        output_json=json_out,
        output_markdown=md_out,
    )
    assert res["status"] == "PASSED"
    assert Path(json_out).exists()
    assert Path(md_out).exists()


def test_tool_clean_catalog(monkeypatch):
    mock_clean = MagicMock(return_value={"retention_rate_pct": 99.0})
    monkeypatch.setattr("specsynth.tools.clean_catalog", mock_clean)

    res = tool_clean_catalog(base="./mock_base", output_path="out.parquet")
    assert res["retention_rate_pct"] == 99.0
    mock_clean.assert_called_once()


def test_tool_inspect_galaxy(tmp_path, monkeypatch):
    # Setup mock zarr group structures
    mock_in = {
        "tau_diffuse": np.array([0.3, 0.5]),
        "tau_birth": np.array([0.8, 1.2]),
        "redshift": np.array([1.5, 2.0]),
        "sfh": np.array([[100.0, 200.0], [50.0, 75.0]]),
        "params": np.array([[10.5, 0.5, 1.2, 0.02, 0.3, 0.8], [9.8, 1.0, 2.0, 0.01, 0.1, 0.5]]),
    }
    mock_out = {
        "spectra": np.array([[1e-18, 5e-18], [2e-18, 8e-18]])
    }

    def mock_open_group(store, mode="r"):
        if "galaxies.zarr" in store:
            return mock_in
        elif "spectra.zarr" in store:
            return mock_out
        raise ValueError(f"Unknown store {store}")

    monkeypatch.setattr("zarr.open_group", mock_open_group)

    details = tool_inspect_galaxy(base=str(tmp_path), galaxy_idx=0)
    assert details["galaxy_index"] == 0
    assert details["tau_diffuse"] == 0.3
    assert details["tau_birth"] == 0.8
    assert details["redshift"] == 1.5
    assert details["total_stellar_mass_msun"] == 300.0
    assert details["log_stellar_mass"] == 10.5
    assert details["output_type"] == "spectra"
    assert details["min_spectral_flux"] == 1e-18
    assert details["max_spectral_flux"] == 5e-18


def test_tool_inspect_galaxy_photometry(tmp_path, monkeypatch):
    mock_in = {}
    mock_phot = {
        "photometry": np.array([[22.5, 21.8, 20.9]])
    }

    def mock_open_group(store, mode="r"):
        if "galaxies.zarr" in store:
            return mock_in
        elif "spectra.zarr" in store:
            raise FileNotFoundError("no spectra")
        elif "photometry.zarr" in store:
            return mock_phot
        raise ValueError(f"Unknown store {store}")

    monkeypatch.setattr("zarr.open_group", mock_open_group)

    details = tool_inspect_galaxy(base=str(tmp_path), galaxy_idx=0)
    assert details["output_type"] == "photometry"
    assert len(details["photometry_magnitudes"]) == 3
    assert details["photometry_magnitudes"][0] == 22.5


def test_tool_inspect_galaxy_photometry_in_spectra_zarr(tmp_path, monkeypatch):
    mock_in = {}
    class MockSpectraGroup(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attrs = {"filters": ["F090W", "F115W", "F150W"]}

    mock_out = MockSpectraGroup({
        "photometry": np.array([[1.2e-5, 3.4e-5, 5.6e-5]])
    })

    def mock_open_group(store, mode="r"):
        if "galaxies.zarr" in store:
            return mock_in
        elif "spectra.zarr" in store:
            return mock_out
        raise ValueError(f"Unknown store {store}")

    monkeypatch.setattr("zarr.open_group", mock_open_group)

    details = tool_inspect_galaxy(base=str(tmp_path), galaxy_idx=0)
    assert details["output_type"] == "photometry"
    assert len(details["photometry_values"]) == 3
    assert details["filter_names"] == ["F090W", "F115W", "F150W"]


def test_tool_inspect_galaxy_not_found(tmp_path, monkeypatch):
    mock_in = {}

    def mock_open_group(store, mode="r"):
        if "galaxies.zarr" in store:
            return mock_in
        raise FileNotFoundError("not found")

    monkeypatch.setattr("zarr.open_group", mock_open_group)

    details = tool_inspect_galaxy(base=str(tmp_path), galaxy_idx=0)
    assert details["output_type"] == "not_found"
