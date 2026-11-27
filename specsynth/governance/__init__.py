"""
Specsynth Governance & Architecture Freeze Auditing Subsystem.
=============================================================
Defines immutable architecture baseline constants, roadmap core allowlist,
and verification interfaces for Pillar 1 (Zero-Core-Modification Pluggability).
"""

from __future__ import annotations

from specsynth.governance.baseline_verifier import (
    P0_BASELINE_SHA,
    P0_BASELINE_TAG,
    ROADMAP_CORE_ALLOWLIST,
    BaselineVerificationError,
    BaselineVerificationResult,
    ShallowHistoryError,
    verify_frozen_baseline,
)

__all__ = [
    "P0_BASELINE_SHA",
    "P0_BASELINE_TAG",
    "ROADMAP_CORE_ALLOWLIST",
    "BaselineVerificationError",
    "BaselineVerificationResult",
    "ShallowHistoryError",
    "verify_frozen_baseline",
]
