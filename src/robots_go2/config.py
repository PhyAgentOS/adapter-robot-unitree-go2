"""Configuration and joint metadata for the Go2 Forge driver node."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Unitree SDK / rt/lowstate motor index order (FR → FL → RR → RL).
JOINT_NAMES = [
    "FR_hip_joint",
    "FR_thigh_joint",
    "FR_calf_joint",
    "FL_hip_joint",
    "FL_thigh_joint",
    "FL_calf_joint",
    "RR_hip_joint",
    "RR_thigh_joint",
    "RR_calf_joint",
    "RL_hip_joint",
    "RL_thigh_joint",
    "RL_calf_joint",
]

# Soft software limits (radians) for suspended / short-range tests.
JOINT_LIMITS = (
    (-1.0472, 1.0472),
    (-1.5708, 3.4907),
    (-2.9, -0.83776),
    (-1.0472, 1.0472),
    (-1.5708, 3.4907),
    (-2.9, -0.83776),
    (-1.0472, 1.0472),
    (-0.5236, 4.5379),
    (-2.9, -0.83776),
    (-1.0472, 1.0472),
    (-0.5236, 4.5379),
    (-2.9, -0.83776),
)

# Conservative PD for suspended / short-range tests.
DEFAULT_KP = [20.0] * 12
DEFAULT_KD = [0.5] * 12


def clip_position(name: str, value: float) -> float:
    index = JOINT_NAMES.index(name)
    low, high = JOINT_LIMITS[index]
    return min(high, max(low, float(value)))


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parents[2]
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        bundled = (
            Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            / "config"
            / "go2_config.yaml"
        )
        if bundled.is_file():
            return bundled
    return project_root() / "config" / "go2_config.yaml"


@dataclass(frozen=True)
class Go2Config:
    network_interface: str = "auto"
    move_duration: float = 2.0
    control_hz: int = 500
    state_timeout: float = 5.0
    low_level_output_enabled: bool = False
    is_follower: bool = True
    debug: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Go2Config":
        output_enabled = data.get("low_level_output_enabled", False)
        if not isinstance(output_enabled, bool):
            raise ValueError("low_level_output_enabled 必须是布尔值")
        config = cls(
            network_interface=str(data.get("network_interface", "auto")).strip(),
            move_duration=float(data.get("move_duration", 2.0)),
            control_hz=int(data.get("control_hz", 500)),
            state_timeout=float(data.get("state_timeout", 5.0)),
            low_level_output_enabled=output_enabled,
            is_follower=bool(data.get("is_follower", True)),
            debug=bool(data.get("debug", False)),
        )
        if config.move_duration <= 0:
            raise ValueError("move_duration 必须大于 0")
        if config.control_hz <= 0:
            raise ValueError("control_hz 必须大于 0")
        if config.state_timeout <= 0:
            raise ValueError("state_timeout 必须大于 0")
        if not config.network_interface:
            raise ValueError("network_interface 不能为空")
        return config


def load_config(config_path: str | Path | None = None) -> Go2Config:
    path = Path(config_path) if config_path else default_config_path()
    if not path.is_file():
        raise FileNotFoundError(f"Go2 config not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Go2 config must be a mapping: {path}")
    return Go2Config.from_dict(data)


def degrees_summary(radians: list[float]) -> str:
    return ", ".join(
        f"{name}={math.degrees(value):.1f}deg"
        for name, value in zip(JOINT_NAMES, radians, strict=True)
    )
