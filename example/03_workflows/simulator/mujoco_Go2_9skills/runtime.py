"""Go2 九状态 FSM 与 ONNX 策略运行时。"""

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

SKILL_IDS = {
    "passive": 0,
    "fixstand": 1,
    "velocity": 2,
    "stairs_blind": 3,
    "footstand": 4,
    "handstand": 5,
    "bound": 6,
    "pronk": 7,
    "getup": 9,
}

SKILL_ALIASES = {
    "stand": "fixstand",
    "fix_stand": "fixstand",
    "stairs": "stairs_blind",
}

ALLOWED_TRANSITIONS = {
    "passive": {"fixstand", "getup"},
    "fixstand": {
        "passive",
        "velocity",
        "stairs_blind",
        "footstand",
        "handstand",
        "bound",
        "pronk",
    },
    "velocity": {"passive", "fixstand"},
    "stairs_blind": {"passive", "fixstand"},
    "footstand": {"passive"},
    "handstand": {"passive"},
    "getup": {"passive", "fixstand"},
    "bound": {"passive", "fixstand"},
    "pronk": {"passive", "fixstand"},
}

FIXSTAND_CROUCH = np.tile([0.0, 1.36, -2.65], 4)
FIXSTAND_FINAL = np.tile([0.0, 0.8, -1.5], 4)
FIXSTAND_KP = np.tile([60.0, 80.0, 80.0], 4)
FIXSTAND_KD = np.tile([5.0, 4.0, 4.0], 4)
PASSIVE_KP = np.zeros(12)
PASSIVE_KD = np.full(12, 3.0)
POLICY_PREPARE_MOVE_SECONDS = 1.5
POLICY_PREPARE_SETTLE_SECONDS = 0.5


@dataclass(frozen=True)
class RobotKinematics:
    joint_pos: np.ndarray
    joint_vel: np.ndarray
    base_pos: np.ndarray
    base_quat_wxyz: np.ndarray
    base_ang_vel: np.ndarray
    timestamp: float


def projected_gravity(quat_wxyz: np.ndarray) -> np.ndarray:
    """把世界系 [0, 0, -1] 旋转到机体系。"""
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
    """按 Unitree deploy.yaml 构造观测并解释动作。"""

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

        self.default_pos = np.asarray(
            self.config["default_joint_pos"],
            dtype=np.float32,
        )
        self.kp = np.asarray(self.config["stiffness"], dtype=np.float64)
        self.kd = np.asarray(self.config["damping"], dtype=np.float64)
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

        self.phase_period = 0.6
        phase_cfg = self.observation_config.get(
            "keyboard_gait_phase",
            self.observation_config.get("gait_phase"),
        )
        if phase_cfg:
            self.phase_period = float(phase_cfg.get("params", {}).get("period", 0.6))

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
        self.phase = (self.phase + 0.02 / self.phase_period) % 1.0
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
        raise ValueError(f"{self.name}: 不支持的 observation term: {name}")

    def _observation(
        self,
        state: RobotKinematics,
        command: np.ndarray,
    ) -> np.ndarray:
        flattened_terms: list[np.ndarray] = []
        for name, cfg in self.observation_config.items():
            value = self._term_value(name, state, command)
            scale = np.asarray(cfg.get("scale", 1.0), dtype=np.float32)
            value = value * scale
            clip = cfg.get("clip")
            if clip is not None:
                value = np.clip(value, clip[0], clip[1])

            history_length = int(cfg.get("history_length", 1))
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
                f"{self.name}: ONNX 输入需要 {self.input_size}，"
                f"实际构造 {observation.size}"
            )
        return observation

    def step(
        self,
        state: RobotKinematics,
        command: np.ndarray,
    ) -> np.ndarray:
        observation = self._observation(state, command)
        output = self.session.run(
            [self.output_name],
            {self.input_name: observation.reshape(1, -1)},
        )[0]
        raw_action = np.asarray(output[0], dtype=np.float32)
        if raw_action.size != 12:
            raise ValueError(f"{self.name}: ONNX 输出不是 12 维")

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
        return target.astype(np.float64)


class Go2SkillRuntime:
    """九状态控制器，复刻 Unitree Go2 部署 FSM 的核心行为。"""

    def __init__(
        self,
        policy_configs: dict[str, tuple[Path, Path]],
        initial_skill: str = "fixstand",
    ):
        self.policies = {
            name: OnnxPolicy(name, paths[0], paths[1])
            for name, paths in policy_configs.items()
        }
        self.skill = self.normalize_skill(initial_skill)
        self.entered_at: float | None = None
        self.fixstand_start = FIXSTAND_FINAL.copy()
        self.policy_start = FIXSTAND_FINAL.copy()
        self.last_error = ""

    @staticmethod
    def normalize_skill(skill: str | int) -> str:
        if isinstance(skill, int) or str(skill).isdigit():
            skill_id = int(skill)
            for name, value in SKILL_IDS.items():
                if value == skill_id:
                    return name
            raise ValueError(f"未知 skill id: {skill_id}")
        normalized = str(skill).strip().lower().replace("-", "_")
        normalized = SKILL_ALIASES.get(normalized, normalized)
        if normalized not in SKILL_IDS:
            raise ValueError(f"未知 skill: {skill}")
        return normalized

    def transition(
        self,
        requested: str | int,
        state: RobotKinematics,
    ) -> bool:
        target = self.normalize_skill(requested)
        if target == self.skill:
            return True
        if target not in ALLOWED_TRANSITIONS[self.skill]:
            self.last_error = f"不允许从 {self.skill} 直接切换到 {target}"
            return False
        self.skill = target
        self.entered_at = state.timestamp
        self.last_error = ""
        if target == "fixstand":
            self.fixstand_start = state.joint_pos.copy()
        if target in self.policies:
            self.policy_start = state.joint_pos.copy()
            self.policies[target].reset()
        return True

    def reset(self, skill: str = "fixstand") -> None:
        """仿真 RESET 后清空 FSM 与策略历史。"""
        self.skill = self.normalize_skill(skill)
        self.entered_at = None
        self.last_error = ""
        for policy in self.policies.values():
            policy.reset()

    def _ensure_entered(self, state: RobotKinematics) -> None:
        if self.entered_at is not None:
            return
        self.entered_at = state.timestamp
        if self.skill == "fixstand":
            self.fixstand_start = state.joint_pos.copy()
        if self.skill in self.policies:
            self.policy_start = state.joint_pos.copy()
            self.policies[self.skill].reset()

    def step(
        self,
        state: RobotKinematics,
        command: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self._ensure_entered(state)

        gravity = projected_gravity(state.base_quat_wxyz)
        if self.skill in {"footstand", "handstand"} and gravity[2] > 0.6:
            self.skill = "passive"
            self.entered_at = state.timestamp
            self.last_error = "姿态保护触发，已切换到 passive"

        if self.skill == "passive":
            return state.joint_pos.copy(), PASSIVE_KP, PASSIVE_KD

        if self.skill == "fixstand":
            elapsed = max(0.0, state.timestamp - float(self.entered_at))
            if elapsed <= 1.0:
                target = self.fixstand_start + elapsed * (
                    FIXSTAND_CROUCH - self.fixstand_start
                )
            elif elapsed <= 2.0:
                target = FIXSTAND_CROUCH + (elapsed - 1.0) * (
                    FIXSTAND_FINAL - FIXSTAND_CROUCH
                )
            else:
                target = FIXSTAND_FINAL
            return target, FIXSTAND_KP, FIXSTAND_KD

        policy = self.policies[self.skill]
        if self.skill != "getup":
            elapsed = max(0.0, state.timestamp - float(self.entered_at))
            prepare_seconds = (
                POLICY_PREPARE_MOVE_SECONDS + POLICY_PREPARE_SETTLE_SECONDS
            )
            if elapsed < prepare_seconds:
                blend = min(1.0, elapsed / POLICY_PREPARE_MOVE_SECONDS)
                target = self.policy_start + blend * (
                    policy.default_pos - self.policy_start
                )
                return target, FIXSTAND_KP, FIXSTAND_KD
        target = policy.step(state, command)
        return target, policy.kp, policy.kd

    def status(
        self,
        command: np.ndarray,
        state: RobotKinematics | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "skill": self.skill,
            "skill_id": SKILL_IDS[self.skill],
            "velocity": [float(value) for value in command],
            "error": self.last_error,
        }
        if state is not None:
            result["sim_time"] = float(state.timestamp)
            result["base_position"] = [
                float(value) for value in state.base_pos
            ]
            result["projected_gravity"] = [
                float(value)
                for value in projected_gravity(state.base_quat_wxyz)
            ]
            elapsed = (
                state.timestamp - self.entered_at
                if self.entered_at is not None
                else 0.0
            )
            result["transitioning"] = (
                self.skill == "fixstand"
                and (self.entered_at is None or elapsed < 2.0)
            ) or (
                self.skill in self.policies
                and self.skill != "getup"
                and (self.entered_at is None or elapsed < (
                    POLICY_PREPARE_MOVE_SECONDS
                    + POLICY_PREPARE_SETTLE_SECONDS
                ))
            )
        return result
