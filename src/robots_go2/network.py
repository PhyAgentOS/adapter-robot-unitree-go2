"""Network-interface checks used before opening Unitree DDS."""

from __future__ import annotations

import re
import socket
import subprocess


def resolve_robot_network(configured: str) -> str:
    """Resolve an explicit interface or the sole 192.168.123.x interface."""
    available = {name for _, name in socket.if_nameindex()}
    if configured and configured != "auto":
        if configured not in available:
            raise RuntimeError(f"网卡不存在: {configured}")
        return configured

    result = subprocess.run(
        ["ip", "-o", "-4", "addr", "show"],
        check=True,
        capture_output=True,
        text=True,
    )
    matches: set[str] = set()
    for line in result.stdout.splitlines():
        match = re.search(
            r"^\d+:\s+(\S+)\s+.*\binet\s+192\.168\.123\.\d+/",
            line,
        )
        if match:
            matches.add(match.group(1))
    if len(matches) != 1:
        raise RuntimeError(
            "network_interface=auto 要求恰好一个网卡拥有 "
            f"192.168.123.x 地址，当前={sorted(matches)}"
        )
    return next(iter(matches))
