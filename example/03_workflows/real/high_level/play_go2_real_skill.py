#!/usr/bin/env python3
"""Drive the high_level SportClient example over its local HTTP API."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8770"
SDK_SKILLS = (
    "damp",
    "stand_up",
    "stand_down",
    "recovery_stand",
    "balance_stand",
    "velocity",
    "hello",
    "sit",
    "rise_sit",
)


def request(path: str, *, method: str = "GET") -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def status() -> dict:
    return request("/status")


def sdk_position(payload: dict) -> list[float] | None:
    position = payload.get("sdk_state", {}).get("position")
    if not isinstance(position, list) or len(position) < 3:
        return None
    try:
        return [float(position[index]) for index in range(3)]
    except (TypeError, ValueError):
        return None


def switch_skill(skill: str, args: argparse.Namespace) -> None:
    current = status()
    if not current.get("armed", False):
        raise RuntimeError("控制器尚未 arm")

    result = request(f"/skill/{skill}", method="POST")
    if skill != "velocity" or args.duration <= 0:
        print(result)
        return

    start_position = sdk_position(current)
    motion_states: list[dict] = []
    deadline = time.monotonic() + args.duration
    try:
        while time.monotonic() < deadline:
            response = request(
                f"/velocity?vx={args.vx}&vy={args.vy}&wz={args.wz}",
                method="POST",
            )
            state = response.get("sdk_state", {})
            if isinstance(state, dict):
                motion_states.append(state)
            time.sleep(0.2)
    finally:
        request("/velocity?vx=0&vy=0&wz=0", method="POST")

    time.sleep(0.5)
    final = status()
    end_position = sdk_position(final)
    displacement = (
        [
            round(end_position[index] - start_position[index], 4)
            for index in range(3)
        ]
        if start_position is not None and end_position is not None
        else None
    )
    print(
        {
            "requested_velocity": [args.vx, args.vy, args.wz],
            "duration_sec": args.duration,
            "start_position_m": start_position,
            "end_position_m": end_position,
            "displacement_m": displacement,
            "final_skill": final.get("requested_skill"),
            "error": final.get("error", ""),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "status",
            "preflight",
            "arm",
            "disarm",
            "stop",
            *SDK_SKILLS,
        ),
    )
    parser.add_argument("--vx", type=float, default=0.15)
    parser.add_argument("--vy", type=float, default=0.0)
    parser.add_argument("--wz", type=float, default=0.0)
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="driving duration in seconds; zero only switches state",
    )
    args = parser.parse_args()
    if args.duration < 0:
        parser.error("--duration must be >= 0")

    if args.command == "status":
        print(status())
    elif args.command == "preflight":
        print(request("/preflight"))
    elif args.command == "arm":
        print(request("/arm", method="POST"))
    elif args.command == "disarm":
        print(request("/disarm", method="POST"))
    elif args.command == "stop":
        print(request("/stop", method="POST"))
    else:
        switch_skill(args.command, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
