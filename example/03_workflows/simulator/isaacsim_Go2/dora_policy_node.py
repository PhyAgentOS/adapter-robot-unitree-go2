#!/usr/bin/env python3
"""Dora node that runs one Go2 ONNX policy at 50 Hz."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


forge_runtime = Path(
    os.environ.get("FORGE_RUNTIME", Path.home() / "robots/forge_runtime")
)
forge_site_packages = (
    forge_runtime
    / f".venv/lib/python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if not forge_site_packages.is_dir():
    raise FileNotFoundError(
        f"Forge Python environment not found: {forge_site_packages}"
    )
sys.path.insert(0, str(forge_site_packages))

import numpy as np
import pyarrow as pa
import yaml
from dora import Node
from forge_msgs import Action

from rl_policy import JOINT_ORDER, OnnxPolicy, RobotKinematics


def _batch(value: object) -> pa.RecordBatch:
    if isinstance(value, pa.RecordBatch):
        return value
    if isinstance(value, pa.StructArray):
        return pa.RecordBatch.from_struct_array(value)
    if isinstance(value, pa.Table):
        batches = value.to_batches()
        if len(batches) == 1:
            return batches[0]
    raise TypeError(f"Expected Arrow struct data, got {type(value)!r}")


def parse_policy_state(
    value: pa.RecordBatch | pa.Table,
) -> RobotKinematics:
    batch = _batch(value)
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
        raise ValueError(
            f"Invalid policy_state; missing={sorted(missing)}"
        )
    return RobotKinematics(
        joint_pos=np.asarray(
            batch.column("joint_pos")[0].as_py(),
            dtype=np.float32,
        ),
        joint_vel=np.asarray(
            batch.column("joint_vel")[0].as_py(),
            dtype=np.float32,
        ),
        base_pos=np.asarray(
            batch.column("base_pos")[0].as_py(),
            dtype=np.float32,
        ),
        base_quat_wxyz=np.asarray(
            batch.column("base_quat_wxyz")[0].as_py(),
            dtype=np.float32,
        ),
        base_ang_vel=np.asarray(
            batch.column("base_ang_vel")[0].as_py(),
            dtype=np.float32,
        ),
        timestamp=float(batch.column("timestamp")[0].as_py()),
    )


def build_action(target: np.ndarray) -> pa.RecordBatch:
    return Action.from_np(
        target,
        JOINT_ORDER,
        mode="position",
        unit="radians",
    ).to_arrow(JOINT_ORDER)


def build_control_profile(
    kp: np.ndarray,
    kd: np.ndarray,
) -> pa.RecordBatch:
    return pa.RecordBatch.from_arrays(
        [
            pa.array(JOINT_ORDER, type=pa.string()),
            pa.array(kp.tolist(), type=pa.float64()),
            pa.array(kd.tolist(), type=pa.float64()),
        ],
        names=["name", "kp", "kd"],
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    return parser.parse_args()


def _load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Dora config must be a mapping")
    return config


def _policy(config: dict[str, Any], config_path: Path) -> OnnxPolicy:
    name = str(config.get("policy", "velocity"))
    policy_root = Path(config["policy_root"]).expanduser()
    if not policy_root.is_absolute():
        policy_root = (config_path.parent / policy_root).resolve()
    root = policy_root / name / "v0"
    return OnnxPolicy(
        name,
        root / "exported/policy.onnx",
        root / "params/deploy.yaml",
    )


def _command(policy: OnnxPolicy, config: dict[str, Any]) -> np.ndarray:
    command = np.asarray(
        config.get("command", [0.0, 0.0, 0.0]),
        dtype=np.float32,
    )
    if command.shape != (3,):
        raise ValueError("command must be [vx, vy, wz]")
    ranges = (
        policy.config.get("commands", {})
        .get("base_velocity", {})
        .get("ranges")
    )
    if ranges is None:
        command.fill(0.0)
        return command
    for index, key in enumerate(("lin_vel_x", "lin_vel_y", "ang_vel_z")):
        limits = ranges.get(key)
        if limits is not None:
            command[index] = np.clip(command[index], limits[0], limits[1])
    return command


def main() -> int:
    args = _parse_args()
    config_path = Path(args.config).resolve()
    config = _load_config(config_path)
    policy = _policy(config, config_path)
    command = _command(policy, config)
    node = Node()
    steps = 0

    print(
        f"[go2_dora_policy] policy={policy.name} "
        f"input={policy.input_size} command={command.tolist()}",
        flush=True,
    )
    for event in node:
        match event["type"]:
            case "INPUT":
                if event["id"] != "policy_state":
                    continue
                state = parse_policy_state(event["value"])
                target = policy.step(state, command)
                node.send_output(
                    "control_profile",
                    build_control_profile(policy.kp, policy.kd),
                )
                # policy_sync advances physics as soon as Action arrives, so
                # gains must be published before the position target.
                node.send_output("action", build_action(target))
                steps += 1
                if steps % 50 == 0:
                    print(
                        f"[go2_dora_policy] steps={steps} "
                        f"sim_time={state.timestamp:.2f} "
                        f"base={state.base_pos.round(3).tolist()} "
                        f"quat={state.base_quat_wxyz.round(3).tolist()}",
                        flush=True,
                    )
            case "STOP":
                break
            case "ERROR":
                print(
                    f"[go2_dora_policy] Dora error: {event.get('error')}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
