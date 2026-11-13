from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

pytestmark = pytest.mark.integration

from specsynth.agent import AgentInvestigationResult, RootCauseCluster, SentryAgent
from specsynth.cli import build_parser, cmd_sentry_agent


def test_agent_clean_catalog_certified_pristine(tmp_path, monkeypatch):
    mock_audit = {
        "status": "PASSED",
        "total_galaxies_evaluated": 1000,
        "passed_count": 1000,
        "flagged_count": 0,
        "pass_rate_pct": 100.0,
        "anomalies": [],
    }
    monkeypatch.setattr("specsynth.agent.tool_run_sentry_audit", lambda **kwargs: mock_audit)

    memo_file = tmp_path / "memo.md"
    json_file = tmp_path / "result.json"

    agent = SentryAgent(
        base=str(tmp_path),
        sample_size=1000,
        output_memo_path=str(memo_file),
    )
    res = agent.run()

    assert res.status == "CERTIFIED_PRISTINE"
    assert res.total_evaluated == 1000
    assert res.passed_count == 1000
    assert res.flagged_count == 0
    assert res.retention_rate_pct == 100.0
    assert len(res.clusters) == 0

    assert memo_file.exists()
    content = memo_file.read_text(encoding="utf-8")
    assert "CERTIFIED PRISTINE" in content
    assert "Scientific Readiness" in content

    # Test JSON serialization
    res.to_json(str(json_file))
    assert json_file.exists()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["status"] == "CERTIFIED_PRISTINE"


def test_agent_anomalies_auto_remediated(tmp_path, monkeypatch):
    mock_audit = {
        "status": "WARNING",
        "total_galaxies_evaluated": 100,
        "passed_count": 98,
        "flagged_count": 2,
        "pass_rate_pct": 98.0,
        "anomalies": [
            {
                "anomaly_id": "ANOM-01",
                "category": "INPUT_SCHEMA_FAULT",
                "metric_name": "tau_diffuse",
                "observed_value": -0.5,
                "galaxy_index": 10,
                "root_cause": "Negative dust optical depth",
                "remediation": "Apply non-negative clip",
            },
            {
                "anomaly_id": "ANOM-02",
                "category": "PHYSICAL_ANOMALY",
                "metric_name": "d4000_break",
                "observed_value": 0.65,
                "galaxy_index": 25,
                "root_cause": "Inverted break",
                "remediation": "Check SFH",
            },
        ],
    }
    monkeypatch.setattr("specsynth.agent.tool_run_sentry_audit", lambda **kwargs: mock_audit)

    mock_clean_res = {
        "total_galaxies": 100,
        "valid_galaxies": 98,
        "quarantined_count": 2,
        "retention_rate_pct": 98.0,
        "output_path": str(tmp_path / "clean.parquet"),
    }
    monkeypatch.setattr("specsynth.agent.tool_clean_catalog", lambda **kwargs: mock_clean_res)

    mock_inspect = {
        "galaxy_index": 10,
        "tau_diffuse": -0.5,
        "tau_birth": 0.2,
        "total_stellar_mass_msun": 1e10,
        "redshift": 1.5,
    }
    monkeypatch.setattr("specsynth.agent.tool_inspect_galaxy", lambda **kwargs: mock_inspect)

    memo_file = tmp_path / "memo.md"
    clean_file = tmp_path / "clean.parquet"

    agent = SentryAgent(
        base=str(tmp_path),
        sample_size=100,
        max_anomaly_rate=0.05,  # 5% allowed
        auto_remediate=True,
        clean_output_path=str(clean_file),
        output_memo_path=str(memo_file),
    )
    res = agent.run()

    assert res.status == "REMEDIATED_CLEAN"
    assert res.flagged_count == 2
    assert res.retention_rate_pct == 98.0
    assert len(res.clusters) == 2
    assert res.quarantined_indices == [10, 25]

    assert memo_file.exists()
    content = memo_file.read_text(encoding="utf-8")
    assert "REMEDIATED CLEAN" in content
    assert "Discovered Anomaly Clusters" in content or "Anomaly Clusters" in content
    assert "INPUT_SCHEMA_FAULT" in content


def test_agent_anomalies_without_auto_remediate(tmp_path, monkeypatch):
    mock_audit = {
        "status": "WARNING",
        "total_galaxies_evaluated": 50,
        "passed_count": 49,
        "flagged_count": 1,
        "pass_rate_pct": 98.0,
        "anomalies": [
            {
                "anomaly_id": "ANOM-01",
                "category": "NUMERICAL_FAULT",
                "metric_name": "finite_flux",
                "observed_value": np.nan,
                "galaxy_index": 7,
            }
        ],
    }
    monkeypatch.setattr("specsynth.agent.tool_run_sentry_audit", lambda **kwargs: mock_audit)

    agent = SentryAgent(
        base=str(tmp_path),
        sample_size=50,
        auto_remediate=False,
        output_memo_path=str(tmp_path / "memo.md"),
    )
    res = agent.run()

    assert res.status == "INVESTIGATION_FLAGGED"
    assert res.clean_catalog_path is None


def test_agent_anomalies_critical_rejected(tmp_path, monkeypatch):
    mock_audit = {
        "status": "CRITICAL_FAILURE",
        "total_galaxies_evaluated": 100,
        "passed_count": 50,
        "flagged_count": 50,
        "pass_rate_pct": 50.0,
        "anomalies": [
            {
                "anomaly_id": f"ANOM-{i}",
                "category": "NUMERICAL_FAULT",
                "metric_name": "finite_flux",
                "observed_value": np.nan,
                "galaxy_index": i,
            }
            for i in range(50)
        ],
    }
    monkeypatch.setattr("specsynth.agent.tool_run_sentry_audit", lambda **kwargs: mock_audit)
    monkeypatch.setattr("specsynth.agent.tool_clean_catalog", lambda **kwargs: {"retention_rate_pct": 50.0})

    agent = SentryAgent(
        base=str(tmp_path),
        sample_size=100,
        max_anomaly_rate=0.001,  # Strict threshold
        auto_remediate=True,
        output_memo_path=str(tmp_path / "memo.md"),
    )
    res = agent.run()

    assert res.status == "CRITICAL_REJECTED"


def test_agent_deduce_hypothesis_rules():
    agent = SentryAgent()

    # Input Schema Fault
    hyp, act = agent._deduce_hypothesis("INPUT_SCHEMA_FAULT", "tau_diffuse", {}, {})
    assert "negative dust" in hyp.lower()

    hyp2, act2 = agent._deduce_hypothesis("INPUT_SCHEMA_FAULT", "mass", {}, {})
    assert "schema contract" in hyp2.lower()

    # Numerical Faults
    hyp_fin, _ = agent._deduce_hypothesis("NUMERICAL_FAULT", "finite_flux", {}, {})
    assert "nan or inf" in hyp_fin.lower()

    hyp_eng, _ = agent._deduce_hypothesis("NUMERICAL_FAULT", "energy_conservation", {}, {})
    assert "1st law of thermodynamics" in hyp_eng.lower()

    # Physical Anomalies
    hyp_d4, _ = agent._deduce_hypothesis("PHYSICAL_ANOMALY", "d4000_break", {}, {})
    assert "inverted 4000" in hyp_d4.lower()

    hyp_uv, _ = agent._deduce_hypothesis("PHYSICAL_ANOMALY", "uv_slope_beta", {}, {})
    assert "uv continuum slope" in hyp_uv.lower()

    hyp_mag, _ = agent._deduce_hypothesis("PHYSICAL_ANOMALY", "ab_magnitude_range", {}, {})
    assert "survey limits" in hyp_mag.lower()

    # Population Drift
    hyp_pop, _ = agent._deduce_hypothesis("POPULATION_DRIFT", "color_dispersion", {}, {})
    assert "population collapse" in hyp_pop.lower()

    # Fallback
    fallback_anom = {"root_cause": "Custom root cause", "remediation": "Custom remediation"}
    hyp_fb, act_fb = agent._deduce_hypothesis("UNKNOWN_CAT", "custom_metric", {}, fallback_anom)
    assert hyp_fb == "Custom root cause"
    assert act_fb == "Custom remediation"


def test_cli_cmd_sentry_agent_dispatch(tmp_path, monkeypatch):
    mock_run = MagicMock(
        return_value=AgentInvestigationResult(
            timestamp="2026-11-13T00:00:00Z",
            base=str(tmp_path),
            status="CERTIFIED_PRISTINE",
            total_evaluated=100,
            passed_count=100,
            flagged_count=0,
            pass_rate_pct=100.0,
            retention_rate_pct=100.0,
            clusters=[
                RootCauseCluster(
                    category="TEST",
                    metric_name="test_metric",
                    count=1,
                    sample_galaxy_indices=[1],
                    observed_range=(1.0, 2.0),
                    primary_hypothesis="Hyp",
                    recommended_action="Act",
                )
            ],
            clean_catalog_path=str(tmp_path / "clean.parquet"),
            memo_path=str(tmp_path / "memo.md"),
        )
    )
    monkeypatch.setattr(SentryAgent, "run", mock_run)

    parser = build_parser()
    args = parser.parse_args([
        "--base", str(tmp_path),
        "sentry-agent",
        "--sample", "100",
        "--clean-output", str(tmp_path / "clean.parquet"),
        "--output-memo", str(tmp_path / "memo.md"),
    ])

    with patch("sys.exit") as mock_exit:
        cmd_sentry_agent(args, None)
        mock_exit.assert_called_once_with(0)
