#!/usr/bin/env python3
"""Emit JointCommand 12-joint small swings for robots_go2 (suspended test)."""

from __future__ import annotations

import argparse
import time

from dora import Node
from forge_msgs import JointCommand, JointState

# SDK / robots_go2 order: FR → FL → RR → RL
JOINT_ORDER = [
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

DIRECTIONS = [
    -1.0,
    -1.0,
    1.0,
    1.0,
    -1.0,
    1.0,
    -1.0,
    -1.0,
    1.0,
    1.0,
    -1.0,
    1.0,
]
AMPLITUDE = 0.2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-delay-sec", type=float, default=5.0)
    parser.add_argument("--move-sec", type=float, default=1.2)
    parser.add_argument("--hold-sec", type=float, default=0.5)
    parser.add_argument("--between-joints-sec", type=float, default=0.5)
    parser.add_argument("--confirm-suspended", action="store_true")
    parser.add_argument("--confirm-high-risk", action="store_true")
    args = parser.parse_args()
    if not args.confirm_suspended or not args.confirm_high_risk:
        parser.error(
            "自动真机序列必须同时设置 "
            "--confirm-suspended 和 --confirm-high-risk"
        )
    if args.startup_delay_sec < 5.0:
        parser.error("--startup-delay-sec 不得小于5秒")
    if args.move_sec <= 0 or args.hold_sec < 0 or args.between_joints_sec < 0.5:
        parser.error("时间参数无效（between-joints-sec 不得小于0.5）")
    return args


def build_command(positions: list[float]) -> JointCommand:
    return JointCommand(
        name=list(JOINT_ORDER),
        mode="position",
        position=[float(value) for value in positions],
    )


def main() -> int:
    args = parse_args()
    node = Node()
    started = time.monotonic()
    baseline: list[float] | None = None
    joint_index = 0
    phase = "wait_startup"
    phase_ends_at = started + args.startup_delay_sec
    print(
        "[joint_sequence_source] suspended 12-joint sequence "
        f"(startup={args.startup_delay_sec}s, amplitude={AMPLITUDE}rad)"
    )

    for event in node:
        kind = event.get("type")
        if kind in {"STOP", "ERROR"}:
            break
        if kind != "INPUT":
            continue

        input_id = event["id"]
        if input_id == "state":
            try:
                state = JointState.from_arrow(event["value"])
                by_name = dict(zip(state.name, state.position, strict=False))
                sample = [float(by_name[name]) for name in JOINT_ORDER]
                if baseline is None and phase == "wait_startup":
                    if time.monotonic() >= phase_ends_at - 0.5:
                        baseline = sample
                        print("[joint_sequence_source] captured baseline from state")
            except Exception as exc:
                print(f"[joint_sequence_source] ignore bad state: {exc}")
            continue

        if input_id != "tick":
            continue

        now = time.monotonic()
        if phase == "wait_startup":
            if now < phase_ends_at:
                continue
            if baseline is None:
                print(
                    "[joint_sequence_source] no state yet; waiting for baseline"
                )
                phase_ends_at = now + 1.0
                continue
            phase = "to_peak"
            peak = list(baseline)
            peak[joint_index] = (
                baseline[joint_index] + DIRECTIONS[joint_index] * AMPLITUDE
            )
            print(
                f"[joint_sequence_source] [{joint_index + 1}/12] "
                f"{JOINT_ORDER[joint_index]} → peak"
            )
            node.send_output("action", build_command(peak).to_arrow())
            phase_ends_at = now + args.move_sec + args.hold_sec
            continue

        if now < phase_ends_at:
            continue

        if phase == "to_peak":
            phase = "to_home"
            print(
                f"[joint_sequence_source] [{joint_index + 1}/12] "
                f"{JOINT_ORDER[joint_index]} → baseline"
            )
            node.send_output(
                "action",
                build_command(list(baseline)).to_arrow(),
            )
            phase_ends_at = now + args.move_sec + args.between_joints_sec
            continue

        if phase == "to_home":
            joint_index += 1
            if joint_index >= len(JOINT_ORDER):
                print("[joint_sequence_source] sequence complete; holding")
                phase = "done"
                node.send_output(
                    "action",
                    build_command(list(baseline)).to_arrow(),
                )
                continue
            phase = "to_peak"
            peak = list(baseline)
            peak[joint_index] = (
                baseline[joint_index] + DIRECTIONS[joint_index] * AMPLITUDE
            )
            print(
                f"[joint_sequence_source] [{joint_index + 1}/12] "
                f"{JOINT_ORDER[joint_index]} → peak"
            )
            node.send_output("action", build_command(peak).to_arrow())
            phase_ends_at = now + args.move_sec + args.hold_sec
            continue

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
