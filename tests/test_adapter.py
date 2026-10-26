from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pyarrow as pa

from robots_unitree_go2 import main as adapter


ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def BalanceStand(self) -> int:
        self.calls.append(("BalanceStand",))
        return 0

    def Move(self, vx: float, vy: float, wz: float) -> int:
        self.calls.append(("Move", vx, vy, wz))
        return 0

    def StopMove(self) -> int:
        self.calls.append(("StopMove",))
        return 0


def command(vx: float, vy: float, wz: float) -> pa.RecordBatch:
    return pa.RecordBatch.from_pydict(
        {"vx": [vx], "vy": [vy], "wz": [wz], "timestamp": [100.0]}
    )


def config() -> adapter.Config:
    return adapter.Config.from_yaml(ROOT / "configs/config.example.yaml")


def ready_backend() -> adapter.SportBackend:
    cfg = replace(config(), velocity_prepare_s=0.0001)
    backend = adapter.SportBackend(cfg, lambda: 100.0)
    backend.client = Client()
    backend.low_state_at = 100.0
    backend.sport_state_at = 100.0
    return backend


def test_sport_velocity_lifecycle() -> None:
    backend = ready_backend()
    backend.set_command(command(0.1, 0.0, 0.0))
    assert backend.moving
    assert backend.client.calls[:2] == [
        ("BalanceStand",),
        ("Move", 0.1, 0.0, 0.0),
    ]
    backend.set_command(command(0.0, 0.0, 0.0))
    assert not backend.moving
    assert backend.client.calls[-1] == ("StopMove",)


def test_official_go2_subnet_and_reserved_robot_address() -> None:
    output = "2: enx0 inet 192.168.123.100/24 brd 192.168.123.255 scope global enx0"
    assert (
        adapter._local_ipv4_for_robot("enx0", "192.168.123.161", output)
        == "192.168.123.100"
    )
    reserved = (
        "2: enx0 inet 192.168.123.161/24 "
        "brd 192.168.123.255 scope global enx0"
    )
    try:
        adapter._local_ipv4_for_robot("enx0", "192.168.123.161", reserved)
    except RuntimeError as exc:
        assert "reserved for the Go2" in str(exc)
    else:
        raise AssertionError("the host must not use the Go2's reserved address")


def test_move_command_is_slew_limited() -> None:
    backend = ready_backend()
    backend.set_command(command(backend.config.max_vx_mps, 0.0, 0.0))
    first_move = backend.client.calls[-1]
    assert first_move[0] == "Move"
    assert 0.0 < first_move[1] <= (
        backend.config.max_ax_mps2 * backend.config.velocity_refresh_s + 1e-9
    )
    assert backend.target_velocity[0] == backend.config.max_vx_mps


def test_velocity_limit_fails_closed() -> None:
    backend = ready_backend()
    try:
        backend.set_command(
            command(backend.config.max_vx_mps + 0.01, 0.0, 0.0)
        )
    except ValueError as exc:
        assert "exceeds configured limits" in str(exc)
    else:
        raise AssertionError("out-of-range velocity must be rejected")


def test_watchdog_stops_motion() -> None:
    now = [100.0]
    cfg = replace(config(), velocity_prepare_s=0.0001)
    backend = adapter.SportBackend(cfg, lambda: now[0])
    backend.client = Client()
    backend.low_state_at = 100.0
    backend.sport_state_at = 100.0
    backend.set_command(command(0.1, 0.0, 0.0))
    now[0] += cfg.velocity_watchdog_s + 0.01
    backend.low_state_at = now[0]
    backend.sport_state_at = now[0]
    backend.refresh()
    assert not backend.moving
    assert backend.client.calls[-1] == ("StopMove",)
