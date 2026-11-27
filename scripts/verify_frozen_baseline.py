#!/usr/bin/env python3
"""
CLI Runner for Frozen P0 Baseline Architecture Verification (GitHub Issue #29).
==============================================================================
Audits git change history against the immutable P0 architecture-freeze baseline commit
(8e36648) to prove that external adapters operate without unauthorized core modifications.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from specsynth.governance import (
    P0_BASELINE_SHA,
    BaselineVerificationResult,
    verify_frozen_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify codebase against the frozen P0 architecture baseline (Issue #29 / P6)"
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=P0_BASELINE_SHA,
        help=f"Immutable baseline commit SHA (default: {P0_BASELINE_SHA[:7]})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("baseline_verification_report.json"),
        help="Path to export machine-readable JSON report",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with non-zero exit code if unauthorized core changes are detected",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("  SPECSYNTH ARCHITECTURE FREEZE VERIFIER")
    print(f"  Auditing Against Immutable P0 Baseline: {args.baseline[:12]}")
    print("  Pillar 1: Zero-Core-Modification Pluggability (Issue #29 / P6)")
    print("=" * 80)

    res: BaselineVerificationResult = verify_frozen_baseline(
        repo_path=repo_root,
        baseline_sha=args.baseline,
        strict=args.strict,
    )

    print(f"Tested Commit  : {res.tested_commit_sha[:12]} ({res.tested_branch})")
    print(f"Baseline Commit: {res.baseline_sha[:12]} ({'RESOLVED' if len(res.baseline_sha) == 40 else 'UNRESOLVED'})")
    print(f"Shallow Clone  : {'YES (Fail-closed history check)' if res.is_shallow_clone else 'NO (Full history available)'}")
    print("-" * 80)

    if res.status == "SHALLOW_HISTORY_ERROR":
        print(f"\n[FAIL] {res.diagnostic_summary}")
        return 1

    print(f"{'Core File Path':<35} {'Status':<6} {'Roadmap':<10} {'Feature Subsystem'}")
    print("-" * 80)
    for f in res.modified_core_files:
        print(f"{f['file_path']:<35} {f['change_type']:<6} {f['milestone']:<10} {f['feature'][:27]}")

    if res.unauthorized_core_files:
        print("-" * 80)
        print("UNAUTHORIZED CORE MODIFICATIONS DETECTED:")
        for uf in res.unauthorized_core_files:
            print(f"  [!] {uf['file_path']} (+{uf['lines_added']}/-{uf['lines_deleted']}) - Feature: {uf['feature']}")

    print("-" * 80)
    print(f"External Plugin Files Tracked : {len(res.external_plugin_files)} files in examples/external_engine_plugin/")
    print(f"Roadmap Core Files Modified   : {len(res.modified_core_files)} files (All roadmap-attributed)")
    print(f"Unauthorized Core Files       : {len(res.unauthorized_core_files)} files")
    print(f"Overall Compliance Status     : {res.status}")
    print("=" * 80)

    # Save machine-readable report
    output_path = args.output.resolve()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(res.to_dict(), f, indent=2)
    print(f"Machine-readable audit report written to: {output_path}")

    if args.strict and not res.passed:
        print("\nFAILED: Strict mode enabled and baseline deviations were detected.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
