"""Unit tests for port conflict detection and available port finder."""

from runrepo.services.ports import find_available_port, is_port_in_use


def test_is_port_in_use_closed_port():
    # High port unlikely to be open
    assert is_port_in_use(59998) is False


def test_find_available_port_default():
    port = find_available_port(59000)
    assert port >= 59000
