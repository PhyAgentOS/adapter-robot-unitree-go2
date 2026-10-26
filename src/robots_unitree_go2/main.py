#!/usr/bin/env python3
"""Unitree Go2 SportClient Dora backend for the real-hardware profile.

Startup is read-only: it validates sport mode and waits for fresh DDS state, but
does not change posture. BalanceStand is requested only when the first non-zero
velocity command arrives. A receive-side watchdog always converges to StopMove.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import re
import socket
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pyarrow as pa
import yaml


@dataclass(frozen=True, slots=True)
class Config:
    network_interface: str
    robot_ip: str
    require_robot_ping: bool
    domain_id: int
    rpc_timeout_s: float
    ping_timeout_s: float
    state_wait_s: float
    initial_state_stable_s: float
    state_max_age_s: float
    velocity_prepare_s: float
    velocity_watchdog_s: float
    velocity_refresh_s: float
    max_vx_mps: float
    max_vy_mps: float
    max_wz_radps: float
    max_ax_mps2: float
    max_ay_mps2: float
    max_awz_radps2: float

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise TypeError("robots_unitree_go2 config must be a mapping")
        values = {
            "rpc_timeout_s": float(raw.get("rpc_timeout_s", 5.0)),
            "ping_timeout_s": float(raw.get("ping_timeout_s", 1.0)),
            "state_wait_s": float(raw.get("state_wait_s", 5.0)),
            "initial_state_stable_s": float(raw.get("initial_state_stable_s", 1.0)),
            "state_max_age_s": float(raw.get("state_max_age_s", 0.5)),
            "velocity_prepare_s": float(raw.get("velocity_prepare_s", 1.0)),
            "velocity_watchdog_s": float(raw.get("velocity_watchdog_s", 0.6)),
            "velocity_refresh_s": float(raw.get("velocity_refresh_s", 0.2)),
            "max_vx_mps": float(raw.get("max_vx_mps", 0.3)),
            "max_vy_mps": float(raw.get("max_vy_mps", 0.2)),
            "max_wz_radps": float(raw.get("max_wz_radps", 0.5)),
            "max_ax_mps2": float(raw.get("max_ax_mps2", 0.5)),
            "max_ay_mps2": float(raw.get("max_ay_mps2", 0.5)),
            "max_awz_radps2": float(raw.get("max_awz_radps2", 1.0)),
        }
        if any(not math.isfinite(v) or v <= 0 for v in values.values()):
            raise ValueError("all robots_unitree_go2 numeric settings must be positive")
        if values["velocity_refresh_s"] >= values["velocity_watchdog_s"]:
            raise ValueError("velocity_refresh_s must be below velocity_watchdog_s")
        robot_ip = str(raw.get("robot_ip", "192.168.123.161")).strip()
        try:
            ipaddress.IPv4Address(robot_ip)
        except ipaddress.AddressValueError as exc:
            raise ValueError(f"robot_ip must be a valid IPv4 address: {robot_ip}") from exc
        domain_id = int(raw.get("domain_id", 0))
        if not 0 <= domain_id <= 232:
            raise ValueError("domain_id must be between 0 and 232")
        require_robot_ping = raw.get("require_robot_ping", True)
        if not isinstance(require_robot_ping, bool):
            raise TypeError("require_robot_ping must be true or false")
        return cls(
            network_interface=str(raw.get("network_interface", "auto")).strip(),
            robot_ip=robot_ip,
            require_robot_ping=require_robot_ping,
            domain_id=domain_id,
            **values,
        )


def resolve_robot_network(configured: str) -> str:
    available = {name for _, name in socket.if_nameindex()}
    if configured and configured != "auto":
        if configured not in available:
            raise RuntimeError(f"configured network interface does not exist: {configured}")
        return configured
    result = subprocess.run(
        ["ip", "-o", "-4", "addr", "show"],
        check=True,
        capture_output=True,
        text=True,
    )
    matches = {
        match.group(1)
        for line in result.stdout.splitlines()
        if (match := re.search(r"^\d+:\s+(\S+)\s+.*\binet\s+192\.168\.123\.\d+/", line))
    }
    if len(matches) != 1:
        raise RuntimeError(
            "network_interface=auto requires exactly one 192.168.123.x interface; "
            f"found {sorted(matches)}"
        )
    return next(iter(matches))


def _local_ipv4_for_robot(interface: str, robot_ip: str, output: str) -> str:
    """Select the interface address that shares the robot's IPv4 subnet."""
    robot = ipaddress.IPv4Address(robot_ip)
    candidates: list[ipaddress.IPv4Interface] = []
    for line in output.splitlines():
        match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", line)
        if match:
            candidates.append(ipaddress.IPv4Interface(match.group(1)))
    matches = [candidate for candidate in candidates if robot in candidate.network]
    if not matches:
        configured = [str(candidate) for candidate in candidates]
        raise RuntimeError(
            f"interface {interface} has no IPv4 address in the Go2 subnet for {robot_ip}; "
            f"configured addresses: {configured}"
        )
    if any(candidate.ip == robot for candidate in matches):
        raise RuntimeError(
            f"interface {interface} uses {robot_ip}, which is reserved for the Go2; "
            "assign the user PC a different address such as 192.168.123.100/24"
        )
    return str(matches[0].ip)


def validate_robot_network(
    interface: str,
    robot_ip: str,
    *,
    require_ping: bool,
    ping_timeout_s: float,
) -> str:
    result = subprocess.run(
        ["ip", "-o", "-4", "addr", "show", "dev", interface],
        check=True,
        capture_output=True,
        text=True,
    )
    local_ip = _local_ipv4_for_robot(interface, robot_ip, result.stdout)
    if require_ping:
        timeout = max(1, math.ceil(ping_timeout_s))
        try:
            probe = subprocess.run(
                ["ping", "-n", "-c", "1", "-W", str(timeout), "-I", interface, robot_ip],
                check=False,
                capture_output=True,
                text=True,
                timeout=ping_timeout_s + 1.0,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ping is required for Go2 preflight but is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Go2 preflight ping timed out: {robot_ip} via {interface}") from exc
        if probe.returncode != 0:
            raise RuntimeError(
                f"Go2 is not reachable at {robot_ip} via {interface}; "
                "check the Ethernet cable, static IPv4 address, and robot power"
            )
    return local_ip


def _value(value: Any) -> Any:
    return value() if callable(value) else value


def _checked(operation: str, callback: Callable[[], Any]) -> None:
    code = callback()
    if code not in (None, 0):
        suffix = "; effect may be unknown, do not retry blindly" if code == 3104 else ""
        raise RuntimeError(f"Unitree SDK {operation} failed: code={code}{suffix}")


def _batch(value: object) -> pa.RecordBatch:
    if isinstance(value, pa.RecordBatch):
        return value
    if isinstance(value, pa.StructArray):
        return pa.RecordBatch.from_struct_array(value)
    raise TypeError("velocity command must be an Arrow RecordBatch or StructArray")


def _list(values: list[float]) -> pa.Array:
    return pa.array([values], type=pa.list_(pa.float64()))


class SportBackend:
    def __init__(self, config: Config, clock: Any = time.monotonic) -> None:
        self.config = config
        self.clock = clock
        self.lock = threading.RLock()
        self.client: Any = None
        self.subscribers: list[Any] = []
        self.network = ""
        self.local_ip = ""
        self.mode: dict[str, str] = {}
        self.low_state_at = 0.0
        self.sport_state_at = 0.0
        self.position = [0.0, 0.0, 0.0]
        self.quat = [1.0, 0.0, 0.0, 0.0]
        self.ang_vel = [0.0, 0.0, 0.0]
        self.joint_pos = [0.0] * 12
        self.joint_vel = [0.0] * 12
        self.velocity = (0.0, 0.0, 0.0)
        self.target_velocity = (0.0, 0.0, 0.0)
        self.command_deadline = 0.0
        self.last_refresh = 0.0
        self.velocity_ready = False
        self.moving = False
        self.error = ""

    def connect(self) -> None:
        from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
        from unitree_sdk2py.go2.sport.sport_client import SportClient
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_

        self.network = resolve_robot_network(self.config.network_interface)
        self.local_ip = validate_robot_network(
            self.network,
            self.config.robot_ip,
            require_ping=self.config.require_robot_ping,
            ping_timeout_s=self.config.ping_timeout_s,
        )
        ChannelFactoryInitialize(self.config.domain_id, self.network)
        switcher = MotionSwitcherClient()
        switcher.SetTimeout(self.config.rpc_timeout_s)
        switcher.Init()
        code, result = switcher.CheckMode()
        if code != 0 or not result or not str(result.get("name", "")):
            raise RuntimeError(
                f"Go2 main motion service is unavailable (code={code}); enable mcf/sport_mode "
                "and put the robot in motion mode with the Unitree App or remote controller"
            )
        self.mode = {"form": str(result.get("form", "")), "name": str(result["name"])}
        client = SportClient()
        client.SetTimeout(self.config.rpc_timeout_s)
        client.Init()
        sport = ChannelSubscriber("rt/sportmodestate", SportModeState_)
        low = ChannelSubscriber("rt/lowstate", LowState_)
        sport.Init(self._on_sport_state, 10)
        low.Init(self._on_low_state, 10)
        self.client = client
        self.subscribers = [sport, low]

        deadline = self.clock() + self.config.state_wait_s
        stable_since: float | None = None
        while self.clock() < deadline:
            if self.fresh():
                now = self.clock()
                stable_since = now if stable_since is None else stable_since
                if now - stable_since >= self.config.initial_state_stable_s:
                    return
            else:
                stable_since = None
            time.sleep(0.02)
        self.close()
        raise RuntimeError("timed out waiting for fresh Go2 low-state and sport-state feedback")

    def _on_sport_state(self, message: Any) -> None:
        position = list(_value(getattr(message, "position", [])) or [])
        if len(position) < 2:
            return
        with self.lock:
            self.position = [float(position[0]), float(position[1]), float(position[2] if len(position) > 2 else 0.0)]
            self.sport_state_at = self.clock()

    def _on_low_state(self, message: Any) -> None:
        motors = list(_value(getattr(message, "motor_state", [])) or [])
        imu = _value(getattr(message, "imu_state", None))
        if len(motors) < 12 or imu is None:
            return
        quat = list(_value(getattr(imu, "quaternion", [])) or [])
        gyro = list(_value(getattr(imu, "gyroscope", [])) or [])
        if len(quat) != 4 or len(gyro) != 3:
            return
        with self.lock:
            self.joint_pos = [float(_value(getattr(item, "q", 0.0))) for item in motors[:12]]
            self.joint_vel = [float(_value(getattr(item, "dq", 0.0))) for item in motors[:12]]
            self.quat = [float(v) for v in quat]
            self.ang_vel = [float(v) for v in gyro]
            self.low_state_at = self.clock()

    def fresh(self) -> bool:
        now = self.clock()
        with self.lock:
            return (
                self.low_state_at > 0
                and self.sport_state_at > 0
                and now - self.low_state_at <= self.config.state_max_age_s
                and now - self.sport_state_at <= self.config.state_max_age_s
            )

    def require_fresh(self) -> None:
        if not self.fresh():
            raise RuntimeError("fresh Go2 low-state and sport-state feedback is required")

    def policy_state(self) -> pa.RecordBatch:
        self.require_fresh()
        with self.lock:
            return pa.RecordBatch.from_arrays(
                [
                    _list(self.joint_pos),
                    _list(self.joint_vel),
                    _list(self.position),
                    _list(self.quat),
                    _list(self.ang_vel),
                    pa.array([self.clock()], type=pa.float64()),
                ],
                names=["joint_pos", "joint_vel", "base_pos", "base_quat_wxyz", "base_ang_vel", "timestamp"],
            )

    def set_command(self, value: object) -> None:
        batch = _batch(value)
        if batch.num_rows != 1 or not {"vx", "vy", "wz"}.issubset(batch.schema.names):
            raise ValueError("velocity command must contain one vx/vy/wz row")
        velocity = tuple(float(batch[name][0].as_py()) for name in ("vx", "vy", "wz"))
        if not all(math.isfinite(v) for v in velocity):
            raise ValueError("velocity command must be finite")
        limits = (self.config.max_vx_mps, self.config.max_vy_mps, self.config.max_wz_radps)
        if any(abs(v) > limit + 1e-6 for v, limit in zip(velocity, limits, strict=True)):
            raise ValueError(f"velocity command exceeds configured limits: {velocity}")
        self.require_fresh()
        now = self.clock()
        self.command_deadline = now + self.config.velocity_watchdog_s
        if not any(abs(v) > 1e-6 for v in velocity):
            self.target_velocity = (0.0, 0.0, 0.0)
            self.stop_move()
            return
        if not self.velocity_ready:
            _checked("BalanceStand", self.client.BalanceStand)
            time.sleep(self.config.velocity_prepare_s)
            self.require_fresh()
            self.velocity_ready = True
        self.target_velocity = velocity
        self._send_velocity()

    def _send_velocity(self) -> None:
        now = self.clock()
        dt = (
            self.config.velocity_refresh_s
            if self.last_refresh <= 0
            else max(0.0, now - self.last_refresh)
        )
        accelerations = (
            self.config.max_ax_mps2,
            self.config.max_ay_mps2,
            self.config.max_awz_radps2,
        )
        next_velocity = []
        for current, target, acceleration in zip(
            self.velocity, self.target_velocity, accelerations, strict=True
        ):
            maximum_step = acceleration * dt
            delta = max(-maximum_step, min(maximum_step, target - current))
            next_velocity.append(current + delta)
        self.velocity = tuple(next_velocity)
        # Move is a no-reply RPC. Mark the effect as possible before sending so
        # an exception or DDS timeout still converges through StopMove.
        self.moving = True
        _checked("Move", lambda: self.client.Move(*self.velocity))
        self.last_refresh = now

    def refresh(self) -> None:
        now = self.clock()
        if self.moving and now > self.command_deadline:
            self.error = "velocity watchdog expired; StopMove sent"
            self.stop_move()
        elif self.moving and now - self.last_refresh >= self.config.velocity_refresh_s:
            self.require_fresh()
            self._send_velocity()

    def stop_move(self) -> None:
        if self.client is not None and self.moving:
            _checked("StopMove", self.client.StopMove)
        self.moving = False
        self.velocity = (0.0, 0.0, 0.0)
        self.target_velocity = (0.0, 0.0, 0.0)
        self.command_deadline = 0.0

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.client is not None,
            "network_interface": self.network,
            "local_ip": self.local_ip,
            "robot_ip": self.config.robot_ip,
            "dds_domain_id": self.config.domain_id,
            "motion_mode": self.mode,
            "state_fresh": self.fresh(),
            "velocity_ready": self.velocity_ready,
            "moving": self.moving,
            "velocity": list(self.velocity),
            "target_velocity": list(self.target_velocity),
            "error": self.error,
        }

    def close(self) -> None:
        try:
            self.stop_move()
        finally:
            for subscriber in self.subscribers:
                try:
                    subscriber.Close()
                except Exception:
                    pass
            self.subscribers = []
            self.client = None


class Runner:
    def __init__(self, node: Any, backend: SportBackend) -> None:
        self.node = node
        self.backend = backend

    def process_event(self, event: dict[str, Any]) -> int | None:
        event_type = event.get("type")
        if event_type == "STOP":
            self.backend.close()
            return 0
        if event_type == "ERROR":
            self.backend.close()
            return 1
        if event_type != "INPUT":
            return None
        try:
            if event.get("id") == "velocity_command":
                self.backend.set_command(event.get("value"))
            elif event.get("id") == "tick":
                self.backend.refresh()
                self.node.send_output("policy_state", self.backend.policy_state())
                self.node.send_output("driver_status", json.dumps(self.backend.status()).encode())
        except Exception as exc:
            self.backend.error = str(exc)
            try:
                self.backend.stop_move()
            finally:
                self.node.send_output("driver_status", json.dumps(self.backend.status()).encode())
        return None

    def run(self, events: Iterable[dict[str, Any]]) -> int:
        for event in events:
            result = self.process_event(event)
            if result is not None:
                return result
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unitree Go2 SportClient Dora backend")
    parser.add_argument("--config", default="robot.yaml")
    parser.add_argument("--check-config", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = Config.from_yaml(args.config)
    if args.check_config:
        from unitree_sdk2py.go2.sport.sport_client import SportClient  # noqa: F401
        print(json.dumps({"ok": True, "backend": "SportClient", "config": str(Path(args.config).resolve())}))
        return 0
    from dora import Node

    backend = SportBackend(config)
    backend.connect()
    node = Node()
    return Runner(node, backend).run(node)


if __name__ == "__main__":
    raise SystemExit(main())
