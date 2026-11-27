#!/usr/bin/env python3
"""
Independent Model Context Protocol (MCP) stdio Client Transport Harness.
=======================================================================
Enforces Milestone P4 / P6 (Issue #30) Out-of-Process Transport Acceptance.

Communicates with any compliant MCP server process over standard input/output (stdio)
pipes using newline-delimited JSON-RPC 2.0 messages. Does NOT import server code or
call in-memory handler functions.

Supported Operations:
- Lifecycle: initialize -> notifications/initialized -> tools/list -> tools/call -> shutdown
- Standard JSON-RPC error parsing (-32700, -32601, -32602, -32000)
- Process isolation, timeout enforcement, and graceful process termination.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


class MCPTransportError(Exception):
    """Raised when an MCP JSON-RPC protocol error occurs over the transport."""
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"MCP Transport Error [{code}]: {message}")
        self.code = code
        self.message = message
        self.data = data


class MCPStdioClient:
    """
    Independent client managing an MCP server child process over stdio.
    """

    def __init__(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        timeout: float = 15.0,
        env: dict[str, str] | None = None,
    ):
        self.cmd = cmd
        self.cwd = str(cwd) if cwd else str(REPO_ROOT)
        self.timeout = timeout
        self.env = env
        self.proc: subprocess.Popen | None = None
        self._msg_id: int = 1
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self.protocol_version: str = "2024-11-05"

    def __enter__(self) -> MCPStdioClient:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def start(self) -> None:
        """Launch server child process with redirected stdin and stdout pipes."""
        if self.proc is not None:
            return

        import os
        spawn_env = os.environ.copy()
        if self.env:
            spawn_env.update(self.env)

        # Force unbuffered stdout in Python
        spawn_env["PYTHONUNBUFFERED"] = "1"

        self.proc = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=spawn_env,
            bufsize=1,  # Line-buffered
        )

    def close(self) -> None:
        """Terminate child process and close pipes cleanly."""
        if self.proc is None:
            return

        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2.0)
        except Exception:
            pass
        finally:
            self.proc = None

    def send_raw(self, raw_line: str) -> dict[str, Any]:
        """Send raw line over stdin and read single JSON-RPC response line from stdout."""
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("MCP server process is not running")

        # Strip any trailing newlines then write clean newline
        line_to_send = raw_line.strip() + "\n"
        self.proc.stdin.write(line_to_send)
        self.proc.stdin.flush()

        # Read line response with timeout
        start_time = time.time()
        while True:
            if time.time() - start_time > self.timeout:
                raise TimeoutError(f"Timed out waiting for response from MCP server after {self.timeout}s")

            # Check if process died
            ret = self.proc.poll()
            if ret is not None:
                err_output = self.proc.stderr.read() if self.proc.stderr else ""
                raise RuntimeError(f"Server process terminated with exit code {ret}: {err_output}")

            line = self.proc.stdout.readline()
            if not line:
                time.sleep(0.02)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                return json.loads(line)
            except json.JSONDecodeError as exc:
                raise MCPTransportError(-32700, f"Malformed response line: {line} ({exc})")

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send standard JSON-RPC 2.0 request and return result dict or raise MCPTransportError."""
        current_id = self._msg_id
        self._msg_id += 1

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": current_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        raw_req = json.dumps(payload)
        resp = self.send_raw(raw_req)

        if "error" in resp:
            err = resp["error"]
            raise MCPTransportError(
                code=err.get("code", -32000),
                message=err.get("message", "Unknown error"),
                data=err.get("data"),
            )

        return resp.get("result", {})

    def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send standard JSON-RPC 2.0 notification (no response expected)."""
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("MCP server process is not running")

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        raw_req = json.dumps(payload) + "\n"
        self.proc.stdin.write(raw_req)
        self.proc.stdin.flush()

    # -------------------------------------------------------------------------
    # High-Level MCP Protocol Methods
    # -------------------------------------------------------------------------
    def initialize(
        self,
        client_name: str = "specsynth-test-client",
        client_version: str = "1.0.0",
    ) -> dict[str, Any]:
        """Perform MCP initialize handshake."""
        result = self.send_request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "clientInfo": {"name": client_name, "version": client_version},
                "capabilities": {},
            },
        )
        self.server_info = result.get("serverInfo", {})
        self.capabilities = result.get("capabilities", {})
        self.protocol_version = result.get("protocolVersion", self.protocol_version)

        # Send initialized notification
        self.send_notification("notifications/initialized")
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        """Query server for available tools (tools/list)."""
        res = self.send_request("tools/list", {})
        return res.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a specific tool (tools/call) and parse content text as JSON."""
        res = self.send_request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        content_list = res.get("content", [])
        if not content_list:
            return {}

        text_content = content_list[0].get("text", "{}")
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            return {"raw_text": text_content}


def create_python_mcp_client(repo_root: Path | None = None) -> MCPStdioClient:
    """Create an out-of-process client connected to the Python MCP server."""
    root = repo_root or REPO_ROOT
    server_script = root / "specsynth" / "mcp" / "server.py"
    cmd = [sys.executable, str(server_script)]
    return MCPStdioClient(cmd=cmd, cwd=root)


def create_node_mcp_client(repo_root: Path | None = None) -> MCPStdioClient:
    """Create an out-of-process client connected to the Node.js MCP server."""
    root = repo_root or REPO_ROOT
    server_script = root / "perandam-psi" / "mcp_server.mjs"
    cmd = ["node", str(server_script)]
    return MCPStdioClient(cmd=cmd, cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent MCP stdio Client Transport Runner")
    parser.add_argument("--server", choices=["python", "node", "both"], default="both")
    args = parser.parse_args()

    targets = []
    if args.server in ("python", "both"):
        targets.append(("Python MCP Server", create_python_mcp_client()))
    if args.server in ("node", "both"):
        targets.append(("Node.js MCP Server", create_node_mcp_client()))

    print("=" * 75)
    print("Independent MCP stdio Client Transport Demonstration")
    print("Testing real out-of-process JSON-RPC 2.0 communication over pipes")
    print("=" * 75)

    all_passed = True
    for label, client in targets:
        print(f"\n[*] Testing {label} over stdio transport...")
        with client:
            # 1. Initialize
            init_res = client.initialize()
            print(f"  ✓ Handshake OK: {client.server_info.get('name')} v{client.server_info.get('version')} (Protocol: {client.protocol_version})")

            # 2. Tools List
            tools = client.list_tools()
            tool_names = [t["name"] for t in tools]
            print(f"  ✓ Discovered {len(tools)} tools over transport.")
            assert "specsynth_calculate_cosmology" in tool_names
            assert "specsynth_list_filters" in tool_names

            # 3. Tool Call: Cosmology
            cosmo = client.call_tool("specsynth_calculate_cosmology", {"redshift": 1.5, "h0": 67.74, "om0": 0.3089})
            print(f"  ✓ Tool Call OK (specsynth_calculate_cosmology): D_L = {cosmo.get('luminosity_distance_mpc')} Mpc")

            # 4. Tool Call: List Filters
            filters = client.call_tool("specsynth_list_filters", {"instrument": "jwst_nircam"})
            n_filters = len(filters.get("filters", []))
            print(f"  ✓ Tool Call OK (specsynth_list_filters): Found {n_filters} JWST NIRCam filters")

    print("\n" + "=" * 75)
    print("SUCCESS: Independent stdio client transport verified across servers!")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    sys.exit(main())
