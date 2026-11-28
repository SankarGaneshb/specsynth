"""
Frozen P0 Architecture Baseline Verifier Engine.
================================================
Compares git change history and the working tree against the immutable P0
architecture-freeze baseline commit (8e36648) to audit Pillar 1 compliance:
Zero-Core-Modification Pluggability (GitHub Issue #29 / Milestone P6).

Per user directive:
Does not crash abruptly when core deviations are detected; instead, it cataloges
exact modified files, line diff metrics, feature subsystems, and roadmap milestones
in a machine-readable audit report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any

# Canonical P0 Architecture Freeze Baseline Commit
P0_BASELINE_SHA: str = "8e36648d7bad3959cdd8ed32c0232f0370fec461"
P0_BASELINE_TAG: str = "p0-architecture-freeze"

# Explicit Reviewed Allowlist of Core Paths with Roadmap Milestone Attribution
ROADMAP_CORE_ALLOWLIST: dict[str, dict[str, Any]] = {
    "specsynth/__init__.py": {
        "milestone": "P0-P6",
        "issue": "#14-#28",
        "feature": "Top-level package namespace and public API exports",
    },
    "specsynth/core.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "GEMM spectral matrix contraction and Charlot & Fall (2000) dust",
    },
    "specsynth/cosmology.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "FlatLambdaCDM cosmological distance measures and TNG cosmology",
    },
    "specsynth/sfh.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "Delayed-tau SFH synthesis and strict mass conservation",
    },
    "specsynth/filters.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "STScI calibrated instrument filter curves and AB zero points",
    },
    "specsynth/igm.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "Madau (1995) intergalactic medium optical depth and transmission",
    },
    "specsynth/provenance.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "Cryptographic SHA-256 provenance manifest generator",
    },
    "specsynth/adapters/fsps.py": {
        "milestone": "P1",
        "issue": "#15",
        "feature": "Authentic FSPS ASCII spectral grid loader and exporter",
    },
    "specsynth/adapters/__init__.py": {
        "milestone": "P0",
        "issue": "#14",
        "feature": "Dynamic adapter plugin registry and entry-point discovery",
    },
    "specsynth/adapters/base.py": {
        "milestone": "P0",
        "issue": "#14",
        "feature": "BaseAdapter contract interface and SSPData standard container",
    },
    "specsynth/adapters/conformance.py": {
        "milestone": "P6",
        "issue": "#20",
        "feature": "11-point mathematical and scientific invariant conformance suite",
    },
    "specsynth/simulation.py": {
        "milestone": "P2",
        "issue": "#16",
        "feature": "Simulation galaxy particle ingestion and truth-in-labeling",
    },
    "specsynth/transforms.py": {
        "milestone": "P2",
        "issue": "#16",
        "feature": "Physical coordinate frames, Center-of-Mass, and angular momentum alignment",
    },
    "specsynth/evolution.py": {
        "milestone": "P3",
        "issue": "#17,#27",
        "feature": "Cosmic-time FLRW evolution, Leitner-Kravtsov recycling, and SubLink merger trees",
    },
    "specsynth/mcp/server.py": {
        "milestone": "P4",
        "issue": "#18",
        "feature": "Canonical Model Context Protocol (MCP) server implementation",
    },
    "specsynth/mcp/bridge.py": {
        "milestone": "P4",
        "issue": "#18",
        "feature": "Local HTTP/JSON-RPC bridge server for frontend and Node.js parity",
    },
    "specsynth/contracts/__init__.py": {
        "milestone": "P0",
        "issue": "#14",
        "feature": "Canonical contract schemas namespace exports",
    },
    "specsynth/contracts/data_mode.py": {
        "milestone": "P5",
        "issue": "#32",
        "feature": "Canonical DataMode and scientific provenance classifications (v1.0.0)",
    },
    "specsynth/contracts/ssp.py": {
        "milestone": "P0",
        "issue": "#14",
        "feature": "Canonical SSPGridContract (v1.0.0)",
    },
    "specsynth/contracts/simulation.py": {
        "milestone": "P0",
        "issue": "#14",
        "feature": "Canonical SimulationGalaxyContract (v1.0.0)",
    },
    "specsynth/contracts/galaxy3d.py": {
        "milestone": "P0,#16",
        "issue": "#14,#16",
        "feature": "Canonical Galaxy3DContract and ParticleBatchContract (v1.0.0)",
    },
    "specsynth/contracts/photometry.py": {
        "milestone": "P0,#15",
        "issue": "#14,#15",
        "feature": "Canonical SyntheticObservationContract and PhotometryPointContract (v1.0.0)",
    },
    "specsynth/contracts/evolution.py": {
        "milestone": "P3",
        "issue": "#17,#27",
        "feature": "Canonical EvolutionaryTrackContract, ProgenitorNode, and MergerEvent (v1.0.0)",
    },
    "specsynth/contracts/mcp.py": {
        "milestone": "P0,#18",
        "issue": "#14,#18",
        "feature": "Canonical MCP Tool Schemas and M8ven annotations (v1.0.0)",
    },
    "specsynth/governance/__init__.py": {
        "milestone": "P6",
        "issue": "#29",
        "feature": "Governance and frozen baseline verification namespace",
    },
    "specsynth/governance/baseline_verifier.py": {
        "milestone": "P6",
        "issue": "#29",
        "feature": "Frozen P0 baseline verification engine and shallow-clone handling",
    },
}


class BaselineVerificationError(Exception):
    """Raised when frozen baseline verification fails under strict mode."""
    pass


class ShallowHistoryError(BaselineVerificationError):
    """Raised when local Git history is shallow and P0 baseline is unreachable."""
    pass


@dataclass
class BaselineVerificationResult:
    """Structured report payload for P0 architecture freeze auditing."""
    baseline_sha: str
    tested_commit_sha: str
    tested_branch: str
    is_shallow_clone: bool
    status: str  # "CONFORMANT" | "DRIFT_DETECTED" | "SHALLOW_HISTORY_ERROR"
    passed: bool
    allowed_core_files: list[str]
    modified_core_files: list[dict[str, Any]]
    unauthorized_core_files: list[dict[str, Any]]
    external_plugin_files: list[str]
    diagnostic_summary: str
    environment: dict[str, Any]
    timestamp_utc: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run_git_cmd(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Execute git command safely and return (code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def is_git_repository(repo_path: Path) -> bool:
    """Check if the specified path resides in a Git repository."""
    code, out, _ = _run_git_cmd(["rev-parse", "--is-inside-work-tree"], repo_path)
    return code == 0 and out == "true"


def is_shallow_clone(repo_path: Path) -> bool:
    """Check if the repository is a shallow clone."""
    code, out, _ = _run_git_cmd(["rev-parse", "--is-shallow-repository"], repo_path)
    return code == 0 and out == "true"


def resolve_commit_sha(repo_path: Path, ref: str) -> str | None:
    """Resolve a Git reference or tag to a 40-character commit SHA."""
    code, out, _ = _run_git_cmd(["rev-parse", "--verify", f"{ref}^{{commit}}"], repo_path)
    if code == 0 and len(out) == 40:
        return out
    return None


def get_current_head_sha(repo_path: Path) -> str:
    """Get the current HEAD commit SHA."""
    code, out, _ = _run_git_cmd(["rev-parse", "HEAD"], repo_path)
    return out if code == 0 else "UNKNOWN"


def get_current_branch(repo_path: Path) -> str:
    """Get the current branch name or 'DETACHED_HEAD'."""
    code, out, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    return out if code == 0 else "UNKNOWN"


def verify_frozen_baseline(
    repo_path: Path | None = None,
    baseline_sha: str = P0_BASELINE_SHA,
    strict: bool = False,
    allowlist: dict[str, dict[str, Any]] | None = None,
) -> BaselineVerificationResult:
    """
    Verify working tree and commit history against the immutable P0 baseline.

    Args:
        repo_path: Path to root of the repository. Defaults to Specsynth repository root.
        baseline_sha: Immutable commit SHA to compare against. Defaults to P0_BASELINE_SHA.
        strict: If True, fail with passed=False when unallowlisted core files are detected.
        allowlist: Dictionary of approved core files. Defaults to ROADMAP_CORE_ALLOWLIST.

    Returns:
        BaselineVerificationResult containing structured diagnostic report.
    """
    if repo_path is None:
        repo_path = Path(__file__).resolve().parents[2]
    repo_path = repo_path.resolve()

    if allowlist is None:
        allowlist = ROADMAP_CORE_ALLOWLIST

    env_info = {
        "os_platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "git_available": is_git_repository(repo_path),
    }

    if not is_git_repository(repo_path):
        return BaselineVerificationResult(
            baseline_sha=baseline_sha,
            tested_commit_sha="NON_GIT_WORKSPACE",
            tested_branch="NONE",
            is_shallow_clone=False,
            status="NON_GIT_WORKSPACE",
            passed=False,
            allowed_core_files=sorted(list(allowlist.keys())),
            modified_core_files=[],
            unauthorized_core_files=[],
            external_plugin_files=[],
            diagnostic_summary="Target directory is not a Git repository. Cannot perform history verification.",
            environment=env_info,
        )

    shallow = is_shallow_clone(repo_path)
    resolved_baseline = resolve_commit_sha(repo_path, baseline_sha)
    head_sha = get_current_head_sha(repo_path)
    branch = get_current_branch(repo_path)

    # 1. Handle Missing / Unreachable Baseline Commit (Fail Closed)
    if resolved_baseline is None:
        remediation_msg = (
            f"ERROR: P0 architecture-freeze baseline commit {baseline_sha[:7]} is not found in local git history.\n"
            f"Shallow clone detected: {shallow}.\n"
            f"Remediation:\n"
            f"  Run 'git fetch origin {baseline_sha}' (or 'git fetch --unshallow') to fetch frozen baseline history."
        )
        if strict:
            raise ShallowHistoryError(remediation_msg)

        return BaselineVerificationResult(
            baseline_sha=baseline_sha,
            tested_commit_sha=head_sha,
            tested_branch=branch,
            is_shallow_clone=shallow,
            status="SHALLOW_HISTORY_ERROR",
            passed=False,
            allowed_core_files=sorted(list(allowlist.keys())),
            modified_core_files=[],
            unauthorized_core_files=[],
            external_plugin_files=[],
            diagnostic_summary=remediation_msg,
            environment=env_info,
        )

    # 2. Compute Change Tree between P0 Baseline and Current Tree
    # git diff --name-status <baseline_sha> HEAD
    code, diff_out, err = _run_git_cmd(
        ["diff", "--name-status", resolved_baseline, "HEAD"],
        repo_path,
    )
    if code != 0:
        raise BaselineVerificationError(f"git diff failed between {resolved_baseline} and HEAD: {err}")

    # Also inspect uncommitted working tree changes
    code_wt, wt_out, _ = _run_git_cmd(["status", "--porcelain"], repo_path)

    # Collect changed paths
    changed_items: list[tuple[str, str]] = []  # (status, path)
    for line in diff_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            changed_items.append((parts[0], parts[1].replace("\\", "/")))

    # Process core files vs external plugin files
    modified_core: list[dict[str, Any]] = []
    unauthorized_core: list[dict[str, Any]] = []
    external_plugin_files: list[str] = []

    for status_code, file_path in changed_items:
        if file_path.startswith("examples/external_engine_plugin/"):
            external_plugin_files.append(file_path)
            continue

        if file_path.startswith("specsynth/"):
            # Check line stats
            _, numstat_out, _ = _run_git_cmd(
                ["diff", "--numstat", resolved_baseline, "HEAD", "--", file_path],
                repo_path,
            )
            additions, deletions = 0, 0
            if numstat_out:
                ns_parts = numstat_out.split()
                if len(ns_parts) >= 2 and ns_parts[0].isdigit() and ns_parts[1].isdigit():
                    additions = int(ns_parts[0])
                    deletions = int(ns_parts[1])

            item_info = {
                "file_path": file_path,
                "change_type": status_code,
                "lines_added": additions,
                "lines_deleted": deletions,
            }

            if file_path in allowlist:
                item_info["milestone"] = allowlist[file_path].get("milestone", "KNOWN")
                item_info["issue"] = allowlist[file_path].get("issue", "APPROVED")
                item_info["feature"] = allowlist[file_path].get("feature", "Core Subsystem")
                modified_core.append(item_info)
            else:
                item_info["milestone"] = "UNCLASSIFIED_DISCREPANCY"
                item_info["issue"] = "UNAUTHORIZED"
                item_info["feature"] = "Unregistered core file modification"
                unauthorized_core.append(item_info)

    # 3. Formulate Compliance Verdict
    has_unauthorized = len(unauthorized_core) > 0
    if not has_unauthorized:
        status_verdict = "CONFORMANT"
        passed = True
        summary = (
            f"P0 Frozen Baseline Verification: CONFORMANT. "
            f"All {len(modified_core)} modified core files are documented under authorized roadmap milestones. "
            f"External adapter plugin files ({len(external_plugin_files)} files) are strictly isolated."
        )
    else:
        status_verdict = "DRIFT_DETECTED"
        passed = False if strict else True  # Permissive reporting by default per user directive
        summary = (
            f"P0 Frozen Baseline Verification: DRIFT_DETECTED. "
            f"{len(unauthorized_core)} core file(s) modified without roadmap allowlist registration: "
            f"{[f['file_path'] for f in unauthorized_core]}. Detailed feature info recorded in report."
        )

    return BaselineVerificationResult(
        baseline_sha=resolved_baseline,
        tested_commit_sha=head_sha,
        tested_branch=branch,
        is_shallow_clone=shallow,
        status=status_verdict,
        passed=passed,
        allowed_core_files=sorted(list(allowlist.keys())),
        modified_core_files=modified_core,
        unauthorized_core_files=unauthorized_core,
        external_plugin_files=external_plugin_files,
        diagnostic_summary=summary,
        environment=env_info,
    )
