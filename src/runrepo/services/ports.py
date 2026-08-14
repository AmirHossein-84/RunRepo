"""Port conflict detection and allocation helper."""

import socket


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently occupied by any process or container on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        result = sock.connect_ex((host, port))
        return result == 0


def find_available_port(starting_port: int, max_attempts: int = 50, host: str = "127.0.0.1") -> int:
    """Find the first available TCP port starting from `starting_port`."""
    for port in range(starting_port, starting_port + max_attempts):
        if not is_port_in_use(port, host=host):
            return port
    return starting_port
