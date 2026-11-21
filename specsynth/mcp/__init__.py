"""
specsynth.mcp: Model Context Protocol (MCP) and Local Bridge Suite for SpecSynth & PerandamΨ.
"""

__all__ = ["SpecsynthMCPServer", "run_bridge_server"]


def __getattr__(name: str):
    if name == "SpecsynthMCPServer":
        from specsynth.mcp.server import SpecsynthMCPServer
        return SpecsynthMCPServer
    if name == "run_bridge_server":
        from specsynth.mcp.bridge import run_bridge_server
        return run_bridge_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

