"""
Lightweight Zero-Dependency Local HTTP Bridge for SpecSynth & PerandamΨ.
Serves REST endpoints on localhost:8000 for the PerandamΨ Web UI.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any, Dict

# Ensure stdout and stderr handle UTF-8 without failing on Windows charmap/cp1252
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from specsynth.filters import FILTER_SETS, STANDARD_FILTER_SPECS
from specsynth.mcp.server import SpecsynthMCPServer

logger = logging.getLogger("specsynth.bridge")


class BridgeHTTPHandler(BaseHTTPRequestHandler):
    """CORS-enabled HTTP request handler for the PerandamΨ frontend."""

    server_instance: SpecsynthMCPServer | None = None
    auth_token: str | None = None
    allow_remote: bool = False

    def _check_auth(self) -> bool:
        """Validate bearer token authentication if auth_token is configured."""
        if not self.auth_token:
            return True

        auth_header = self.headers.get("Authorization", "")
        token_header = self.headers.get("X-Specsynth-Token", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header:
            token = auth_header.strip()
        elif token_header:
            token = token_header.strip()

        if token == self.auth_token:
            return True

        self._set_cors_headers(401)
        self.wfile.write(json.dumps({"error": "401 Unauthorized: Valid Bearer token required"}).encode("utf-8"))
        return False

    def _set_cors_headers(self, status_code: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status_code)
        origin = self.headers.get("Origin", "") if hasattr(self, "headers") and self.headers else ""
        allowed_origin = "http://localhost:5173"
        if origin:
            try:
                parsed_origin = urlparse(origin)
                # Check exact hostname to prevent subdomain bypasses like http://localhost.attacker.com
                if parsed_origin.scheme in ("http", "https") and parsed_origin.hostname in ("localhost", "127.0.0.1", "::1", "[::1]"):
                    allowed_origin = origin
            except Exception:
                pass
        self.send_header("Access-Control-Allow-Origin", allowed_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_cors_headers(204)

    def do_GET(self) -> None:
        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        mcp = self.server_instance or SpecsynthMCPServer()

        # 1. SPA Static File Serving (perandam-psi/dist)
        dist_dir = Path(__file__).parents[2] / "perandam-psi" / "dist"
        index_file = dist_dir / "index.html"

        if not path.startswith("/api"):
            subpath = path.lstrip("/") or "index.html"
            dist_resolved = dist_dir.resolve()
            try:
                target_file = (dist_dir / subpath).resolve()
                if dist_resolved not in target_file.parents and target_file != dist_resolved:
                    self._set_cors_headers(403, content_type="text/plain")
                    self.wfile.write(b"403 Forbidden: Directory traversal blocked")
                    return
            except Exception:
                self._set_cors_headers(403, content_type="text/plain")
                self.wfile.write(b"403 Forbidden: Invalid file path")
                return

            if target_file.exists() and target_file.is_file():
                content_type = "text/html"
                if subpath.endswith(".js"):
                    content_type = "application/javascript"
                elif subpath.endswith(".css"):
                    content_type = "text/css"
                elif subpath.endswith(".json"):
                    content_type = "application/json"
                elif subpath.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif subpath.endswith(".png"):
                    content_type = "image/png"
                elif subpath.endswith(".ico"):
                    content_type = "image/x-icon"
                self._set_cors_headers(200, content_type=content_type)
                if subpath.endswith("index.html") or subpath == "index.html":
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                with open(target_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            elif subpath.startswith("assets/") or "." in subpath:
                # Do NOT serve index.html for missing static assets (causes JS MIME type error)
                self._set_cors_headers(404, content_type="text/plain")
                self.wfile.write(f"Asset '{subpath}' not found".encode("utf-8"))
                return
            elif index_file.exists():
                self._set_cors_headers(200, content_type="text/html")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                with open(index_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            elif path in ("/", ""):
                self._set_cors_headers(200)
                res = {
                    "service": "Perandam Space Intelligence (PSI) — SpecSynth HTTP Bridge",
                    "mark": "PerandamΨ",
                    "status": "online",
                    "version": "1.0.0",
                    "frontend_url": "http://localhost:5173",
                    "endpoints": {
                        "health": "/api/health",
                        "filters": "/api/filters?instrument=jwst_nircam",
                        "tng_catalog": "/api/tng-catalog?limit=5",
                        "inspect_galaxy": "/api/inspect?galaxy_idx=0",
                        "system_hardware": "/api/system",
                        "sentry_audit": "/api/audit",
                        "cosmology": "/api/cosmology?redshift=2.0",
                        "galaxy3d": "/api/galaxy3d?galaxy_id=TNG-0059",
                        "evolution": "/api/evolution?galaxy_id=TNG-DISC-01",
                        "hypotheses": "/api/hypotheses?min_sigma=2.0",
                        "tools": "/api/tools",
                    },
                    "instructions": "Build frontend with 'cd perandam-psi; npm run build' to serve from port 8000, or run 'npm run dev'.",
                }
                self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))
                return
            else:
                self._set_cors_headers(404)
                self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found"}).encode("utf-8"))
                return

        # 2. REST API Endpoints (/api/*)
        now = datetime.now().strftime("%H:%M:%S")
        if path == "/api/health":
            self._set_cors_headers(200)
            res = {
                "status": "ok",
                "service": "specsynth-mcp-bridge",
                "brand": "Perandam Space Intelligence (PSI)",
                "mark": "PerandamΨ",
                "version": "1.0.0",
                "timestamp": now,
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))
            print(f"[{now}] [Engine Heartbeat] GET /api/health -> 200 OK (Perandam-Psi connected)")

        elif path == "/api/filters":
            inst = query.get("instrument", [None])[0]
            data = mcp._tool_list_filters({"instrument": inst})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Filters API] GET /api/filters?instrument={inst or 'all'} -> 200 OK")

        elif path == "/api/tng-catalog":
            limit = int(query.get("limit", [100])[0])
            data = mcp._tool_load_tng_demo({"limit": limit})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Catalog API] GET /api/tng-catalog (limit={limit}) -> 200 OK")

        elif path == "/api/inspect":
            idx_param = query.get("galaxy_idx", query.get("idx", [None]))[0]
            gid = query.get("galaxy_id", query.get("id", [None]))[0]
            base = query.get("base", ["./run"])[0]
            args = {"base": base}
            if gid is not None:
                args["galaxy_id"] = gid
            if idx_param is not None:
                try:
                    args["galaxy_idx"] = int(idx_param)
                except ValueError:
                    args["galaxy_id"] = idx_param
            elif gid is None:
                args["galaxy_idx"] = 0

            # Forward-modeling dynamic parameter overrides
            if "redshift" in query or "z" in query:
                args["redshift"] = float(query.get("redshift", query.get("z", [None]))[0])
            if "dust_av" in query or "av" in query:
                args["dust_av"] = float(query.get("dust_av", query.get("av", [None]))[0])

            data = mcp._tool_inspect_galaxy(args)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Inspect API] GET /api/inspect ({args}) -> 200 OK")

        elif path == "/api/system":
            data = mcp._tool_get_system_info({})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [System API] GET /api/system -> 200 OK (Hardware reported)")

        elif path == "/api/audit":
            base = query.get("base", ["./run"])[0]
            data = mcp._tool_run_sentry_audit({"base": base, "sample_size": 5000})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Sentry Audit API] GET /api/audit (base={base}) -> 200 OK")

        elif path == "/api/cosmology":
            z_val = float(query.get("redshift", query.get("z", [0.0]))[0])
            h0_val = float(query.get("h0", [67.74])[0])
            om0_val = float(query.get("om0", query.get("omega_m", [0.3089]))[0])
            data = mcp._tool_calculate_cosmology({"redshift": z_val, "h0": h0_val, "om0": om0_val})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Cosmology API] GET /api/cosmology?z={z_val} -> 200 OK")

        elif path == "/api/galaxy3d":
            gid = query.get("galaxy_id", query.get("id", ["TNG-0059"]))[0]
            frame = query.get("coordinate_frame", ["physical_rest"])[0]
            data = mcp._tool_get_3d_galaxy({"galaxy_id": gid, "coordinate_frame": frame})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Galaxy 3D API] GET /api/galaxy3d?id={gid} -> 200 OK")

        elif path == "/api/evolution":
            gid = query.get("galaxy_id", query.get("id", ["TNG-DISC-01"]))[0]
            data = mcp._tool_get_evolution_track({"galaxy_id": gid})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Evolution API] GET /api/evolution?id={gid} -> 200 OK")

        elif path == "/api/hypotheses":
            min_sig = float(query.get("min_sigma", [2.0])[0])
            limit_val = int(query.get("limit", [5])[0])
            data = mcp._tool_query_hypotheses({"min_sigma": min_sig, "limit": limit_val})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Hypotheses API] GET /api/hypotheses -> 200 OK")

        elif path in ("/api/tools", "/api/tools/list"):
            resp = mcp.handle_request({
                "jsonrpc": "2.0",
                "id": "http-bridge-get",
                "method": "tools/list",
                "params": {},
            })
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            print(f"[{now}] [MCP Tools List] GET {path} -> 200 OK")

        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found"}).encode("utf-8"))
            print(f"[{now}] [404 Not Found] GET {path}")

    def do_POST(self) -> None:
        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        now = datetime.now().strftime("%H:%M:%S")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = {}
        if body:
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"error": "Malformed JSON body"}).encode("utf-8"))
                print(f"[{now}] [400 Bad Request] POST {path} (Malformed JSON)")
                return

        mcp = self.server_instance or SpecsynthMCPServer()

        if path in ("/api/tools/call", "/api/tools"):
            if "method" in data:
                # Direct JSON-RPC dispatch (initialize, tools/list, tools/call)
                resp = mcp.handle_request(data)
                method_name = data.get("method")
            else:
                # Legacy REST format: { "name": ..., "arguments": ... }
                tool_name = data.get("name")
                tool_args = data.get("arguments", {})
                resp = mcp.handle_request({
                    "jsonrpc": "2.0",
                    "id": "http-bridge",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": tool_args},
                })
                method_name = f"tools/call ({tool_name})"
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            print(f"[{now}] [MCP Tool Dispatch] POST {path} -> {method_name} -> 200 OK")

        elif path == "/api/cosmology":
            res = mcp._tool_calculate_cosmology(data)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
            print(f"[{now}] [Cosmology API] POST /api/cosmology -> 200 OK")

        elif path == "/api/galaxy3d":
            res = mcp._tool_get_3d_galaxy(data)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
            print(f"[{now}] [Galaxy 3D API] POST /api/galaxy3d -> 200 OK")

        elif path == "/api/evolution":
            res = mcp._tool_get_evolution_track(data)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
            print(f"[{now}] [Evolution API] POST /api/evolution -> 200 OK")

        elif path == "/api/hypotheses":
            res = mcp._tool_query_hypotheses(data)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
            print(f"[{now}] [Hypotheses API] POST /api/hypotheses -> 200 OK")

        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": f"POST endpoint '{path}' not found"}).encode("utf-8"))
            print(f"[{now}] [404 Not Found] POST {path}")

    def log_message(self, format: str, *args: Any) -> None:
        """Stream HTTP access logs to console."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = format % args
        # Only log non-empty message strings
        if msg.strip():
            print(f"[{timestamp}] [HTTP Log] {self.command} {self.path} -> {msg}")


def is_loopback(host: str) -> bool:
    """Check if host address is a local loopback interface."""
    return host.strip().lower() in ("127.0.0.1", "localhost", "::1", "[::1]")


def run_bridge_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    allow_remote: bool = False,
    token: str | None = None,
) -> None:
    if not is_loopback(host) and not allow_remote:
        raise ValueError(
            f"Refusing to bind HTTP bridge to non-loopback interface '{host}' without explicit '--allow-remote' flag."
        )

    resolved_token = token or os.environ.get("SPECSYNTH_BRIDGE_TOKEN")
    if allow_remote and not resolved_token:
        import secrets
        resolved_token = secrets.token_hex(16)
        print(f"[SECURITY WARNING] Binding to remote interface {host} without user token. Generated ephemeral token: {resolved_token}")

    BridgeHTTPHandler.server_instance = SpecsynthMCPServer()
    BridgeHTTPHandler.auth_token = resolved_token
    BridgeHTTPHandler.allow_remote = allow_remote

    server_address = (host, port)
    httpd = HTTPServer(server_address, BridgeHTTPHandler)
    auth_status = f"Enforced (Token: {resolved_token[:6]}...)" if resolved_token else "Disabled (Loopback Only)"
    banner = f"""
================================================================================
  Perandam-Psi (PSI) - SpecSynth Scientific Engine & HTTP Bridge v1.0.0
================================================================================
  * Local Engine URL   : http://{host}:{port}
  * Web Explorer UI    : http://localhost:5173 (Dev) or http://{host}:{port} (Prod)
  * Authentication     : {auth_status}
  * Active Endpoints   : /api/health, /api/filters, /api/system, /api/inspect, /api/audit
  * MCP Tool Endpoint  : POST /api/tools/call
  * Status             : Online & streaming live logs below
================================================================================
"""
    print(banner.strip())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Perandam-Psi HTTP Bridge.")
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PerandamΨ SpecSynth HTTP Bridge.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--allow-remote", action="store_true", help="Allow binding to non-loopback interfaces")
    parser.add_argument("--token", default=None, help="Bearer token for HTTP authentication (or via SPECSYNTH_BRIDGE_TOKEN)")
    args = parser.parse_args()
    run_bridge_server(host=args.host, port=args.port, allow_remote=args.allow_remote, token=args.token)


if __name__ == "__main__":
    main()
