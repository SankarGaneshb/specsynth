from __future__ import annotations

import argparse
import sys
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from specsynth.cli import (
    build_parser,
    cmd_benchmark,
    cmd_clean_catalog,
    cmd_import_catalog,
    cmd_make_sfh,
    cmd_make_ssp,
    cmd_sentry,
    cmd_synth,
    cmd_verify,
    main,
)
from specsynth.sentry import AnomalyRecord, SentryReport


def test_build_parser_subcommands():
    ap = build_parser()
    assert isinstance(ap, argparse.ArgumentParser)
    
    sub_actions = [action for action in ap._actions if isinstance(action, argparse._SubParsersAction)]
    assert len(sub_actions) == 1
    choices = sub_actions[0].choices
    
    assert "make-ssp" in choices
    assert "make-sfh" in choices
    assert "import-catalog" in choices
    assert "benchmark" in choices
    assert "synth" in choices
    assert "verify" in choices
    assert "sentry" in choices
    assert "clean-catalog" in choices


def test_cli_parser_defaults():
    ap = build_parser()
    
    args_sentry = ap.parse_args(["sentry"])
    assert args_sentry.sample == 50_000
    assert args_sentry.min_mag == 10.0
    assert args_sentry.max_mag == 35.0
    assert args_sentry.max_anomaly_rate == 0.001
    assert args_sentry.output == "sentry_report.json"
    assert args_sentry.fn == cmd_sentry

    args_clean = ap.parse_args(["clean-catalog"])
    assert args_clean.report == "sentry_report.json"
    assert args_clean.output == "clean_catalog.parquet"
    assert args_clean.fn == cmd_clean_catalog

    args_synth = ap.parse_args(["synth", "--sentry", "--fail-on-anomaly", "--filters", "jwst_nircam"])
    assert args_synth.sentry is True
    assert args_synth.fail_on_anomaly is True
    assert args_synth.filters == "jwst_nircam"


def test_cli_cmd_make_ssp_toy(monkeypatch):
    mock_write_many = MagicMock()
    monkeypatch.setattr("specsynth.cli.write_many", mock_write_many)

    ap = build_parser()
    args = ap.parse_args([
        "make-ssp",
        "--adapter", "toy",
        "--n-age", "5",
        "--n-met", "2",
        "--n-wave", "20",
        "--resample-wave", "2000", "5000", "30",
    ])
    mock_client = MagicMock()
    args.fn(args, mock_client)
    mock_write_many.assert_called_once()


def test_cli_cmd_make_ssp_validation_errors():
    ap = build_parser()

    # bc03 missing --input-path
    args_bc03 = ap.parse_args(["make-ssp", "--adapter", "bc03"])
    with pytest.raises(ValueError, match="--input-path is required for the bc03 adapter"):
        args_bc03.fn(args_bc03, MagicMock())

    # emiles missing --input-path
    args_emiles = ap.parse_args(["make-ssp", "--adapter", "emiles"])
    with pytest.raises(ValueError, match="--input-path is required for the emiles adapter"):
        args_emiles.fn(args_emiles, MagicMock())

    # fits missing --input-file
    args_fits = ap.parse_args(["make-ssp", "--adapter", "fits"])
    with pytest.raises(ValueError, match="--input-file is required for the fits adapter"):
        args_fits.fn(args_fits, MagicMock())


def test_cli_cmd_make_sfh(monkeypatch):
    monkeypatch.setattr("specsynth.cli.read_small", lambda s, c: np.array([1.0, 2.0]))
    mock_write_many = MagicMock()
    monkeypatch.setattr("specsynth.cli.write_many", mock_write_many)

    ap = build_parser()
    args = ap.parse_args(["make-sfh", "--n-gal", "100", "--chunk", "50"])
    mock_client = MagicMock()
    args.fn(args, mock_client)
    mock_write_many.assert_called_once()

    # Test auto-tuning chunk size when n_tasks > 25000
    args_large = ap.parse_args(["make-sfh", "--n-gal", "30000", "--chunk", "1"])
    args_large.fn(args_large, mock_client)
    assert args_large.chunk > 1


def test_cli_cmd_synth_full(monkeypatch):
    import dask.array as da

    # Mock inputs
    ages = np.array([1e6, 5e9])
    mets = np.array([0.02])
    wave = np.linspace(1000, 10000, 20)
    def mock_read_small(store, comp):
        if comp == "ages": return ages
        if comp == "mets": return mets
        if comp == "wave": return wave
        raise ValueError(comp)

    monkeypatch.setattr("specsynth.cli.read_small", mock_read_small)
    monkeypatch.setattr("specsynth.cli.wait", MagicMock())

    ssp_da = da.ones((2, 20), chunks=(2, 20), dtype=np.float32)
    sfh_da = da.ones((10, 2), chunks=(5, 2), dtype=np.float32)
    tau_da = da.zeros(10, chunks=(5,), dtype=np.float32)

    def mock_from_zarr(store, component=None):
        if component == "ssp": return ssp_da
        if component == "sfh": return sfh_da
        if component in ("tau_diffuse", "tau_birth"): return tau_da
        raise ValueError(component)

    monkeypatch.setattr("dask.array.from_zarr", mock_from_zarr)
    monkeypatch.setattr("specsynth.cli.write_many", MagicMock())

    class MockGroup:
        def __init__(self):
            self.attrs = {}

    monkeypatch.setattr("zarr.open_group", lambda *args, **kwargs: MockGroup())

    mock_client = MagicMock()
    mock_client.persist = lambda x: x
    mock_client.scheduler_info.return_value = {"workers": {"worker1": {}}}

    ap = build_parser()
    # Test with filters, redshift, igm, and sentry
    args = ap.parse_args([
        "synth",
        "--filters", "jwst_nircam",
        "--redshift", "1.5",
        "--igm",
        "--sentry",
    ])

    mock_report = SentryReport(
        timestamp="2026-11-13T00:00:00Z",
        provenance="Test",
        total_galaxies_evaluated=10,
        passed_count=10,
        flagged_count=0,
        pass_rate_pct=100.0,
        status="PASSED",
    )
    monkeypatch.setattr("specsynth.sentry.run_sentry_audit", MagicMock(return_value=mock_report))

    args.fn(args, mock_client)


def test_cli_cmd_synth_fail_on_anomaly(monkeypatch):
    import dask.array as da
    ages, mets, wave = np.array([1e6]), np.array([0.02]), np.linspace(1000, 10000, 10)
    monkeypatch.setattr("specsynth.cli.read_small", lambda s, c: ages if c=="ages" else (mets if c=="mets" else wave))
    monkeypatch.setattr("specsynth.cli.wait", MagicMock())

    ssp_da = da.ones((1, 10), chunks=(1, 10), dtype=np.float32)
    sfh_da = da.ones((5, 1), chunks=(5, 1), dtype=np.float32)
    tau_da = da.zeros(5, chunks=(5,), dtype=np.float32)

    def mock_from_zarr(store, component=None):
        if component == "ssp": return ssp_da
        if component == "sfh": return sfh_da
        return tau_da

    monkeypatch.setattr("dask.array.from_zarr", mock_from_zarr)
    monkeypatch.setattr("specsynth.cli.write_many", MagicMock())
    monkeypatch.setattr("zarr.open_group", lambda *a, **kw: MagicMock())

    mock_client = MagicMock()
    mock_client.persist = lambda x: x
    mock_client.scheduler_info.return_value = {"workers": {}}

    mock_fail_report = SentryReport(
        timestamp="2026-11-13T00:00:00Z",
        provenance="Test",
        total_galaxies_evaluated=5,
        passed_count=0,
        flagged_count=5,
        pass_rate_pct=0.0,
        status="CRITICAL_FAILURE",
    )
    monkeypatch.setattr("specsynth.sentry.run_sentry_audit", MagicMock(return_value=mock_fail_report))

    ap = build_parser()
    args = ap.parse_args(["synth", "--sentry", "--fail-on-anomaly"])

    with pytest.raises(RuntimeError, match="Sentry audit detected critical anomalies"):
        args.fn(args, mock_client)


def test_cli_cmd_verify(monkeypatch):
    ages = np.array([1e6, 5e9])
    mets = np.array([0.02])
    wave = np.linspace(1000, 10000, 20)
    ssp = np.ones((2, 20), dtype=np.float64)

    def mock_read_small(store, comp):
        if comp == "ages": return ages
        if comp == "mets": return mets
        if comp == "wave": return wave
        if comp == "ssp": return ssp
        raise ValueError(comp)

    monkeypatch.setattr("specsynth.cli.read_small", mock_read_small)

    class MockZarr:
        def __init__(self, data):
            self.data = data
            self.attrs = {}
        def __getitem__(self, k):
            return self.data[k]
        def __contains__(self, k):
            return k in self.data

    mock_in = MockZarr({
        "sfh": np.ones((5, 2), dtype=np.float32),
        "tau_diffuse": np.zeros(5, dtype=np.float32),
        "tau_birth": np.zeros(5, dtype=np.float32),
    })

    # Exact match output
    ny = 1
    kd = (wave / 5500.0) ** -0.7
    kb = (wave / 5500.0) ** -1.3
    ref = np.exp(-0.0 * kd) * (
        mock_in["sfh"][:, ny:] @ ssp[ny:] + np.exp(-0.0 * kb) * (mock_in["sfh"][:, :ny] @ ssp[:ny])
    ).astype(np.float32)

    mock_out = MockZarr({"spectra": ref})

    def mock_open(store, mode="r"):
        if "galaxies.zarr" in store: return mock_in
        return mock_out

    monkeypatch.setattr("zarr.open_group", mock_open)

    ap = build_parser()
    args = ap.parse_args(["verify", "--sample", "5"])

    with pytest.raises(SystemExit) as exc:
        args.fn(args, MagicMock())
    assert exc.value.code == 0


def test_cli_cmd_import_catalog(monkeypatch):
    mock_import = MagicMock(return_value={
        "n_galaxies": 100,
        "ssp_grid_k": 20,
    })
    monkeypatch.setattr("specsynth.catalog.import_catalog", mock_import)

    ap = build_parser()
    args = ap.parse_args([
        "import-catalog",
        "--input-file", "test.fits",
        "--mass-col", "M_STAR",
        "--age-col", "T_ONSET",
        "--tau-col", "TAU",
        "--met-col", "MET",
        "--dust-diffuse-col", "TAU_D",
        "--dust-birth-col", "TAU_B",
        "--redshift-col", "Z",
    ])
    args.fn(args, None)
    mock_import.assert_called_once()


def test_cli_cmd_benchmark_dispatch(monkeypatch):
    mock_run_suite = MagicMock(return_value={"cpu_performance": {"throughput_galaxies_per_sec": 1000}})
    monkeypatch.setattr("specsynth.benchmark.run_benchmark_suite", mock_run_suite)
    monkeypatch.setattr("specsynth.benchmark.print_benchmark_summary", MagicMock())
    
    ap = build_parser()
    args = ap.parse_args(["benchmark", "--n-gal", "100", "--n-runs", "1", "--n-warmup", "1"])
    
    args.fn(args, None)
    mock_run_suite.assert_called_once()


def test_cli_cmd_sentry_dispatch(monkeypatch, tmp_path):
    anom = AnomalyRecord(
        anomaly_id="ANOM-1",
        tier=3,
        category="PHYSICAL_ANOMALY",
        severity="CRITICAL",
        galaxy_index=1,
        metric_name="mag_r",
        observed_value=40.0,
        expected_range=[10.0, 35.0],
        root_cause="Unrealistically faint galaxy",
        input_parameters={},
    )
    mock_report = SentryReport(
        timestamp="2026-11-13T00:00:00Z",
        provenance="Test",
        total_galaxies_evaluated=10,
        passed_count=9,
        flagged_count=1,
        pass_rate_pct=90.0,
        status="WARNING",
        anomalies=[anom],
    )
    monkeypatch.setattr("specsynth.sentry.run_sentry_audit", MagicMock(return_value=mock_report))
    
    md_file = str(tmp_path / "sentry.md")
    ap = build_parser()
    args = ap.parse_args(["--base", "./mock_run", "sentry", "--sample", "10", "-m", md_file])
    
    # Test exiting with code 1 on WARNING
    with pytest.raises(SystemExit) as exc:
        args.fn(args, None)
    assert exc.value.code == 1

    # Test CRITICAL_FAILURE -> sys.exit(2)
    mock_report.status = "CRITICAL_FAILURE"
    with pytest.raises(SystemExit) as exc_crit:
        args.fn(args, None)
    assert exc_crit.value.code == 2


def test_cli_cmd_clean_catalog_dispatch(monkeypatch):
    mock_clean = MagicMock(return_value={
        "total_galaxies": 100,
        "valid_galaxies": 95,
        "quarantined_count": 5,
        "retention_rate_pct": 95.0,
        "output_path": "clean.parquet",
    })
    monkeypatch.setattr("specsynth.catalog.clean_catalog", mock_clean)
    
    ap = build_parser()
    args = ap.parse_args(["--base", "./mock_run", "clean-catalog", "--output", "clean.parquet"])
    args.fn(args, None)
    mock_clean.assert_called_once()


def test_cli_main_bypass_for_local_commands(monkeypatch):
    mock_fn = MagicMock()
    monkeypatch.setattr(sys, "argv", ["specsynth", "sentry"])
    monkeypatch.setattr("specsynth.cli.cmd_sentry", mock_fn)
    
    main()
    mock_fn.assert_called_once()


def test_cli_main_with_scheduler(monkeypatch):
    mock_client = MagicMock()
    mock_client.scheduler_info.return_value = {"workers": {"w1": {}}}
    mock_client_cls = MagicMock(return_value=mock_client)
    monkeypatch.setattr("specsynth.cli.Client", mock_client_cls)

    mock_fn = MagicMock()
    monkeypatch.setattr("specsynth.cli.cmd_make_sfh", mock_fn)
    monkeypatch.setattr(sys, "argv", ["specsynth", "--scheduler", "tcp://mock:8786", "make-sfh", "--n-gal", "10"])

    main()
    mock_fn.assert_called_once()
    mock_client.close.assert_called_once()
