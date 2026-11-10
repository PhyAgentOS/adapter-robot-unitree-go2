#!/usr/bin/env python3
"""播放单个 Go2 技能，或依次验证全部九个状态。"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request


SKILLS = (
    "passive",
    "fixstand",
    "velocity",
    "stairs_blind",
    "footstand",
    "handstand",
    "getup",
    "bound",
    "pronk",
)
BASE_URL = "http://127.0.0.1:8770"


def request(path: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}", method="POST")
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.loads(response.read())


def status() -> dict:
    with urllib.request.urlopen(f"{BASE_URL}/status", timeout=3) as response:
        return json.loads(response.read())


def wait_for_skill(skill: str, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = status()
        if current["skill"] == skill and not current.get("transitioning", False):
            return current
        time.sleep(0.1)
    raise RuntimeError(f"等待 {skill} 就绪超时，当前={status()}")


def wait_sim_seconds(seconds: float, timeout: float = 180.0) -> dict:
    current = status()
    started_at = float(current["sim_time"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = status()
        if float(current["sim_time"]) - started_at >= seconds:
            return current
        time.sleep(0.1)
    raise RuntimeError(f"等待仿真推进 {seconds:.1f}s 超时，当前={current}")


def switch(skill: str) -> dict:
    request(f"/skill/{skill}")
    current = wait_for_skill(skill)
    print(f"OK switch {skill}")
    return current


def reset() -> dict:
    request("/reset")
    current = wait_for_skill("fixstand")
    if current["error"] or current["projected_gravity"][2] >= -0.6:
        raise RuntimeError(f"RESET 后状态异常: {current}")
    print(
        f"OK fixstand: z={current['base_position'][2]:.3f}, "
        f"gravity_z={current['projected_gravity'][2]:.3f}"
    )
    return current


def assert_physics(
    skill: str,
    *,
    upright: bool,
    dwell: float,
    expected_gravity_x: float | None = None,
) -> None:
    current = wait_sim_seconds(dwell)
    if current["skill"] != skill or current["error"]:
        raise RuntimeError(f"{skill} 运行异常: {current}")
    base_position = current.get("base_position", [])
    gravity = current.get("projected_gravity", [])
    if (
        len(base_position) != 3
        or len(gravity) != 3
        or not all(math.isfinite(value) for value in base_position + gravity)
    ):
        raise RuntimeError(f"{skill} 状态数据无效: {current}")
    if base_position[2] <= 0.05:
        raise RuntimeError(f"{skill} 机身落地: {current}")
    if upright and (base_position[2] <= 0.15 or gravity[2] >= -0.6):
        raise RuntimeError(f"{skill} 翻倒或未站稳: {current}")
    if expected_gravity_x is not None and (
        base_position[2] <= 0.35
        or gravity[0] * expected_gravity_x <= 0.8
        or abs(gravity[2]) >= 0.4
    ):
        raise RuntimeError(f"{skill} 未达到目标竖立姿态: {current}")
    print(
        f"OK physics {skill}: z={base_position[2]:.3f}, "
        f"gravity_z={gravity[2]:.3f}"
    )


def play_one(
    skill: str,
    *,
    vx: float | None,
    vy: float,
    wz: float,
) -> int:
    reset()
    if skill == "fixstand":
        print(status())
        return 0

    if skill == "getup":
        switch("passive")
        wait_sim_seconds(3.0)
        switch("getup")
        print(status())
        return 0

    default_vx = {
        "velocity": 0.3,
        "stairs_blind": 0.5,
        "bound": 0.3,
        "pronk": 0.3,
    }.get(skill, 0.0)
    selected_vx = default_vx if vx is None else vx
    request(f"/velocity?vx={selected_vx}&vy={vy}&wz={wz}")
    switch(skill)
    print(status())
    return 0


def validate_all() -> int:
    failures: list[str] = []
    request("/velocity?vx=0&vy=0&wz=0")
    print(f"START {status()['skill']}")

    for skill in ["velocity", "stairs_blind", "bound", "pronk"]:
        try:
            reset()
            request("/velocity?vx=0.3&vy=0&wz=0")
            switch(skill)
            assert_physics(skill, upright=True, dwell=5.0)
        except Exception as exc:
            failures.append(f"{skill}: {exc}")
            print(f"FAIL {skill}: {exc}")

    for skill in ["footstand", "handstand"]:
        try:
            reset()
            request("/velocity?vx=0&vy=0&wz=0")
            switch(skill)
            assert_physics(
                skill,
                upright=False,
                dwell=6.0,
                expected_gravity_x=-1.0 if skill == "footstand" else 1.0,
            )
        except Exception as exc:
            failures.append(f"{skill}: {exc}")
            print(f"FAIL {skill}: {exc}")

    try:
        reset()
        switch("passive")
        passive = wait_sim_seconds(3.0)
        print(
            f"OK passive: z={passive['base_position'][2]:.3f}, "
            f"gravity_z={passive['projected_gravity'][2]:.3f}"
        )
        switch("getup")
        assert_physics("getup", upright=True, dwell=8.0)
    except Exception as exc:
        failures.append(f"passive/getup: {exc}")
        print(f"FAIL passive/getup: {exc}")

    if failures:
        print("FAILED_SKILLS")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("ALL_SKILLS_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", choices=(*SKILLS, "all"))
    parser.add_argument("--vx", type=float, default=None)
    parser.add_argument("--vy", type=float, default=0.0)
    parser.add_argument("--wz", type=float, default=0.0)
    args = parser.parse_args()
    if args.skill == "all":
        return validate_all()
    return play_one(
        args.skill,
        vx=args.vx,
        vy=args.vy,
        wz=args.wz,
    )


if __name__ == "__main__":
    raise SystemExit(main())
