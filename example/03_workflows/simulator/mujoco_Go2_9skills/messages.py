"""Go2 策略节点的 Arrow / Forge 消息转换。"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pyarrow as pa
from forge_msgs import Action, JointValue
from forge_msgs.value import ensure_record_batch

from runtime import JOINT_ORDER, RobotKinematics


def parse_policy_state(value: pa.RecordBatch | pa.Table | bytes) -> RobotKinematics:
    batch = ensure_record_batch(value)
    required = {
        "joint_pos",
        "joint_vel",
        "base_pos",
        "base_quat_wxyz",
        "base_ang_vel",
        "timestamp",
    }
    missing = required.difference(batch.schema.names)
    if batch.num_rows != 1 or missing:
        raise ValueError(f"policy_state 缺少字段: {sorted(missing)}")

    state = RobotKinematics(
        joint_pos=np.asarray(batch.column("joint_pos")[0].as_py(), dtype=np.float64),
        joint_vel=np.asarray(batch.column("joint_vel")[0].as_py(), dtype=np.float64),
        base_pos=np.asarray(batch.column("base_pos")[0].as_py(), dtype=np.float64),
        base_quat_wxyz=np.asarray(
            batch.column("base_quat_wxyz")[0].as_py(),
            dtype=np.float64,
        ),
        base_ang_vel=np.asarray(
            batch.column("base_ang_vel")[0].as_py(),
            dtype=np.float64,
        ),
        timestamp=float(batch.column("timestamp")[0].as_py()),
    )
    if state.joint_pos.size != 12 or state.joint_vel.size != 12:
        raise ValueError("policy_state 的 joint_pos/joint_vel 必须为 12 维")
    if (
        state.base_pos.size != 3
        or state.base_quat_wxyz.size != 4
        or state.base_ang_vel.size != 3
    ):
        raise ValueError("policy_state 的 quaternion/ang_vel 维度错误")
    return state


def build_action(target: np.ndarray) -> pa.RecordBatch:
    action = Action(
        joints={
            name: JointValue(
                value=float(target[index]),
                mode="position",
                unit="radians",
            )
            for index, name in enumerate(JOINT_ORDER)
        }
    )
    return action.to_arrow(JOINT_ORDER)


def build_control_profile(kp: np.ndarray, kd: np.ndarray) -> pa.RecordBatch:
    return pa.RecordBatch.from_arrays(
        [
            pa.array([kp.tolist()], type=pa.list_(pa.float64(), 12)),
            pa.array([kd.tolist()], type=pa.list_(pa.float64(), 12)),
        ],
        names=["kp", "kd"],
    )


def build_status(status: dict[str, Any]) -> bytes:
    return json.dumps(status, ensure_ascii=False).encode("utf-8")
