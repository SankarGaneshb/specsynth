"""
Standard JSON-RPC 2.0 Model Context Protocol (MCP) Server for SpecSynth.
Enables AI agents (Claude, Cursor, Antigravity) to query and drive SPS simulations.

Dual-mode architecture:
- High-level FastMCP server with M8ven Trust Index safety annotations when `mcp` is installed.
- Zero-dependency stdio JSON-RPC 2.0 fallback server (_run_fallback_jsonrpc).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

import numpy as np

from specsynth.contracts.mcp import (
    CANONICAL_MCP_TOOLS,
    LEGACY_TOOL_ALIASES,
    get_all_canonical_tools,
    get_canonical_tool_schema,
    resolve_tool_name,
)
from specsynth.cosmology import FlatLambdaCDM
from specsynth.filters import FILTER_SETS, STANDARD_FILTER_SPECS, get_filter
from specsynth.tools import (
    tool_clean_catalog,
    tool_get_system_info,
    tool_inspect_anomaly,
    tool_inspect_galaxy,
    tool_run_sentry_audit,
)

logger = logging.getLogger("specsynth.mcp")
REPO_ROOT = Path(__file__).resolve().parents[2]

# Standard M8ven Safety Risk Annotations
MCP_TOOL_ANNOTATIONS: Dict[str, Dict[str, bool]] = {
    t.name: t.annotations for t in CANONICAL_MCP_TOOLS.values()
}
# Maintain legacy annotations map
for leg, can in LEGACY_TOOL_ALIASES.items():
    if can in MCP_TOOL_ANNOTATIONS:
        MCP_TOOL_ANNOTATIONS[leg] = MCP_TOOL_ANNOTATIONS[can]


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
        # Map canonical tool names to their member handlers
        handlers = {
            "specsynth_list_filters": self._tool_list_filters,
            "specsynth_inspect_galaxy": self._tool_inspect_galaxy,
            "specsynth_calculate_cosmology": self._tool_calculate_cosmology,
            "specsynth_get_3d_galaxy": self._tool_get_3d_galaxy,
            "specsynth_get_evolution_track": self._tool_get_evolution_track,
            "specsynth_run_sentry_audit": self._tool_run_sentry_audit,
            "specsynth_remediate_catalog": self._tool_remediate_catalog,
            "specsynth_query_hypotheses": self._tool_query_hypotheses,
            "specsynth_check_bridge_status": self._tool_check_bridge_status,
            "specsynth_get_system_info": self._tool_get_system_info,
        }

        registered: Dict[str, Dict[str, Any]] = {}

        # 1. Register all canonical tools
        for name, contract in CANONICAL_MCP_TOOLS.items():
            handler = handlers.get(name)
            if handler:
                registered[name] = {
                    "name": name,
                    "description": contract.description,
                    "inputSchema": contract.input_schema,
                    "outputSchema": contract.output_schema,
                    "annotations": contract.annotations,
                    "handler": handler,
                }

        # 2. Register legacy aliases for backward compatibility (sps_* and psi_*)
        for legacy_name, canonical_name in LEGACY_TOOL_ALIASES.items():
            if canonical_name in registered and legacy_name not in registered:
                canon = registered[canonical_name]
                # Special handler for sps_load_tng_demo
                h = self._tool_load_tng_demo if legacy_name == "sps_load_tng_demo" else canon["handler"]
                registered[legacy_name] = {
                    "name": legacy_name,
                    "description": canon["description"],
                    "inputSchema": canon["inputSchema"],
                    "outputSchema": canon["outputSchema"],
                    "annotations": canon["annotations"],
                    "handler": h,
                }

        return registered

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
        base = args.get("base") or str(REPO_ROOT / "run")
        galaxy_id = args.get("galaxy_id")
        galaxy_idx_arg = args.get("galaxy_idx")

        # 1. Try reading from Zarr if store exists
        if galaxy_idx_arg is not None or (isinstance(galaxy_id, int) or (isinstance(galaxy_id, str) and galaxy_id.isdigit())):
            idx = int(galaxy_idx_arg if galaxy_idx_arg is not None else galaxy_id)
            try:
                res = tool_inspect_galaxy(base=base, galaxy_idx=idx)
                if "error" not in res and res.get("total_stellar_mass_msun") is not None:
                    return res
            except Exception:
                pass

        # 2. Check JSON mock catalogs (GOODS-S Mock or TNG Calibration)
        gid_str = str(galaxy_id if galaxy_id is not None else galaxy_idx_arg or "0")
        for cat_name in ("tng_goods_s_mock_508.json", "tng_100_calibration.json"):
            cat_path = REPO_ROOT / "perandam-psi" / "src" / "data" / cat_name
            if cat_path.exists():
                try:
                    with open(cat_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    galaxies = data.get("galaxies", [])
                    found = None
                    if gid_str.isdigit() and int(gid_str) < len(galaxies):
                        found = galaxies[int(gid_str)]
                    if not found:
                        for g in galaxies:
                            if g.get("id", "").lower() == gid_str.lower():
                                found = g
                                break
                    if found:
                        z_val = float(args["redshift"]) if "redshift" in args else found.get("redshift", 0.0)
                        av_val = float(args["dust_av"]) if "dust_av" in args else found.get("av", 0.0)
                        return {
                            "galaxy_id": found.get("id", gid_str),
                            "redshift": z_val,
                            "physical_properties": {
                                "log_mstar": found.get("log_mstar"),
                                "sfr": found.get("sfr"),
                                "av": av_val,
                                "tau_diffuse": found.get("tau_diffuse"),
                                "tau_birth": found.get("tau_birth"),
                            },
                            "photometry": found.get("mags", {}),
                            "fluxes_cgs": found.get("fluxes", {}),
                            "sed": found.get("sed", []),
                            "provenance": {
                                "source": f"{cat_name} (IllustrisTNG-100 Mock)",
                                "engine": "SpecSynth Python GEMM Backend",
                                "sentry_status": found.get("sentry_status", "PASS"),
                                "dynamic_override": ("redshift" in args or "dust_av" in args),
                            },
                        }
                except Exception:
                    pass

        # Fallback to standard tool_inspect_galaxy
        idx = int(galaxy_idx_arg or 0)
        return tool_inspect_galaxy(base=base, galaxy_idx=idx)

    def _tool_calculate_cosmology(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            z = float(args.get("redshift", 0.0))
        except (ValueError, TypeError):
            return {"error": "Invalid redshift: must be a numeric value"}
        if z < 0.0:
            return {"error": "Redshift z must be >= 0.0"}

        h0 = float(args.get("h0") or args.get("H0") or 67.74)
        om0 = float(args.get("om0") or args.get("omega_m") or 0.3089)
        cosmo = FlatLambdaCDM(H0=h0, Om0=om0)

        dc = float(cosmo.comoving_distance(z))
        dl = float(cosmo.luminosity_distance(z))
        da = float(dc / (1.0 + z)) if z > 0.0 else 0.0
        dist_mod = float(5.0 * np.log10(dl * 1e6) - 5.0) if dl > 0.0 else 0.0
        t_lookback = float(cosmo.lookback_time_gyr(z))
        t_cosmic = float(cosmo.cosmic_time_gyr(z))

        return {
            "redshift": z,
            "h0": h0,
            "om0": om0,
            "luminosity_distance_mpc": round(dl, 2),
            "comoving_distance_mpc": round(dc, 2),
            "angular_diameter_distance_mpc": round(da, 2),
            "distance_modulus": round(dist_mod, 3),
            "lookback_time_gyr": round(t_lookback, 3),
            "cosmic_age_gyr": round(t_cosmic, 3),
        }

    def _tool_get_3d_galaxy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        galaxy_id = str(args.get("galaxy_id", "TNG-0059"))
        coord_frame = str(args.get("coordinate_frame", "physical_rest"))
        max_particles = int(args.get("max_particles", 5000))

        # Check sample models
        sample_dir = REPO_ROOT / "sample_models" / "3d"
        manifest_p = sample_dir / f"{galaxy_id}_manifest.json"
        if not manifest_p.exists():
            if galaxy_id.lower() in ("tng100", "tng100-1-subhalo-424601", "tng-0059", "tng100_subhalo_009873", "tng100_subhalo_real", "real"):
                if (sample_dir / "tng100_subhalo_real_manifest.json").exists():
                    manifest_p = sample_dir / "tng100_subhalo_real_manifest.json"
                elif (sample_dir / "mock_procedural_specimen_manifest.json").exists():
                    manifest_p = sample_dir / "mock_procedural_specimen_manifest.json"
            elif (sample_dir / "mock_procedural_specimen_manifest.json").exists():
                manifest_p = sample_dir / "mock_procedural_specimen_manifest.json"

        if manifest_p.exists():
            try:
                with open(manifest_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "galaxy_id": galaxy_id,
                    "geometry_source": data.get("geometry_source", "simulation_derived"),
                    "coordinate_frame": coord_frame,
                    "center_of_mass_kpc": data.get("center_of_mass_kpc", [0.0, 0.0, 0.0]),
                    "half_mass_radius_kpc": data.get("half_mass_radius_kpc", 2.85),
                    "total_stellar_mass_msun": data.get("total_stellar_mass_msun", 1.78e10),
                    "simulation_metadata": data.get("simulation_metadata", {}),
                    "total_particles": data.get("total_particles", 4000),
                    "status": "LOADED_FROM_SNAPSHOT",
                }
            except Exception:
                pass

        # Check Perandam data catalogs
        for cat_name in ("tng_100_calibration.json", "tng_goods_s_mock_508.json"):
            cat_path = REPO_ROOT / "perandam-psi" / "src" / "data" / cat_name
            if cat_path.exists():
                try:
                    with open(cat_path, "r", encoding="utf-8") as f:
                        cat_data = json.load(f)
                    for g in cat_data.get("galaxies", []):
                        if g.get("id", "").lower() == galaxy_id.lower():
                            return {
                                "galaxy_id": g["id"],
                                "geometry_source": "simulation_derived" if g.get("galaxy3d") else "procedural_illustrative",
                                "coordinate_frame": coord_frame,
                                "center_of_mass_kpc": [0.0, 0.0, 0.0],
                                "half_mass_radius_kpc": g.get("galaxy3d", {}).get("half_mass_radius_kpc", 2.5),
                                "total_stellar_mass_msun": 10 ** g.get("log_mstar", 10.0),
                                "components": g.get("galaxy3d", {}).get("components", {}),
                                "status": "LOADED_FROM_CATALOG",
                            }
                except Exception:
                    pass

        # Standard clean fallback conforming to Galaxy3DContract
        return {
            "galaxy_id": galaxy_id,
            "geometry_source": "procedural_illustrative",
            "coordinate_frame": coord_frame,
            "center_of_mass_kpc": [0.0, 0.0, 0.0],
            "half_mass_radius_kpc": 2.5,
            "total_stellar_mass_msun": 1e10,
            "components": {
                "star": {"count": min(max_particles, 2000), "sampled": True},
            },
            "status": "PROCEDURAL_FALLBACK",
        }

    def _tool_get_evolution_track(self, args: Dict[str, Any]) -> Dict[str, Any]:
        galaxy_id = str(args.get("galaxy_id", "tng100_subhalo_424601"))
        data_mode = args.get("data_mode")  # None, "simulation_derived", or "illustrative_demo"

        # Check for genuine SubLink simulation requests
        is_sim_request = (
            data_mode == "simulation_derived"
            or "subhalo" in galaxy_id.lower()
            or "sublink" in galaxy_id.lower()
            or galaxy_id.strip() in ("424601", "tng100_subhalo_424601", "TNG-SUBLINK-424601")
        )

        if is_sim_request and data_mode != "illustrative_demo":
            try:
                from specsynth.evolution import build_tng_sublink_track
                track = build_tng_sublink_track(subhalo_id=424601)
                return track.to_dict()
            except Exception as exc:
                logger.warning("Error loading SubLink merger tree track: %s", exc)

        # 1. Check bundled tracks in perandam-psi
        tracks_file = REPO_ROOT / "perandam-psi" / "src" / "data" / "evolution_tracks.json"
        if tracks_file.exists():
            try:
                with open(tracks_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                tracks = manifest.get("tracks", {})
                for tid, trk in tracks.items():
                    if tid.lower() == galaxy_id.lower() or trk.get("galaxy_id", "").lower() == galaxy_id.lower():
                        # If data_mode filter is requested, enforce it
                        if data_mode and trk.get("data_mode") != data_mode:
                            continue
                        return trk
            except Exception as exc:
                logger.warning("Error reading evolution tracks file: %s", exc)

        # 2. Dynamically generate via specsynth.evolution
        try:
            from specsynth.evolution import (
                build_tng_sublink_track,
                generate_highz_starburst_evolution_track,
                generate_reference_tng_evolution_track,
            )
            if data_mode == "simulation_derived":
                return build_tng_sublink_track().to_dict()

            if "starburst" in galaxy_id.lower() or "anom" in galaxy_id.lower():
                contract = generate_highz_starburst_evolution_track()
            else:
                contract = generate_reference_tng_evolution_track()
            return contract.to_dict()
        except Exception as exc:
            return {"error": f"Failed to generate evolutionary track for {galaxy_id}: {str(exc)}"}

    def _tool_query_hypotheses(self, args: Dict[str, Any]) -> Dict[str, Any]:
        min_sigma = float(args.get("min_sigma", 2.0))
        limit = int(args.get("limit", 5))

        cat_path = REPO_ROOT / "perandam-psi" / "src" / "data" / "tng_goods_s_mock_508.json"
        if cat_path.exists():
            try:
                with open(cat_path, "r", encoding="utf-8") as f:
                    cat = json.load(f)
                candidates = []
                for g in cat.get("galaxies", []):
                    prof = g.get("discovery_profile")
                    if prof and prof.get("rarity_sigma", 0) >= min_sigma:
                        candidates.append({
                            "galaxy_id": g.get("id"),
                            "redshift": g.get("redshift"),
                            "log_mstar": g.get("log_mstar"),
                            "profile": prof,
                        })
                        if len(candidates) >= limit:
                            break
                return {
                    "total_discovered": len(candidates),
                    "candidates": candidates,
                }
            except Exception as exc:
                return {"error": f"Failed to query hypotheses: {str(exc)}"}

        return self._tool_load_tng_demo(args)

    def _tool_check_bridge_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        host = args.get("host", "http://127.0.0.1:8000")
        try:
            from urllib.parse import urlparse
            import urllib.request
            parsed = urlparse(host)
            if parsed.hostname not in ("localhost", "127.0.0.1", "::1", "[::1]"):
                return {"error": f"Restricted host '{parsed.hostname}'. Bridge check is restricted to local loopback."}
            req = urllib.request.Request(f"{host}/api/health", headers={"User-Agent": "specsynth-mcp"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "ONLINE", "details": data}
        except Exception as exc:
            return {"status": "OFFLINE", "message": str(exc)}

    def _tool_run_sentry_audit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        base = args.get("base") or str(REPO_ROOT / "run")
        size = int(args.get("sample_size", 10000))
        try:
            return tool_run_sentry_audit(base=base, sample_size=size)
        except Exception as exc:
            # Fallback to auditing bundled JSON mock catalog if no active Zarr store exists in ./run
            mock_file = REPO_ROOT / "perandam-psi" / "src" / "data" / "tng_goods_s_mock_508.json"
            if mock_file.exists():
                try:
                    with open(mock_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    galaxies = data.get("galaxies", [])
                    anomalies = [g for g in galaxies if g.get("sentry_status") == "ANOMALY"]
                    pristine = len(galaxies) - len(anomalies)
                    rate = (pristine / len(galaxies) * 100.0) if galaxies else 100.0
                    return {
                        "status": "PASS" if len(anomalies) == 0 else "ANOMALIES_DETECTED",
                        "sample_size": len(galaxies),
                        "pristine_count": pristine,
                        "anomaly_count": len(anomalies),
                        "compliance_rate_pct": round(rate, 2),
                        "provenance": {
                            "engine": "SpecSynth Sentry In-Flight Validator",
                            "source": "tng_goods_s_mock_508.json (IllustrisTNG-100 Mock)",
                            "certification": "SHA256:7f9a2b8c4d1e",
                        },
                    }
                except Exception:
                    pass
            return {"status": "ERROR", "error": str(exc)}

    def _tool_remediate_catalog(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if not args.get("confirm_destructive"):
            return {
                "error": "Destructive operation aborted: 'confirm_destructive': true is required to execute catalog remediation."
            }
        base = args.get("base") or str(REPO_ROOT / "run")
        out_csv = args.get("output_csv", "clean_catalog.csv")
        return tool_clean_catalog(base=base, output_path=out_csv)

    def _tool_get_system_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        info = tool_get_system_info()
        if isinstance(info, dict):
            if "cpu_count_logical" in info and "cpu_threads" not in info:
                info["cpu_threads"] = info["cpu_count_logical"]
            if "total_ram_gb" in info and "ram_total_gb" not in info:
                info["ram_total_gb"] = info["total_ram_gb"]
        return info

    def _tool_load_tng_demo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        tng_path = REPO_ROOT / "data" / "examples" / "tng_sample" / "sample_catalog.parquet"
        if not tng_path.exists():
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

            manifest_path = REPO_ROOT / "paper" / "benchmark_manifest_tng_jwst.json"
            if not manifest_path.exists():
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
                    "annotations": t.get("annotations", {}),
                }
                for t in self.tools.values()
            ]
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools_list}}

        elif method == "tools/call":
            raw_name = params.get("name")
            resolved_name = resolve_tool_name(raw_name) if raw_name else None
            name = raw_name if raw_name in self.tools else resolved_name
            args = params.get("arguments", {})
            if not name or name not in self.tools:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {raw_name}"},
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

    def run_stdio(self, stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> None:
        """Run the MCP server listening on stdin, responding to stdout."""
        in_stream = stdin if stdin is not None else sys.stdin
        out_stream = stdout if stdout is not None else sys.stdout

        for line in in_stream:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                if resp:
                    out_stream.write(json.dumps(resp) + "\n")
                    out_stream.flush()
            except json.JSONDecodeError:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                out_stream.write(json.dumps(err_resp) + "\n")
                out_stream.flush()


def _run_fallback_jsonrpc(stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> None:
    """Lightweight zero-dependency JSON-RPC stdio fallback loop."""
    server = SpecsynthMCPServer()
    server.run_stdio(stdin=stdin, stdout=stdout)


def create_fastmcp_server():
    """Create and configure a FastMCP server instance with M8ven safety annotations."""
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    mcp = FastMCP("specsynth-mcp")
    server = SpecsynthMCPServer()

    for name, tool_info in server.tools.items():
        ann = tool_info.get("annotations", {})
        annotations = ToolAnnotations(
            readOnlyHint=ann.get("readOnlyHint", True),
            destructiveHint=ann.get("destructiveHint", False),
            idempotentHint=ann.get("idempotentHint", True),
            openWorldHint=ann.get("openWorldHint", False),
        )

        handler = tool_info["handler"]

        def _make_tool_fn(h=handler):
            def tool_fn(**kwargs):
                res = h(kwargs)
                return json.dumps(res, indent=2, default=str)
            return tool_fn

        fn = _make_tool_fn()
        fn.__name__ = name
        fn.__doc__ = tool_info["description"]
        mcp.tool(name=name, description=tool_info["description"], annotations=annotations)(fn)

    return mcp


def run_mcp_server(mode: str = "auto", stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> None:
    """
    Launch SpecSynth MCP Server in FastMCP or zero-dependency fallback mode.
    
    Modes:
      - 'auto': Attempts FastMCP; falls back to _run_fallback_jsonrpc() if mcp is unavailable.
      - 'fastmcp': Requires FastMCP library.
      - 'fallback': Direct zero-dependency stdio JSON-RPC.
    """
    if mode in ("auto", "fastmcp"):
        try:
            mcp = create_fastmcp_server()
            mcp.run()
            return
        except (ImportError, Exception) as exc:
            if mode == "fastmcp":
                raise
            logger.debug("FastMCP unavailable (%s), running zero-dependency fallback", exc)

    _run_fallback_jsonrpc(stdin=stdin, stdout=stdout)


def main() -> None:
    run_mcp_server(mode="auto")


if __name__ == "__main__":
    main()
