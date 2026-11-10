#!/usr/bin/env python3
"""Emit per-joint min / max / home trajectories for Go2 MuJoCo acceptance."""

from __future__ import annotations

import argparse
import math
import time

from dora import Node
from forge_msgs import Action, JointValue


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

# Matches assets/mjcf/Go2.xml ctrlrange / joint range.
JOINT_LIMITS = {
    "FL_hip_joint": (-1.0472, 1.0472),
    "FL_thigh_joint": (-1.5708, 3.4907),
    "FL_calf_joint": (-2.7227, -0.83776),
    "FR_hip_joint": (-1.0472, 1.0472),
    "FR_thigh_joint": (-1.5708, 3.4907),
    "FR_calf_joint": (-2.7227, -0.83776),
    "RL_hip_joint": (-1.0472, 1.0472),
    "RL_thigh_joint": (-0.5236, 4.5379),
    "RL_calf_joint": (-2.7227, -0.83776),
    "RR_hip_joint": (-1.0472, 1.0472),
    "RR_thigh_joint": (-0.5236, 4.5379),
    "RR_calf_joint": (-2.7227, -0.83776),
}

# Matches scene.xml keyframe "home" / policy default_joint_pos.
HOME_POSE = {
    "FL_hip_joint": -0.1,
    "FL_thigh_joint": 0.9,
    "FL_calf_joint": -1.8,
    "FR_hip_joint": 0.1,
    "FR_thigh_joint": 0.9,
    "FR_calf_joint": -1.8,
    "RL_hip_joint": -0.1,
    "RL_thigh_joint": 0.9,
    "RL_calf_joint": -1.8,
    "RR_hip_joint": 0.1,
    "RR_thigh_joint": 0.9,
    "RR_calf_joint": -1.8,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase-seconds",
        type=float,
        default=1.5,
        help="seconds spent ramping into min, max, or home",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=0.75,
        help="seconds spent holding min, max, or home",
    )
    parser.add_argument(
        "--startup-hold-seconds",
        type=float,
        default=2.0,
        help="initial all-joint home hold before the first sweep",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="repeat the full 12-joint sequence forever",
    )
    args = parser.parse_args()
    if args.phase_seconds <= 0 or args.hold_seconds < 0:
        parser.error("--phase-seconds 必须大于0，--hold-seconds 必须大于等于0")
    if args.startup_hold_seconds < 0:
        parser.error("--startup-hold-seconds 必须大于等于0")
    return args


def smoothstep(progress: float) -> float:
    clamped = min(1.0, max(0.0, progress))
    return clamped * clamped * (3.0 - 2.0 * clamped)


def build_action(targets: dict[str, float]) -> Action:
    return Action(
        joints={
            name: JointValue(
                value=float(targets[name]),
                mode="position",
                unit="radians",
            )
            for name in JOINT_ORDER
        }
    )


def home_targets() -> dict[str, float]:
    return {name: float(HOME_POSE[name]) for name in JOINT_ORDER}


def interpolate(
    start: dict[str, float],
    end: dict[str, float],
    progress: float,
) -> dict[str, float]:
    alpha = smoothstep(progress)
    return {
        name: start[name] + alpha * (end[name] - start[name])
        for name in JOINT_ORDER
    }


def build_schedule(
    *,
    phase_seconds: float,
    hold_seconds: float,
    startup_hold_seconds: float,
) -> list[tuple[float, str, dict[str, float], dict[str, float]]]:
    """Return (duration, label, start, end) segments."""
    schedule: list[tuple[float, str, dict[str, float], dict[str, float]]] = []
    home = home_targets()
    if startup_hold_seconds > 0:
        schedule.append((startup_hold_seconds, "startup_home", home, home))

    for joint in JOINT_ORDER:
        lower, upper = JOINT_LIMITS[joint]
        to_min = dict(home)
        to_min[joint] = lower
        to_max = dict(home)
        to_max[joint] = upper

        schedule.append((phase_seconds, f"{joint}:to_min", home, to_min))
        if hold_seconds > 0:
            schedule.append((hold_seconds, f"{joint}:hold_min", to_min, to_min))
        schedule.append((phase_seconds, f"{joint}:to_max", to_min, to_max))
        if hold_seconds > 0:
            schedule.append((hold_seconds, f"{joint}:hold_max", to_max, to_max))
        schedule.append((phase_seconds, f"{joint}:to_home", to_max, home))
        if hold_seconds > 0:
            schedule.append((hold_seconds, f"{joint}:hold_home", home, home))
    return schedule


def main() -> int:
    args = parse_args()
    schedule = build_schedule(
        phase_seconds=args.phase_seconds,
        hold_seconds=args.hold_seconds,
        startup_hold_seconds=args.startup_hold_seconds,
    )
    cycle_seconds = sum(duration for duration, _, _, _ in schedule)
    print(
        "[joint_sweep_source] "
        f"12 joints × min/max/home, cycle≈{cycle_seconds:.1f}s, "
        f"loop={args.loop}"
    )
    for joint in JOINT_ORDER:
        lower, upper = JOINT_LIMITS[joint]
        print(
            f"  {joint}: min={lower:.4f} max={upper:.4f} "
            f"home={HOME_POSE[joint]:.4f}"
        )

    node = Node()
    started = time.monotonic()
    last_label = ""
    finished = False

    for event in node:
        if event["type"] != "INPUT" or event["id"] != "tick":
            if event["type"] in {"STOP", "ERROR"}:
                break
            continue

        elapsed = time.monotonic() - started
        if not args.loop and elapsed >= cycle_seconds:
            if not finished:
                print("[joint_sweep_source] sequence complete; holding home")
                finished = True
            node.send_output(
                "action",
                build_action(home_targets()).to_arrow(JOINT_ORDER),
            )
            continue

        t = elapsed % cycle_seconds if args.loop else elapsed
        cursor = 0.0
        targets = home_targets()
        for duration, label, start, end in schedule:
            if t < cursor + duration or math.isclose(
                t, cursor + duration, abs_tol=1e-9
            ):
                progress = 0.0 if duration <= 0 else (t - cursor) / duration
                targets = interpolate(start, end, progress)
                if label != last_label:
                    print(f"[joint_sweep_source] {label}")
                    last_label = label
                break
            cursor += duration

        node.send_output(
            "action",
            build_action(targets).to_arrow(JOINT_ORDER),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
