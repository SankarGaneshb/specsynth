"""
Lightweight Zero-Dependency Local HTTP Bridge for SpecSynth & PerandamΨ.
Serves REST endpoints on localhost:8000 for the PerandamΨ Web UI.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any, Dict

from specsynth.filters import FILTER_SETS, STANDARD_FILTER_SPECS
from specsynth.mcp.server import SpecsynthMCPServer

logger = logging.getLogger("specsynth.bridge")


class BridgeHTTPHandler(BaseHTTPRequestHandler):
    """CORS-enabled HTTP request handler for the PerandamΨ frontend."""

    server_instance: SpecsynthMCPServer | None = None

    def _set_cors_headers(self, status_code: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status_code)
        origin = self.headers.get("Origin", "") if hasattr(self, "headers") and self.headers else ""
        allowed_prefixes = ("http://localhost", "http://127.0.0.1", "http://[::1]")
        if any(origin.startswith(p) for p in allowed_prefixes):
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_cors_headers(204)

    def do_GET(self) -> None:
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
            print(f"[{now}] [Engine Heartbeat] GET /api/health -> 200 OK (PerandamΨ connected)")

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
            idx = int(query.get("galaxy_idx", [0])[0])
            base = query.get("base", ["./run"])[0]
            data = mcp._tool_inspect_galaxy({"base": base, "galaxy_idx": idx})
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            print(f"[{now}] [Inspect API] GET /api/inspect (galaxy_idx={idx}, base={base}) -> 200 OK")

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

        else:
            self._set_cors_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found"}).encode("utf-8"))
            print(f"[{now}] [404 Not Found] GET {path}")

    def do_POST(self) -> None:
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

        if path == "/api/tools/call":
            tool_name = data.get("name")
            tool_args = data.get("arguments", {})
            resp = mcp.handle_request({
                "jsonrpc": "2.0",
                "id": "http-bridge",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": tool_args},
            })
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            print(f"[{now}] [MCP Tool Dispatch] POST /api/tools/call -> tool: '{tool_name}' -> 200 OK")

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


def run_bridge_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server_address = (host, port)
    BridgeHTTPHandler.server_instance = SpecsynthMCPServer()
    httpd = HTTPServer(server_address, BridgeHTTPHandler)
    banner = f"""
================================================================================
  PerandamΨ (PSI) — SpecSynth Scientific Engine & HTTP Bridge v1.0.0
================================================================================
  * Local Engine URL   : http://{host}:{port}
  * Web Explorer UI    : http://localhost:5173 (Dev) or http://{host}:{port} (Prod)
  * Active Endpoints   : /api/health, /api/filters, /api/system, /api/inspect, /api/audit
  * MCP Tool Endpoint  : POST /api/tools/call
  * Status             : Online & streaming live logs below
================================================================================
"""
    print(banner.strip())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down PerandamΨ HTTP Bridge.")
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PerandamΨ SpecSynth HTTP Bridge.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    args = parser.parse_args()
    run_bridge_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
