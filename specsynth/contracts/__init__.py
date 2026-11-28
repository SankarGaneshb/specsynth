"""
specsynth.contracts
===================
Canonical versioned data and protocol contracts for the Specsynth & PerandamΨ ecosystem.
Enforces P0 Scope and Architecture Freeze (Issue #14).
"""

from __future__ import annotations

from specsynth.contracts.data_mode import (
    DataMode,
    ExecutionMode,
    ExecutionProvenance,
    SourceProvenance,
    VerificationStatus,
    classify_source_data_mode,
    compute_file_sha256,
    propagate_mode,
    validate_source_provenance_evidence,
    verify_simulation_cutout_manifest,
)
from specsynth.contracts.evolution import (
    EvolutionaryTrackContract,
    MergerEvent,
    ProgenitorNode,
)
from specsynth.contracts.galaxy3d import (
    CoordinateFrame,
    Galaxy3DContract,
    GeometrySource,
    ParticleBatchContract,
    ParticleType,
)
from specsynth.contracts.mcp import (
    CANONICAL_MCP_TOOLS,
    LEGACY_TOOL_ALIASES,
    MCPToolContract,
    get_all_canonical_tools,
    get_canonical_tool_schema,
    resolve_tool_name,
)
from specsynth.contracts.photometry import (
    PhotometryPointContract,
    SyntheticObservationContract,
)
from specsynth.contracts.simulation import SimulationGalaxyContract
from specsynth.contracts.ssp import SSPGridContract

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "DataMode",
    "ExecutionMode",
    "SourceProvenance",
    "ExecutionProvenance",
    "propagate_mode",
    "classify_source_data_mode",
    "validate_source_provenance_evidence",
    "SSPGridContract",
    "SimulationGalaxyContract",
    "ParticleType",
    "GeometrySource",
    "CoordinateFrame",
    "ParticleBatchContract",
    "Galaxy3DContract",
    "PhotometryPointContract",
    "SyntheticObservationContract",
    "MCPToolContract",
    "CANONICAL_MCP_TOOLS",
    "LEGACY_TOOL_ALIASES",
    "resolve_tool_name",
    "get_all_canonical_tools",
    "get_canonical_tool_schema",
    "ProgenitorNode",
    "MergerEvent",
    "EvolutionaryTrackContract",
]
