"""Unit tests for NetworkDiagnostics probe and DNS resolution."""

import socket
from unittest.mock import patch
from runrepo.diagnostics.network import NetworkDiagnostics


def test_probe_localhost_success():
    # Bind a temporary test socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    try:
        ok, err = NetworkDiagnostics.probe_localhost(port=port)
        assert ok is True
        assert err is None
    finally:
        server_sock.close()


def test_probe_localhost_connection_refused():
    # Find an unused port and probe it
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.close()

    ok, err = NetworkDiagnostics.probe_localhost(port=port)
    assert ok is False
    assert err is not None
    assert any(k in err.lower() for k in ("refused", "failed", "timed out", "timeout"))


def test_dns_resolution_failure():
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Name or service not known")):
        ok, err = NetworkDiagnostics.check_dns("nonexistent.domain.invalid")
        assert ok is False
        assert "DNS resolution failed" in err
