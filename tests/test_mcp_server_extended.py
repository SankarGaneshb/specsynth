"""
Extended test suite for specsynth.mcp Model Context Protocol (MCP) server.

Covers:
- FastMCP server lifecycle, registration, and tool annotations mocking/introspection.
- Full 7-request JSON-RPC sequential batching and stdio stream compliance.
- M8ven Trust Index safety contract and risk vocabulary verification across all tools.
- Negative testing: malformed JSON, unknown tools, unknown methods, and exception resilience.
"""

from __future__ import annotations

import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from specsynth.mcp.server import (
    MCP_TOOL_ANNOTATIONS,
    SpecsynthMCPServer,
    _run_fallback_jsonrpc,
    create_fastmcp_server,
    run_mcp_server,
)


def test_mcp_server_fastmcp_run() -> None:
    """
    Test FastMCP server lifecycle: verifies FastMCP initialization, tool decorator
    registration with ToolAnnotations, and server startup via mcp.run().
    """
    mock_fastmcp_class = MagicMock()
    mock_fastmcp_instance = MagicMock()
    mock_fastmcp_class.return_value = mock_fastmcp_instance

    mock_tool_annotations_class = MagicMock()

    # Track registered tools
    registered_tools = {}

    def mock_tool_decorator(**kwargs):
        def decorator(fn):
            name = kwargs.get("name", fn.__name__)
            registered_tools[name] = {
                "fn": fn,
                "description": kwargs.get("description"),
                "annotations": kwargs.get("annotations"),
            }
            return fn
        return decorator

    mock_fastmcp_instance.tool.side_effect = mock_tool_decorator

    mock_fastmcp_module = MagicMock()
    mock_fastmcp_module.FastMCP = mock_fastmcp_class
    mock_types_module = MagicMock()
    mock_types_module.ToolAnnotations = mock_tool_annotations_class

    with patch.dict(sys.modules, {
        "mcp": MagicMock(),
        "mcp.server": MagicMock(),
        "mcp.server.fastmcp": mock_fastmcp_module,
        "mcp.types": mock_types_module,
    }):
        server = create_fastmcp_server()
        assert server == mock_fastmcp_instance

        # Verify all tools registered
        expected_tools = [
            "sps_list_filters",
            "sps_inspect_galaxy",
            "sps_run_sentry_audit",
            "sps_remediate_catalog",
            "sps_load_tng_demo",
            "sps_get_system_info",
        ]
        for tool_name in expected_tools:
            assert tool_name in registered_tools
            ann = registered_tools[tool_name]["annotations"]
            assert ann is not None

        # Verify run_mcp_server with fastmcp mode triggers mcp.run()
        run_mcp_server(mode="fastmcp")
        mock_fastmcp_instance.run.assert_called_once()


def test_mcp_fallback_jsonrpc() -> None:
    """
    Full 7-request JSON-RPC batching test over simulated stdio.
    Verifies sequential multi-request stream handling, ID matching (id: 1..6),
    valid JSON-RPC 2.0 response format (result.content[0].type == "text"),
    and unknown tool negative handling without crashing.
    """
    batch_requests = [
        # 1. Handshake initialize
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        # 2. Handshake initialized notification (no response)
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        # 3. Tool enumeration
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        # 4. Tool call 1: sps_list_filters
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "sps_list_filters", "arguments": {"instrument": "jwst_nircam"}},
        },
        # 5. Tool call 2: sps_get_system_info
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "sps_get_system_info", "arguments": {}},
        },
        # 6. Tool call 3: sps_load_tng_demo
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "sps_load_tng_demo", "arguments": {"limit": 2}},
        },
        # 7. Tool call 4: invalid_tool (negative test)
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "invalid_tool", "arguments": {}},
        },
    ]

    input_data = "\n".join(json.dumps(r) for r in batch_requests) + "\n"
    stdin_stream = io.StringIO(input_data)
    stdout_stream = io.StringIO()

    _run_fallback_jsonrpc(stdin=stdin_stream, stdout=stdout_stream)

    raw_output = stdout_stream.getvalue().strip()
    lines = [ln for ln in raw_output.splitlines() if ln.strip()]

    # Total requests = 7 (6 calls with ID + 1 notification) -> exactly 6 responses
    assert len(lines) == 6

    responses = [json.loads(ln) for ln in lines]

    # Verify ID matching and JSON-RPC 2.0 version
    assert responses[0]["id"] == 1
    assert responses[0]["jsonrpc"] == "2.0"
    assert responses[0]["result"]["serverInfo"]["name"] == "specsynth-mcp"

    assert responses[1]["id"] == 2
    assert responses[1]["jsonrpc"] == "2.0"
    tools = responses[1]["result"]["tools"]
    assert len(tools) >= 6

    assert responses[2]["id"] == 3
    assert responses[2]["jsonrpc"] == "2.0"
    assert responses[2]["result"]["content"][0]["type"] == "text"

    assert responses[3]["id"] == 4
    assert responses[3]["jsonrpc"] == "2.0"
    assert responses[3]["result"]["content"][0]["type"] == "text"

    assert responses[4]["id"] == 5
    assert responses[4]["jsonrpc"] == "2.0"
    assert responses[4]["result"]["content"][0]["type"] == "text"

    # Unknown tool handling
    r_unknown = responses[5]
    assert r_unknown["id"] == 6
    assert r_unknown["jsonrpc"] == "2.0"
    assert ("result" in r_unknown) ^ ("error" in r_unknown)
    assert "error" in r_unknown
    assert "result" not in r_unknown
    assert r_unknown["error"]["code"] == -32601
    assert "Unknown tool" in r_unknown["error"]["message"]


def test_fastmcp_real_tool_annotations() -> None:
    """
    Verify safety annotations against official MCP risk vocabulary & M8ven Trust Index:
    readOnlyHint, destructiveHint, idempotentHint, openWorldHint.
    """
    server = SpecsynthMCPServer()

    # Verify presence and boolean types on all registered tools
    for name, tool in server.tools.items():
        ann = tool.get("annotations")
        assert ann is not None, f"Tool {name} must have annotations"
        assert isinstance(ann.get("readOnlyHint"), bool)
        assert isinstance(ann.get("destructiveHint"), bool)
        assert isinstance(ann.get("idempotentHint"), bool)
        assert isinstance(ann.get("openWorldHint"), bool)

    # Safety Contract: Read-only inspection tools
    read_only_tools = [
        "sps_list_filters",
        "sps_inspect_galaxy",
        "sps_run_sentry_audit",
        "sps_load_tng_demo",
        "sps_get_system_info",
    ]
    for t_name in read_only_tools:
        ann = server.tools[t_name]["annotations"]
        assert ann["readOnlyHint"] is True, f"{t_name} must be readOnly"
        assert ann["destructiveHint"] is False, f"{t_name} must not be destructive"
        assert ann["idempotentHint"] is True, f"{t_name} must be idempotent"
        assert ann["openWorldHint"] is False, f"{t_name} must have openWorldHint False"

    # Safety Contract: Mutation / remediation tool
    remediate_ann = server.tools["sps_remediate_catalog"]["annotations"]
    assert remediate_ann["readOnlyHint"] is False, "remediate_catalog is not readOnly"
    assert remediate_ann["destructiveHint"] is True, "remediate_catalog triggers confirmation prompts"
    assert remediate_ann["idempotentHint"] is False
    assert remediate_ann["openWorldHint"] is False


def test_mcp_malformed_json_handling() -> None:
    """
    Negative testing: Malformed JSON strings return JSON-RPC 2.0 parse error (-32700)
    without crashing the stdio server process.
    """
    input_data = "{ invalid json line }\n"
    stdin_stream = io.StringIO(input_data)
    stdout_stream = io.StringIO()

    _run_fallback_jsonrpc(stdin=stdin_stream, stdout=stdout_stream)

    output = stdout_stream.getvalue().strip()
    assert output, "Server must output error response for malformed JSON"
    resp = json.loads(output)
    assert resp["jsonrpc"] == "2.0"
    assert resp["error"]["code"] == -32700
    assert "Parse error" in resp["error"]["message"]


def test_mcp_unknown_method_handling() -> None:
    """
    Negative testing: Unknown method returns Method not found (-32601).
    """
    server = SpecsynthMCPServer()
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 42,
        "method": "unsupported/method",
        "params": {},
    })
    assert resp["id"] == 42
    assert resp["error"]["code"] == -32601
    assert "Method 'unsupported/method' not found" in resp["error"]["message"]


def test_mcp_tool_execution_exception_handling() -> None:
    """
    Negative testing: Exception inside a tool handler returns error code -32000
    with error description rather than raising an unhandled exception.
    """
    server = SpecsynthMCPServer()

    with patch.dict(server.tools["sps_inspect_galaxy"], {
        "handler": MagicMock(side_effect=RuntimeError("Zarr store corruption simulated")),
    }):
        resp = server.handle_request({
            "jsonrpc": "2.0",
            "id": 88,
            "method": "tools/call",
            "params": {"name": "sps_inspect_galaxy", "arguments": {"galaxy_idx": 0}},
        })

        assert resp["id"] == 88
        assert ("result" in resp) ^ ("error" in resp)
        assert "error" in resp
        assert "result" not in resp
        assert resp["error"]["code"] == -32000
        assert "Zarr store corruption simulated" in resp["error"]["message"]
