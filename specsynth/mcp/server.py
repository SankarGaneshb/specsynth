"""
Standard JSON-RPC 2.0 Model Context Protocol (MCP) Server for SpecSynth.
Enables AI agents (Claude, Cursor, Antigravity) to query and drive SPS simulations.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from specsynth.filters import FILTER_SETS, STANDARD_FILTER_SPECS, get_filter
from specsynth.tools import (
    tool_clean_catalog,
    tool_get_system_info,
    tool_inspect_anomaly,
    tool_inspect_galaxy,
    tool_run_sentry_audit,
)

logger = logging.getLogger("specsynth.mcp")


class SpecsynthMCPServer:
    """Standard Model Context Protocol (MCP) Server implementing JSON-RPC 2.0 over stdio."""

    def __init__(self) -> None:
        self.server_info = {
            "name": "specsynth-mcp",
            "version": "1.0.0",
            "description": "Perandam Space Intelligence: SpecSynth SPS & Scientific Sentry MCP Server",
        }
        self.tools = self._register_tools()

    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "sps_list_filters": {
                "name": "sps_list_filters",
                "description": "List all available cosmological telescope and instrument filter sets (JWST, Roman, Euclid, Rubin, HST).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "instrument": {
                            "type": "string",
                            "description": "Optional filter to a specific instrument (e.g. 'jwst_nircam', 'roman_wfi', 'hst_wfc3').",
                        }
                    },
                },
                "handler": self._tool_list_filters,
            },
            "sps_inspect_galaxy": {
                "name": "sps_inspect_galaxy",
                "description": "Extract full physical parameters, SFH mass fraction, and synthesized flux for a galaxy by index.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "string", "description": "Base directory containing ssp.zarr and galaxies.zarr", "default": "./run"},
                        "galaxy_idx": {"type": "integer", "description": "Index of the galaxy to inspect", "default": 0},
                    },
                    "required": ["galaxy_idx"],
                },
                "handler": self._tool_inspect_galaxy,
            },
            "sps_run_sentry_audit": {
                "name": "sps_run_sentry_audit",
                "description": "Execute a 4-tier Scientific Sentry quality audit across synthesized catalogs to verify physical invariants.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "string", "description": "Base directory containing ssp.zarr, galaxies.zarr, and spectra.zarr", "default": "./run"},
                        "sample_size": {"type": "integer", "description": "Number of galaxies to audit (default: 10,000)", "default": 10000},
                    },
                },
                "handler": self._tool_run_sentry_audit,
            },
            "sps_remediate_catalog": {
                "name": "sps_remediate_catalog",
                "description": "Trigger the autonomous SentryAgent to isolate anomaly root causes, purge corruptions, and produce a pristine clean catalog.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "string", "description": "Base storage directory", "default": "./run"},
                        "output_csv": {"type": "string", "description": "Output path for the clean catalog CSV", "default": "clean_catalog.csv"},
                    },
                },
                "handler": self._tool_remediate_catalog,
            },
            "sps_load_tng_demo": {
                "name": "sps_load_tng_demo",
                "description": "Retrieve summary and sample galaxies from the validated TNG -> JWST NIRCam scientific demonstration catalog.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Maximum sample galaxies to return (default: 5)", "default": 5},
                    },
                },
                "handler": self._tool_load_tng_demo,
            },
            "sps_get_system_info": {
                "name": "sps_get_system_info",
                "description": "Get current host hardware info, CPU threads, RAM, and GPU/BLAS capabilities.",
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self._tool_get_system_info,
            },
        }

    # Tool Handlers
    def _tool_list_filters(self, args: Dict[str, Any]) -> Dict[str, Any]:
        inst = args.get("instrument")
        if inst and inst in FILTER_SETS:
            filter_details = []
            for f_name in FILTER_SETS[inst]:
                spec = STANDARD_FILTER_SPECS.get(f_name)
                center = spec[0] if spec else None
                fwhm = spec[1] if spec else None
                filter_details.append({
                    "name": f_name,
                    "center_wavelength": center,
                    "fwhm": fwhm,
                })
            return {
                "filter_set": inst,
                "filters": filter_details,
            }
        
        # Return all filter sets
        out = {}
        for set_name, f_list in FILTER_SETS.items():
            filter_details = []
            for f_name in f_list:
                spec = STANDARD_FILTER_SPECS.get(f_name)
                center = spec[0] if spec else None
                filter_details.append({
                    "name": f_name,
                    "center_wavelength": center,
                })
            out[set_name] = filter_details
        return {"available_filter_sets": out}

    def _tool_inspect_galaxy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        base = args.get("base", "./run")
        idx = int(args.get("galaxy_idx", 0))
        return tool_inspect_galaxy(base=base, galaxy_idx=idx)

    def _tool_run_sentry_audit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        base = args.get("base", "./run")
        size = int(args.get("sample_size", 10000))
        return tool_run_sentry_audit(base=base, sample_size=size)

    def _tool_remediate_catalog(self, args: Dict[str, Any]) -> Dict[str, Any]:
        base = args.get("base", "./run")
        out_csv = args.get("output_csv", "clean_catalog.csv")
        return tool_clean_catalog(base=base, output_path=out_csv)

    def _tool_get_system_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return tool_get_system_info()

    def _tool_load_tng_demo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        tng_path = Path("data/examples/tng_sample/sample_catalog.parquet")
        if not tng_path.exists():
            return {"error": f"TNG sample catalog not found at {tng_path}"}
        
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(tng_path))
            n_total = table.num_rows
            limit = min(int(args.get("limit", 5)), 50)
            
            sample_data = []
            cols = table.column_names
            pydict = table.slice(0, limit).to_pydict()
            for i in range(min(limit, n_total)):
                row = {c: pydict[c][i] for c in cols if not isinstance(pydict[c][i], (list, tuple)) or len(pydict[c][i]) < 10}
                sample_data.append(row)

            manifest_path = Path("paper/benchmark_manifest_tng_jwst.json")
            validation_status = "VERIFIED_FSPS_NIRCAM" if manifest_path.exists() else "AVAILABLE"

            return {
                "dataset": "IllustrisTNG -> JWST NIRCam Scientific Validation Sample",
                "total_galaxies": n_total,
                "columns": cols,
                "validation_status": validation_status,
                "sample_galaxies": sample_data,
            }
        except Exception as e:
            return {"error": f"Failed to read TNG sample: {str(e)}"}

    # JSON-RPC Dispatcher
    def handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": self.server_info,
                    "capabilities": {"tools": {}},
                },
            }

        elif method == "notifications/initialized":
            return {}  # Notifications don't require response

        elif method == "tools/list":
            tools_list = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"],
                }
                for t in self.tools.values()
            ]
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools_list}}

        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            if name not in self.tools:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool '{name}' not found"},
                }

            try:
                res = self.tools[name]["handler"](args)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(res, indent=2, default=str)}]
                    },
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(exc)},
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }

    def run_stdio(self) -> None:
        """Run the MCP server listening on stdin, responding to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                if resp:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def main() -> None:
    server = SpecsynthMCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
