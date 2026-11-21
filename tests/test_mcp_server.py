"""
Unit and integration tests for specsynth.mcp: Model Context Protocol Server and HTTP Bridge.
"""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest

from specsynth.mcp.bridge import BridgeHTTPHandler
from specsynth.mcp.server import SpecsynthMCPServer


def test_mcp_server_initialize() -> None:
    server = SpecsynthMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    resp = server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "specsynth-mcp"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_server_tools_list() -> None:
    server = SpecsynthMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = server.handle_request(req)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "sps_list_filters" in tool_names
    assert "sps_inspect_galaxy" in tool_names
    assert "sps_run_sentry_audit" in tool_names
    assert "sps_load_tng_demo" in tool_names


def test_mcp_server_tool_call_list_filters() -> None:
    server = SpecsynthMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "sps_list_filters",
            "arguments": {"instrument": "jwst_nircam"},
        },
    }
    resp = server.handle_request(req)
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["filter_set"] == "jwst_nircam"
    assert len(content["filters"]) >= 6


def test_mcp_server_tool_call_tng_demo() -> None:
    server = SpecsynthMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "sps_load_tng_demo",
            "arguments": {"limit": 3},
        },
    }
    resp = server.handle_request(req)
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    if Path("data/examples/tng_sample/sample_catalog.parquet").exists():
        assert "dataset" in content
        assert content["total_galaxies"] > 0
        assert len(content["sample_galaxies"]) == 3


def test_mcp_server_unknown_tool() -> None:
    server = SpecsynthMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "non_existent_tool", "arguments": {}},
    }
    resp = server.handle_request(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_http_bridge_live_endpoints() -> None:
    from http.server import HTTPServer
    
    server_address = ("127.0.0.1", 18888)
    BridgeHTTPHandler.server_instance = SpecsynthMCPServer()
    httpd = HTTPServer(server_address, BridgeHTTPHandler)
    
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        conn = HTTPConnection("127.0.0.1", 18888)
        
        # Test /api/health
        conn.request("GET", "/api/health")
        res = conn.getresponse()
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["service"] == "specsynth-mcp-bridge"
        assert data["mark"] == "PerandamΨ"

        # Test /api/filters
        conn.request("GET", "/api/filters?instrument=jwst_nircam")
        res2 = conn.getresponse()
        assert res2.status == 200
        data2 = json.loads(res2.read().decode("utf-8"))
        assert data2["filter_set"] == "jwst_nircam"

        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
