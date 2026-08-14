"""Unit tests for PortDiagnostics port availability and process ownership detection."""

import socket
from unittest.mock import MagicMock, patch
from runrepo.diagnostics.network import PortDiagnostics, PortOwnerInfo


def test_check_port_availability_free_port():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.close()

    available, owner = PortDiagnostics.check_port_availability(port=port)
    assert available is True
    assert owner is None


def test_check_port_availability_occupied_port():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    try:
        available, owner = PortDiagnostics.check_port_availability(port=port)
        assert available is False
    finally:
        server_sock.close()


def test_windows_netstat_parsing():
    mock_netstat_output = """
    Active Connections

      Proto  Local Address          Foreign Address        State           PID
      TCP    0.0.0.0:5432           0.0.0.0:0              LISTENING       4321
      TCP    127.0.0.1:6379         0.0.0.0:0              LISTENING       8765
    """

    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = mock_netstat_output

    with patch("subprocess.run", return_value=mock_run):
        with patch.object(PortDiagnostics, "_get_process_name_windows", return_value="postgres.exe"):
            owner = PortDiagnostics._get_port_owner_windows(5432)
            assert owner is not None
            assert owner.port == 5432
            assert owner.pid == 4321
            assert owner.process_name == "postgres.exe"
