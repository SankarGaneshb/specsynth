"""
Security and path-containment unit tests for specsynth.mcp.bridge HTTP server.
"""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from specsynth.mcp.bridge import BridgeHTTPHandler


class DummyRequest:
    def __init__(self, raw_http: bytes):
        self.raw = raw_http
        self.rfile = BytesIO(raw_http)
        self.wfile = BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self.rfile
        elif "w" in mode or "b" in mode:
            return self.wfile
        return self.wfile

    def sendall(self, data):
        self.wfile.write(data)


def test_bridge_cors_restriction() -> None:
    """Verifies that CORS origins are restricted to localhost and do not wildcard '*'."""
    req_bytes = b"GET /api/health HTTP/1.1\r\nHost: localhost:8000\r\nOrigin: http://evil.com\r\n\r\n"
    sock = DummyRequest(req_bytes)
    server = MagicMock()

    handler = BridgeHTTPHandler(sock, ("127.0.0.1", 54321), server)
    out = sock.wfile.getvalue().decode("utf-8")
    assert "Access-Control-Allow-Origin: http://localhost:5173" in out
    assert "Access-Control-Allow-Origin: *" not in out


def test_bridge_cors_localhost_allowed() -> None:
    """Verifies that localhost / 127.0.0.1 origins are permitted in CORS headers."""
    req_bytes = b"GET /api/health HTTP/1.1\r\nHost: localhost:8000\r\nOrigin: http://localhost:3000\r\n\r\n"
    sock = DummyRequest(req_bytes)
    server = MagicMock()

    handler = BridgeHTTPHandler(sock, ("127.0.0.1", 54321), server)
    out = sock.wfile.getvalue().decode("utf-8")
    assert "Access-Control-Allow-Origin: http://localhost:3000" in out


def test_bridge_path_traversal_blocked() -> None:
    """Verifies that path traversal attacks targeting files outside dist/ return 403 Forbidden."""
    req_bytes = b"GET /../../../../setup.py HTTP/1.1\r\nHost: localhost:8000\r\n\r\n"
    sock = DummyRequest(req_bytes)
    server = MagicMock()

    handler = BridgeHTTPHandler(sock, ("127.0.0.1", 54321), server)
    out = sock.wfile.getvalue().decode("utf-8")
    assert "403 Forbidden" in out
