"""
Automated Test Suite for Frozen P0 Baseline Architecture Verification (Issue #29 / P6).
========================================================================================
Validates:
1. Fixed immutable baseline SHA and Git tag resolution.
2. Current repository conformance to the frozen P0 architecture baseline.
3. Negative test: detection of unauthorized core modifications with feature reporting.
4. Negative test: fail-closed handling and actionable remediation on unreachable baseline.
5. Isolation of external adapter plugin code outside the core framework.
6. JSON serialization of machine-readable verification evidence report.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from specsynth.governance import (
    P0_BASELINE_SHA,
    P0_BASELINE_TAG,
    ROADMAP_CORE_ALLOWLIST,
    BaselineVerificationResult,
    ShallowHistoryError,
    verify_frozen_baseline,
)
from specsynth.governance.baseline_verifier import resolve_commit_sha

pytestmark = pytest.mark.critical


def test_baseline_sha_is_fixed_and_resolvable():
    """Verify the P0 baseline SHA is immutable, 40-chars, and resolvable in git history."""
    assert len(P0_BASELINE_SHA) == 40
    assert P0_BASELINE_SHA == "8e36648d7bad3959cdd8ed32c0232f0370fec461"

    repo_root = Path(__file__).resolve().parents[1]
    resolved = resolve_commit_sha(repo_root, P0_BASELINE_SHA)
    assert resolved == P0_BASELINE_SHA, f"Could not resolve P0 baseline SHA: {P0_BASELINE_SHA}"

    # Also verify tag resolution
    tag_resolved = resolve_commit_sha(repo_root, P0_BASELINE_TAG)
    assert tag_resolved == P0_BASELINE_SHA, f"Tag {P0_BASELINE_TAG} did not resolve to {P0_BASELINE_SHA}"


def test_current_repository_conforms_to_baseline():
    """Verify that current repository state is fully conformant to the P0 baseline."""
    repo_root = Path(__file__).resolve().parents[1]
    res = verify_frozen_baseline(repo_path=repo_root)

    assert res.status == "CONFORMANT"
    assert res.passed is True
    assert len(res.unauthorized_core_files) == 0
    assert len(res.modified_core_files) > 0
    assert len(res.external_plugin_files) > 0

    # Ensure every modified core file is tracked under an authorized milestone
    for item in res.modified_core_files:
        assert item["milestone"] in ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P0-P6", "P0,#15", "P0,#16", "P0,#18")
        assert "feature" in item


def test_negative_unauthorized_core_modification_detection():
    """
    Negative test: When an unallowlisted core modification is encountered,
    the verifier detects it, cataloges feature subsystem info, and records DRIFT_DETECTED.
    """
    repo_root = Path(__file__).resolve().parents[1]

    # Create restricted allowlist that intentionally excludes specsynth/core.py
    restricted_allowlist = {k: v for k, v in ROADMAP_CORE_ALLOWLIST.items() if k != "specsynth/core.py"}

    res = verify_frozen_baseline(repo_path=repo_root, allowlist=restricted_allowlist, strict=False)

    assert res.status == "DRIFT_DETECTED"
    assert res.passed is True  # Non-strict mode records drift without aborting per user instruction
    unauthorized_paths = [f["file_path"] for f in res.unauthorized_core_files]
    assert "specsynth/core.py" in unauthorized_paths

    # Verify diagnostic info is recorded
    core_entry = next(f for f in res.unauthorized_core_files if f["file_path"] == "specsynth/core.py")
    assert core_entry["milestone"] == "UNCLASSIFIED_DISCREPANCY"
    assert core_entry["issue"] == "UNAUTHORIZED"

    # Under strict mode, passed must be False
    res_strict = verify_frozen_baseline(repo_path=repo_root, allowlist=restricted_allowlist, strict=True)
    assert res_strict.passed is False


def test_negative_shallow_history_failure():
    """
    Negative test: An unresolvable baseline SHA (e.g. shallow clone)
    triggers a hard fail-closed response with actionable git remediation.
    """
    repo_root = Path(__file__).resolve().parents[1]
    fake_sha = "0000000000000000000000000000000000000000"

    res = verify_frozen_baseline(repo_path=repo_root, baseline_sha=fake_sha, strict=False)

    assert res.status == "SHALLOW_HISTORY_ERROR"
    assert res.passed is False
    assert "git fetch origin" in res.diagnostic_summary or "unshallow" in res.diagnostic_summary

    # Strict mode raises ShallowHistoryError
    with pytest.raises(ShallowHistoryError, match="not found in local git history"):
        verify_frozen_baseline(repo_path=repo_root, baseline_sha=fake_sha, strict=True)


def test_external_plugin_isolation():
    """Verify all external plugin files in examples/ are isolated from core."""
    repo_root = Path(__file__).resolve().parents[1]
    res = verify_frozen_baseline(repo_path=repo_root)

    # Ensure external adapter files are identified in external_plugin_files
    expected_plugin_files = [
        "examples/external_engine_plugin/fsps_external_adapter.py",
        "examples/external_engine_plugin/pyproject.toml",
        "examples/external_engine_plugin/run_genuine_external_workflow.py",
    ]
    for ep in expected_plugin_files:
        assert ep in res.external_plugin_files, f"Expected {ep} in external_plugin_files"


def test_report_json_serialization():
    """Verify verification report payload serializes cleanly to JSON."""
    repo_root = Path(__file__).resolve().parents[1]
    res = verify_frozen_baseline(repo_path=repo_root)

    report_dict = res.to_dict()
    json_str = json.dumps(report_dict, indent=2)
    reloaded = json.loads(json_str)

    assert reloaded["baseline_sha"] == P0_BASELINE_SHA
    assert reloaded["status"] == "CONFORMANT"
    assert isinstance(reloaded["modified_core_files"], list)
    assert isinstance(reloaded["external_plugin_files"], list)
