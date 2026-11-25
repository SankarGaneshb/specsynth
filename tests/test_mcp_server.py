"""
Unit and integration tests for specsynth.mcp: Model Context Protocol Server and HTTP Bridge.
Covers stdio JSON-RPC 2.0 handshake, tool enumeration, M8ven safety annotations, and tool calls.
"""

from __future__ import annotations

import io
import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest

from specsynth.mcp.bridge import BridgeHTTPHandler
from specsynth.mcp.server import SpecsynthMCPServer, _run_fallback_jsonrpc


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
    assert "sps_remediate_catalog" in tool_names
    assert "sps_load_tng_demo" in tool_names
    assert "sps_get_system_info" in tool_names

    for tool in tools:
        assert "annotations" in tool
        ann = tool["annotations"]
        for flag in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            assert flag in ann
            assert isinstance(ann[flag], bool)


def test_mcp_fallback_jsonrpc_list_and_call() -> None:
    """
    Stdio JSON-RPC 2.0 handshake, tool enumeration, annotation structure, and tool invocation.
    Simulates IDE agent interactions (Cursor, Antigravity, Claude Desktop) through stdio streams.
    """
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "sps_list_filters", "arguments": {"instrument": "jwst_nircam"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "sps_get_system_info", "arguments": {}},
        },
    ]

    input_text = "\n".join(json.dumps(r) for r in reqs) + "\n"
    stdin_stream = io.StringIO(input_text)
    stdout_stream = io.StringIO()

    _run_fallback_jsonrpc(stdin=stdin_stream, stdout=stdout_stream)

    lines = [ln.strip() for ln in stdout_stream.getvalue().splitlines() if ln.strip()]
    # Handshake + tools/list + 2 calls = 4 responses (notification has no response)
    assert len(lines) == 4

    responses = [json.loads(line) for line in lines]

    # 1. Initialize response
    r1 = responses[0]
    assert r1["id"] == 1
    assert r1["result"]["serverInfo"]["name"] == "specsynth-mcp"

    # 2. Tools list response
    r2 = responses[1]
    assert r2["id"] == 2
    tools = r2["result"]["tools"]
    assert len(tools) >= 6
    for t in tools:
        ann = t["annotations"]
        assert isinstance(ann["readOnlyHint"], bool)
        assert isinstance(ann["destructiveHint"], bool)
        assert isinstance(ann["idempotentHint"], bool)
        assert isinstance(ann["openWorldHint"], bool)

    # 3. Tool call sps_list_filters
    r3 = responses[2]
    assert r3["id"] == 3
    assert r3["result"]["content"][0]["type"] == "text"
    filters_data = json.loads(r3["result"]["content"][0]["text"])
    assert filters_data["filter_set"] == "jwst_nircam"

    # 4. Tool call sps_get_system_info
    r4 = responses[3]
    assert r4["id"] == 4
    assert r4["result"]["content"][0]["type"] == "text"
    sys_data = json.loads(r4["result"]["content"][0]["text"])
    assert "cpu_logical_cores" in sys_data or "os" in sys_data or "python_version" in sys_data


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
    assert ("result" in resp) ^ ("error" in resp)
    assert "error" in resp
    assert "result" not in resp
    assert resp["error"]["code"] == -32601
    assert "Unknown tool" in resp["error"]["message"]


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

        # Test /api/system
        conn.request("GET", "/api/system")
        res3 = conn.getresponse()
        assert res3.status == 200
        data3 = json.loads(res3.read().decode("utf-8"))
        assert "os" in data3 or "cpu_arch" in data3

        # Test POST /api/tools/call
        post_payload = json.dumps({
            "name": "sps_list_filters",
            "arguments": {"instrument": "jwst_nircam"}
        }).encode("utf-8")
        conn.request("POST", "/api/tools/call", body=post_payload, headers={"Content-Type": "application/json"})
        res4 = conn.getresponse()
        assert res4.status == 200
        data4 = json.loads(res4.read().decode("utf-8"))
        assert "result" in data4

        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
