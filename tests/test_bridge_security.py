"""
Security & Integrity Test Suite for SpecSynth HTTP Bridge & MCP Tools.

Validates:
- Non-loopback binding refusal without explicit --allow-remote
- Bearer token authentication enforcement (401 on missing/invalid, 200 on valid)
- X-Specsynth-Token header support
- Guarding destructive sps_remediate_catalog tool behind confirm_destructive=True
"""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer
from unittest.mock import MagicMock, patch

import pytest

from specsynth.mcp.bridge import BridgeHTTPHandler, is_loopback, run_bridge_server
from specsynth.mcp.server import SpecsynthMCPServer


def test_is_loopback_classification():
    """Verify loopback addresses are accurately recognized."""
    assert is_loopback("127.0.0.1")
    assert is_loopback("localhost")
    assert is_loopback("::1")
    assert is_loopback("[::1]")

    assert not is_loopback("0.0.0.0")
    assert not is_loopback("192.168.1.100")
    assert not is_loopback("10.0.0.1")
    assert not is_loopback("8.8.8.8")
    assert not is_loopback("example.com")


def test_run_bridge_server_refuses_non_loopback_without_allow_remote():
    """Refuse to bind to external interface without --allow-remote."""
    with pytest.raises(ValueError, match="Refusing to bind HTTP bridge to non-loopback interface"):
        run_bridge_server(host="0.0.0.0", port=8999, allow_remote=False)

    with pytest.raises(ValueError, match="Refusing to bind HTTP bridge to non-loopback interface"):
        run_bridge_server(host="192.168.1.50", port=8999, allow_remote=False)


def test_http_bridge_bearer_token_enforcement(tmp_path):
    """Test 401 Unauthorized when token is missing/invalid, 200 when valid."""
    port = 18991
    server_address = ("127.0.0.1", port)

    secret_token = "secure-specsynth-test-token-xyz123"
    BridgeHTTPHandler.server_instance = SpecsynthMCPServer()
    BridgeHTTPHandler.auth_token = secret_token
    BridgeHTTPHandler.allow_remote = True

    httpd = HTTPServer(server_address, BridgeHTTPHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{port}/api/health"

        # 1. Unauthenticated request -> 401
        req_unauth = urllib.request.Request(url)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_unauth)
        assert exc_info.value.code == 401

        # 2. Invalid Bearer token -> 401
        req_bad = urllib.request.Request(url, headers={"Authorization": "Bearer wrong-token"})
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_bad)
        assert exc_info.value.code == 401

        # 3. Valid Bearer token -> 200
        req_ok = urllib.request.Request(url, headers={"Authorization": f"Bearer {secret_token}"})
        with urllib.request.urlopen(req_ok) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"

        # 4. Valid X-Specsynth-Token -> 200
        req_header_ok = urllib.request.Request(url, headers={"X-Specsynth-Token": secret_token})
        with urllib.request.urlopen(req_header_ok) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"

    finally:
        httpd.shutdown()
        httpd.server_close()
        BridgeHTTPHandler.auth_token = None
        BridgeHTTPHandler.allow_remote = False


def test_sps_remediate_catalog_requires_explicit_confirmation():
    """Verify destructive catalog remediation is blocked unless confirm_destructive=True."""
    server = SpecsynthMCPServer()

    # 1. Without confirmation flag
    res_blocked = server.handle_request({
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "sps_remediate_catalog",
            "arguments": {"base": "./run"},
        },
    })
    # Must return error object or result indicating error
    content_str = str(res_blocked)
    assert "confirm_destructive" in content_str
    assert "Destructive operation aborted" in content_str or "confirm_destructive': true is required" in content_str

    # 2. With confirm_destructive=False
    res_blocked_false = server.handle_request({
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {
            "name": "sps_remediate_catalog",
            "arguments": {"base": "./run", "confirm_destructive": False},
        },
    })
    content_str_false = str(res_blocked_false)
    assert "Destructive operation aborted" in content_str_false

    # 3. With confirm_destructive=True (mocking the underlying cleaner)
    with patch("specsynth.mcp.server.tool_clean_catalog") as mock_clean:
        mock_clean.return_value = {"status": "SUCCESS", "purged": 5}
        res_confirmed = server.handle_request({
            "jsonrpc": "2.0",
            "id": 103,
            "method": "tools/call",
            "params": {
                "name": "sps_remediate_catalog",
                "arguments": {"base": "./run", "confirm_destructive": True},
            },
        })
        assert "error" not in res_confirmed
        assert "result" in res_confirmed
        mock_clean.assert_called_once()
