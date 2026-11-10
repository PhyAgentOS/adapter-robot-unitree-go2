#!/usr/bin/env python3
"""Minimal Unitree SportClient backend for the high_level Forge example."""

from __future__ import annotations

import importlib.util
import math
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

SDK_SKILLS = {
    "damp",
    "stand_up",
    "stand_down",
    "recovery_stand",
    "balance_stand",
    "velocity",
    "hello",
    "sit",
    "rise_sit",
}

SDK_TRANSITIONS = {
    "disconnected": set(),
    "connected": {
        "stand_up",
        "stand_down",
        "recovery_stand",
        "balance_stand",
        "velocity",
        "hello",
        "sit",
    },
    "damp": {"stand_up", "recovery_stand"},
    "stand_up": {"stand_down", "balance_stand", "velocity", "hello", "sit"},
    "stand_down": {"damp", "stand_up", "recovery_stand", "balance_stand"},
    "recovery_stand": {
        "stand_down",
        "balance_stand",
        "velocity",
        "hello",
        "sit",
    },
    "balance_stand": {
        "stand_down",
        "stand_up",
        "velocity",
        "recovery_stand",
        "hello",
        "sit",
    },
    "velocity": {"stand_down", "balance_stand", "stand_up"},
    "hello": {
        "stand_down",
        "balance_stand",
        "stand_up",
        "velocity",
        "sit",
    },
    "sit": {"rise_sit"},
    "rise_sit": {
        "sit",
        "stand_down",
        "balance_stand",
        "stand_up",
        "velocity",
        "hello",
    },
}


@dataclass(frozen=True)
class Config:
    network_interface: str
    motion_switcher_timeout_sec: float
    sdk_timeout_sec: float
    sdk_stand_down_wait_sec: float
    sdk_velocity_prepare_wait_sec: float
    sdk_state_wait_sec: float
    sdk_state_max_age_sec: float
    sdk_max_vx: float
    sdk_max_vy: float
    sdk_max_wz: float
    velocity_timeout_sec: float
    velocity_refresh_sec: float

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        return cls(
            network_interface=str(
                data.get("network_interface", "auto")
            ).strip(),
            motion_switcher_timeout_sec=float(
                data.get("motion_switcher_timeout_sec", 10.0)
            ),
            sdk_timeout_sec=float(data.get("sdk_timeout_sec", 10.0)),
            sdk_stand_down_wait_sec=float(
                data.get("sdk_stand_down_wait_sec", 3.0)
            ),
            sdk_velocity_prepare_wait_sec=float(
                data.get("sdk_velocity_prepare_wait_sec", 1.0)
            ),
            sdk_state_wait_sec=float(data.get("sdk_state_wait_sec", 5.0)),
            sdk_state_max_age_sec=float(
                data.get("sdk_state_max_age_sec", 0.5)
            ),
            sdk_max_vx=float(data.get("sdk_max_vx", 0.3)),
            sdk_max_vy=float(data.get("sdk_max_vy", 0.2)),
            sdk_max_wz=float(data.get("sdk_max_wz", 0.5)),
            velocity_timeout_sec=float(data.get("velocity_timeout_sec", 0.6)),
            velocity_refresh_sec=float(data.get("velocity_refresh_sec", 0.2)),
        )


def resolve_robot_network(configured: str) -> str:
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


def _json_value(value: Any) -> Any:
    if callable(value):
        value = value()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return str(value)


class SportClientController:
    """Own SportClient + HTTP-facing lifecycle used by the Dora example node."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._emergency_lock = threading.Lock()
        self._transition_lock = threading.Lock()
        self._client: Any = None
        self._emergency_client: Any = None
        self._subscribers: list[Any] = []
        self._network = ""
        self._requested_skill = "disconnected"
        self._velocity = (0.0, 0.0, 0.0)
        self._velocity_deadline = 0.0
        self._moving = False
        self._stop_event = threading.Event()
        self._emergency_requested = threading.Event()
        self._primary_rpc_active = threading.Event()
        self._emergency_thread: threading.Thread | None = None
        self._command_thread: threading.Thread | None = None
        self._state: dict[str, Any] = {}
        self._state_received_at = 0.0
        self._low_state_received_at = 0.0
        self._low_state_event = threading.Event()
        self._error = ""
        self._motion_mode: dict[str, str] = {}

    @property
    def is_armed(self) -> bool:
        return self._client is not None

    def _require_sport_mode(self) -> dict[str, str]:
        if importlib.util.find_spec("unitree_sdk2py") is None:
            raise RuntimeError(
                "缺少 unitree_sdk2py；请先安装官方 unitree_sdk2_python"
            )
        from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (  # type: ignore[import-not-found]
            MotionSwitcherClient,
        )
        from unitree_sdk2py.core.channel import (  # type: ignore[import-not-found]
            ChannelFactoryInitialize,
        )

        network = resolve_robot_network(self.config.network_interface)
        ChannelFactoryInitialize(0, network)
        client = MotionSwitcherClient()
        client.SetTimeout(self.config.motion_switcher_timeout_sec)
        client.Init()
        for attempt in range(2):
            code, result = client.CheckMode()
            if code == 0 and result is not None:
                mode = {
                    "form": str(result.get("form", "")),
                    "name": str(result.get("name", "")),
                }
                if not mode["name"]:
                    raise RuntimeError(
                        "SDK 要求机载 sport_mode 已启用；请先在 Unitree App "
                        "启用运动服务，再重试"
                    )
                self._motion_mode = mode
                return mode
            if code == 3104 and attempt == 0:
                time.sleep(0.2)
                continue
            detail = "（RPC超时）" if code == 3104 else ""
            raise RuntimeError(
                f"读取 Go2 motion_switcher 失败，code={code}{detail}"
            )
        raise RuntimeError("读取 Go2 motion_switcher 失败")

    def preflight(self) -> dict[str, Any]:
        network = resolve_robot_network(self.config.network_interface)
        mode = self._require_sport_mode()
        return {
            "backend": "sdk",
            "active_backend": "sdk",
            "network_interface": network,
            "motion_mode": mode,
            "skills": sorted(SDK_SKILLS),
            "note": "High Level SDK 要求机器人 sport_mode 已启用",
        }

    def arm(self) -> dict[str, Any]:
        with self._lock:
            if self.is_armed:
                return self.status()
            self._require_sport_mode()
            self._network = resolve_robot_network(
                self.config.network_interface
            )
            self._low_state_event.clear()

            from unitree_sdk2py.core.channel import (  # type: ignore[import-not-found]
                ChannelFactoryInitialize,
                ChannelSubscriber,
            )
            from unitree_sdk2py.go2.sport.sport_client import (  # type: ignore[import-not-found]
                SportClient,
            )
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import (  # type: ignore[import-not-found]
                LowState_,
                SportModeState_,
            )

            ChannelFactoryInitialize(0, self._network)
            client = SportClient()
            client.SetTimeout(self.config.sdk_timeout_sec)
            client.Init()
            emergency_client = SportClient()
            emergency_client.SetTimeout(
                min(1.0, self.config.sdk_timeout_sec)
            )
            emergency_client.Init()

            sport_subscriber = ChannelSubscriber(
                "rt/sportmodestate", SportModeState_
            )
            sport_subscriber.Init(self._on_sport_state, 10)
            lowstate_subscriber = ChannelSubscriber(
                "rt/lowstate", LowState_
            )
            lowstate_subscriber.Init(self._on_low_state, 10)

            self._client = client
            self._emergency_client = emergency_client
            self._subscribers = [sport_subscriber, lowstate_subscriber]
            self._requested_skill = "connected"
            self._velocity = (0.0, 0.0, 0.0)
            self._velocity_deadline = 0.0
            self._moving = False
            self._error = ""
            self._stop_event.clear()
            self._emergency_requested.clear()

        if not self._low_state_event.wait(self.config.sdk_state_wait_sec):
            with self._lock:
                self._client = None
                self._emergency_client = None
                self._subscribers = []
            raise RuntimeError(
                "等待 rt/lowstate 超时；SDK未建立有效状态反馈"
            )

        with self._lock:
            try:
                self._require_fresh_state()
                self._command_thread = threading.Thread(
                    target=self._refresh_velocity,
                    name="go2-sdk-velocity",
                    daemon=True,
                )
                self._command_thread.start()
                return self.status()
            except Exception:
                self._client = None
                self._emergency_client = None
                self._subscribers = []
                raise

    def _on_sport_state(self, message: Any) -> None:
        fields = (
            "mode",
            "progress",
            "gait_type",
            "position",
            "body_height",
            "velocity",
            "yaw_speed",
            "foot_force",
        )
        snapshot = {
            name: _json_value(getattr(message, name))
            for name in fields
            if hasattr(message, name)
        }
        with self._lock:
            self._state.update(snapshot)
            self._state_received_at = time.monotonic()

    def _on_low_state(self, message: Any) -> None:
        motor_states = getattr(message, "motor_state", [])
        if callable(motor_states):
            motor_states = motor_states()
        positions: list[float] = []
        velocities: list[float] = []
        if motor_states is not None:
            for motor in motor_states[:12]:
                q = getattr(motor, "q", 0.0)
                dq = getattr(motor, "dq", 0.0)
                positions.append(float(q() if callable(q) else q))
                velocities.append(float(dq() if callable(dq) else dq))
        with self._lock:
            if positions:
                self._state["joint_positions"] = positions
                self._state["joint_velocities"] = velocities
            if hasattr(message, "imu_state"):
                self._state["imu_state"] = _json_value(
                    getattr(message, "imu_state")
                )
            received_at = time.monotonic()
            self._state_received_at = received_at
            self._low_state_received_at = received_at
            if len(positions) >= 12:
                self._low_state_event.set()

    def _require_fresh_state(self) -> None:
        if self._low_state_received_at <= 0:
            raise RuntimeError("尚未收到有效 rt/lowstate，拒绝发送动作")
        age = time.monotonic() - self._low_state_received_at
        if age > self.config.sdk_state_max_age_sec:
            raise RuntimeError(
                f"rt/lowstate 已过期 {age:.3f}s，拒绝发送动作"
            )

    def _call(self, operation: str, callback: Callable[[], Any]) -> None:
        code = callback()
        if code not in (None, 0):
            if code == 3104:
                raise RuntimeError(
                    f"Unitree SDK {operation} RPC超时，code=3104；"
                    "动作可能已经发出，请先观察机器人，不要立即重复执行"
                )
            raise RuntimeError(f"Unitree SDK {operation} 失败，code={code}")

    def _send_emergency_commands(self) -> None:
        client = self._emergency_client
        if client is None:
            return
        with self._emergency_lock:
            stop_error = ""
            try:
                self._call("emergency StopMove", client.StopMove)
            except Exception as exc:
                stop_error = str(exc)
            try:
                self._call("emergency StandDown", client.StandDown)
            except Exception as exc:
                if stop_error:
                    raise RuntimeError(f"{stop_error}; {exc}") from exc
                raise
            if stop_error:
                raise RuntimeError(stop_error)

    def _call_primary(
        self,
        operation: str,
        callback: Callable[[], Any],
    ) -> None:
        with self._transition_lock:
            interrupted = self._emergency_requested.is_set()
            if not interrupted:
                self._primary_rpc_active.set()
        if interrupted:
            self._raise_if_emergency_requested(operation)
        try:
            self._call(operation, callback)
        finally:
            self._primary_rpc_active.clear()
        self._raise_if_emergency_requested(operation)

    def _repeat_emergency_until_primary_stops(self) -> None:
        while self._primary_rpc_active.is_set():
            try:
                self._send_emergency_commands()
            except Exception as exc:
                self._error = str(exc)
            time.sleep(0.1)
        try:
            self._send_emergency_commands()
        except Exception as exc:
            self._error = str(exc)
        finally:
            with self._transition_lock:
                self._requested_skill = "stand_down"
                self._moving = False

    def _start_emergency_watchdog(self) -> None:
        with self._transition_lock:
            if (
                self._emergency_thread is not None
                and self._emergency_thread.is_alive()
            ):
                return
            self._emergency_thread = threading.Thread(
                target=self._repeat_emergency_until_primary_stops,
                name="go2-sdk-emergency",
                daemon=True,
            )
            self._emergency_thread.start()

    def _raise_if_emergency_requested(self, operation: str) -> None:
        with self._transition_lock:
            interrupted = self._emergency_requested.is_set()
        if not interrupted:
            return
        try:
            self._send_emergency_commands()
        finally:
            with self._transition_lock:
                self._requested_skill = "stand_down"
                self._velocity = (0.0, 0.0, 0.0)
                self._velocity_deadline = 0.0
                self._moving = False
        raise RuntimeError(f"{operation} 执行期间收到软件急停")

    def prepare_skill(self) -> None:
        emergency_thread = self._emergency_thread
        if emergency_thread is not None and emergency_thread.is_alive():
            emergency_thread.join(timeout=2.5)
        if emergency_thread is not None and emergency_thread.is_alive():
            raise RuntimeError("软件急停仍在收尾，暂不接受新技能")
        with self._transition_lock:
            self._emergency_requested.clear()

    def request_skill(self, skill: str) -> dict[str, Any]:
        skill = skill.strip().lower()
        if skill not in SDK_SKILLS:
            raise ValueError(f"未知技能: {skill}")
        current = self._requested_skill
        if skill == current:
            return self.status()
        allowed = SDK_TRANSITIONS.get(current, set())
        if skill not in allowed:
            raise RuntimeError(
                f"SDK 不允许直接从 {current} 切换到 {skill}，"
                f"可选={sorted(allowed)}"
            )
        self.prepare_skill()
        if skill == "velocity":
            return self._prepare_velocity_mode()
        with self._lock:
            if not self.is_armed:
                raise RuntimeError("请先 arm")
            self._require_fresh_state()
            if skill == "damp" and self._requested_skill != "stand_down":
                raise RuntimeError("Damp 仅允许在 StandDown 受控卧倒后执行")
            operations: dict[str, Callable[[], Any]] = {
                "damp": self._client.Damp,
                "stand_up": self._client.StandUp,
                "stand_down": self._client.StandDown,
                "recovery_stand": self._client.RecoveryStand,
                "balance_stand": self._client.BalanceStand,
                "hello": self._client.Hello,
                "sit": self._client.Sit,
                "rise_sit": self._client.RiseSit,
            }
            self._raise_if_emergency_requested(skill)
            if self._requested_skill == "velocity" or self._moving:
                self._call_primary("StopMove", self._client.StopMove)
            self._call_primary(skill, operations[skill])
            with self._transition_lock:
                interrupted = self._emergency_requested.is_set()
                if not interrupted:
                    self._requested_skill = skill
                    self._velocity = (0.0, 0.0, 0.0)
                    self._velocity_deadline = 0.0
                    self._moving = False
            if interrupted:
                self._raise_if_emergency_requested(skill)
            return self.status()

    def _prepare_velocity_mode(self) -> dict[str, Any]:
        with self._lock:
            if not self.is_armed:
                raise RuntimeError("请先 arm")
            self._require_fresh_state()
            self._raise_if_emergency_requested("velocity")
            if self._moving:
                self._call_primary("StopMove", self._client.StopMove)
                self._moving = False
            self._call_primary("BalanceStand", self._client.BalanceStand)
            self._requested_skill = "balance_stand"
            self._velocity = (0.0, 0.0, 0.0)
            self._velocity_deadline = 0.0

        if self._emergency_requested.wait(
            self.config.sdk_velocity_prepare_wait_sec
        ):
            self._raise_if_emergency_requested("velocity")

        with self._lock:
            if not self.is_armed:
                raise RuntimeError("准备 velocity 时控制器已 disarm")
            self._require_fresh_state()
            self._raise_if_emergency_requested("velocity")
            if self._requested_skill != "balance_stand":
                raise RuntimeError("准备 velocity 期间状态已变化，拒绝发送速度")
            self._requested_skill = "velocity"
            return self.status()

    def set_velocity(self, vx: float, vy: float, wz: float) -> dict[str, Any]:
        with self._lock:
            if not self.is_armed:
                raise RuntimeError("请先 arm")
            self._require_fresh_state()
            if self._requested_skill != "velocity":
                raise RuntimeError(
                    f"{self._requested_skill} 状态不接受速度指令"
                )
            velocity = (float(vx), float(vy), float(wz))
            if not all(math.isfinite(value) for value in velocity):
                raise ValueError("速度必须是有限数值")
            limits = (
                self.config.sdk_max_vx,
                self.config.sdk_max_vy,
                self.config.sdk_max_wz,
            )
            names = ("vx", "vy", "wz")
            violations = [
                f"|{name}|={abs(value):.3f}>{limit:.3f}"
                for name, value, limit in zip(names, velocity, limits)
                if abs(value) > limit
            ]
            if violations:
                raise ValueError("；".join(violations))
            velocity_changed = velocity != self._velocity
            self._velocity = velocity
            self._velocity_deadline = (
                time.monotonic() + self.config.velocity_timeout_sec
            )
            if not any(abs(value) > 1e-6 for value in velocity):
                if self._moving:
                    self._call_primary("StopMove", self._client.StopMove)
                self._moving = False
            elif velocity_changed or not self._moving:
                self._send_velocity_once()
            return self.status()

    def _send_velocity_once(self) -> None:
        self._require_fresh_state()
        self._call_primary(
            "Move",
            lambda: self._client.Move(*self._velocity),
        )
        self._moving = True

    def _refresh_velocity(self) -> None:
        while not self._stop_event.wait(self.config.velocity_refresh_sec):
            try:
                with self._lock:
                    if not self.is_armed:
                        return
                    if (
                        self._requested_skill == "velocity"
                        and time.monotonic() <= self._velocity_deadline
                        and any(
                            abs(value) > 1e-6 for value in self._velocity
                        )
                    ):
                        self._send_velocity_once()
                    elif self._moving:
                        self._call_primary(
                            "StopMove",
                            self._client.StopMove,
                        )
                        self._moving = False
            except Exception as exc:
                with self._lock:
                    if self.is_armed and self._moving:
                        try:
                            self._call_primary(
                                "StopMove",
                                self._client.StopMove,
                            )
                        except Exception as stop_exc:
                            self._error = (
                                f"{exc}; StopMove失败: {stop_exc}"
                            )
                            return
                        self._moving = False
                    self._error = str(exc)
                return

    def emergency_stop(self) -> dict[str, Any]:
        if not self.is_armed:
            return self.status()
        with self._transition_lock:
            self._emergency_requested.set()
            self._velocity = (0.0, 0.0, 0.0)
            self._velocity_deadline = 0.0
            self._requested_skill = "emergency_stopping"
            self._moving = False
        self._start_emergency_watchdog()
        return self.status()

    def disarm(self) -> dict[str, Any]:
        with self._lock:
            if not self.is_armed:
                return self.status()
            graceful_error = ""
            try:
                if self._requested_skill not in {"stand_down", "damp"}:
                    self.emergency_stop()
                    time.sleep(self.config.sdk_stand_down_wait_sec)
            except Exception as exc:
                graceful_error = str(exc)
            finally:
                self._stop_event.set()
                self._client = None
                self._emergency_client = None
                self._subscribers = []
                self._moving = False
            self._error = graceful_error
            return self.status()

    def check_process(self) -> None:
        if self.is_armed:
            self._require_fresh_state()

    def status(self) -> dict[str, Any]:
        state_age = (
            time.monotonic() - self._state_received_at
            if self._state_received_at
            else None
        )
        return {
            "armed": self.is_armed,
            "backend": "sdk",
            "active_backend": "sdk",
            "network_interface": self._network,
            "requested_skill": self._requested_skill,
            "velocity": list(self._velocity),
            "velocity_watchdog_active": (
                self.is_armed
                and time.monotonic() <= self._velocity_deadline
            ),
            "sdk_state": dict(self._state),
            "joint_positions": list(
                self._state.get("joint_positions", [])
            ),
            "sdk_state_age_sec": state_age,
            "motion_mode": dict(self._motion_mode),
            "error": self._error,
        }
