"""
specsynth.contracts
===================
Canonical versioned data and protocol contracts for the Specsynth & PerandamΨ ecosystem.
Enforces P0 Scope and Architecture Freeze (Issue #14).
"""

from __future__ import annotations

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
    MCPToolContract,
    get_canonical_tool_schema,
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
    "get_canonical_tool_schema",
    "ProgenitorNode",
    "MergerEvent",
    "EvolutionaryTrackContract",
]
