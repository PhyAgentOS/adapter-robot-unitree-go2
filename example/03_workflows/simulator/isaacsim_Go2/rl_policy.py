"""Unitree Go2 ONNX policy observations and action decoding."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import yaml


JOINT_ORDER = [
    "FL_hip_joint",
    "FL_thigh_joint",
    "FL_calf_joint",
    "FR_hip_joint",
    "FR_thigh_joint",
    "FR_calf_joint",
    "RL_hip_joint",
    "RL_thigh_joint",
    "RL_calf_joint",
    "RR_hip_joint",
    "RR_thigh_joint",
    "RR_calf_joint",
]


@dataclass(frozen=True)
class RobotKinematics:
    joint_pos: np.ndarray
    joint_vel: np.ndarray
    base_pos: np.ndarray
    base_quat_wxyz: np.ndarray
    base_ang_vel: np.ndarray
    timestamp: float


def projected_gravity(quat_wxyz: np.ndarray) -> np.ndarray:
    """Rotate world gravity direction into the robot base frame."""
    w, x, y, z = quat_wxyz
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float32,
    )
    return rotation.T @ np.array([0.0, 0.0, -1.0], dtype=np.float32)


class OnnxPolicy:
    """Construct observations and decode actions from Unitree deploy.yaml."""

    def __init__(self, name: str, onnx_path: Path, deploy_path: Path):
        self.name = name
        with deploy_path.open(encoding="utf-8") as stream:
            self.config: dict[str, Any] = yaml.safe_load(stream)

        self.session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.input_size = int(self.session.get_inputs()[0].shape[-1])
        self.step_dt = float(self.config.get("step_dt", 0.02))

        self.default_pos = np.asarray(
            self.config["default_joint_pos"],
            dtype=np.float32,
        )
        self.kp = np.asarray(self.config["stiffness"], dtype=np.float32)
        self.kd = np.asarray(self.config["damping"], dtype=np.float32)
        self.observation_config = self.config["observations"]

        action_name, action_cfg = next(iter(self.config["actions"].items()))
        self.relative_action = action_name.startswith("Relative")
        self.action_scale = np.asarray(action_cfg["scale"], dtype=np.float32)
        offset = action_cfg.get("offset")
        self.action_offset = (
            np.asarray(offset, dtype=np.float32)
            if offset is not None
            else self.default_pos.copy()
        )
        clip = action_cfg.get("clip")
        self.action_clip = (
            np.asarray(clip, dtype=np.float32) if clip is not None else None
        )

        phase_cfg = self.observation_config.get(
            "keyboard_gait_phase",
            self.observation_config.get("gait_phase"),
        )
        self.phase_period = (
            float(phase_cfg.get("params", {}).get("period", 0.6))
            if phase_cfg
            else 0.6
        )
        self.last_action = np.zeros(12, dtype=np.float32)
        self.phase = 0.0
        self.history: dict[str, deque[np.ndarray]] = {}

    def reset(self) -> None:
        self.last_action.fill(0.0)
        self.phase = 0.0
        self.history.clear()

    def _phase_observation(self, command: np.ndarray) -> np.ndarray:
        value = np.array(
            [
                math.sin(2.0 * math.pi * self.phase),
                math.cos(2.0 * math.pi * self.phase),
            ],
            dtype=np.float32,
        )
        self.phase = (self.phase + self.step_dt / self.phase_period) % 1.0
        if float(np.linalg.norm(command)) < 0.1:
            value.fill(0.0)
        return value

    def _term_value(
        self,
        name: str,
        state: RobotKinematics,
        command: np.ndarray,
    ) -> np.ndarray:
        if name == "base_ang_vel":
            return state.base_ang_vel.astype(np.float32)
        if name == "projected_gravity":
            return projected_gravity(state.base_quat_wxyz)
        if name == "keyboard_velocity_commands":
            return command.astype(np.float32)
        if name in {"keyboard_gait_phase", "gait_phase"}:
            return self._phase_observation(command)
        if name == "joint_pos_rel":
            return state.joint_pos.astype(np.float32) - self.default_pos
        if name == "joint_vel_rel":
            return state.joint_vel.astype(np.float32)
        if name == "last_action":
            return self.last_action.copy()
        raise ValueError(f"{self.name}: unsupported observation term: {name}")

    def observation(
        self,
        state: RobotKinematics,
        command: np.ndarray,
    ) -> np.ndarray:
        flattened_terms: list[np.ndarray] = []
        for name, config in self.observation_config.items():
            value = self._term_value(name, state, command)
            value = value * np.asarray(
                config.get("scale", 1.0),
                dtype=np.float32,
            )
            clip = config.get("clip")
            if clip is not None:
                value = np.clip(value, clip[0], clip[1])

            history_length = int(config.get("history_length", 1))
            history = self.history.get(name)
            if history is None:
                history = deque(
                    (value.copy() for _ in range(history_length)),
                    maxlen=history_length,
                )
                self.history[name] = history
            else:
                history.append(value.copy())
            flattened_terms.extend(history)

        observation = np.concatenate(flattened_terms).astype(np.float32)
        if observation.size != self.input_size:
            raise ValueError(
                f"{self.name}: ONNX expects {self.input_size} observations, "
                f"constructed {observation.size}"
            )
        return observation

    def step(
        self,
        state: RobotKinematics,
        command: np.ndarray,
    ) -> np.ndarray:
        observation = self.observation(state, command)
        output = self.session.run(
            [self.output_name],
            {self.input_name: observation.reshape(1, -1)},
        )[0]
        raw_action = np.asarray(output[0], dtype=np.float32)
        if raw_action.size != 12:
            raise ValueError(f"{self.name}: ONNX output is not 12-dimensional")

        if self.relative_action:
            target = state.joint_pos + self.action_scale * raw_action
        else:
            target = self.action_offset + self.action_scale * raw_action
        if self.action_clip is not None:
            target = np.clip(
                target,
                self.action_clip[:, 0],
                self.action_clip[:, 1],
            )
        self.last_action = raw_action
        return target.astype(np.float32)
