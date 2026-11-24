"""
Extended CLI test suite for specsynth CLI commands, including the MCP server subcommand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

from specsynth.cli import build_parser, main


def test_cli_mcp_command() -> None:
    """
    Verify CLI runner invocation for the 'specsynth mcp' subcommand.
    Pipes an initialize request followed by EOF to verify clean startup, response, and shutdown (exit code 0).
    """
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    input_text = json.dumps(req) + "\n"

    cmd = [sys.executable, "specsynth.py", "mcp", "--mode", "fallback"]
    proc = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert proc.returncode == 0, f"specsynth mcp failed with stderr: {proc.stderr}"
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) >= 1
    resp = json.loads(lines[0])
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "specsynth-mcp"


def test_cli_mcp_parser_and_defaults() -> None:
    """
    Verify argument parser configuration for the 'mcp' subcommand.
    """
    ap = build_parser()
    args = ap.parse_args(["mcp"])
    assert args.cmd == "mcp"
    assert args.mode == "auto"

    args_fallback = ap.parse_args(["mcp", "--mode", "fallback"])
    assert args_fallback.mode == "fallback"

    args_fast = ap.parse_args(["mcp", "--mode", "fastmcp"])
    assert args_fast.mode == "fastmcp"
