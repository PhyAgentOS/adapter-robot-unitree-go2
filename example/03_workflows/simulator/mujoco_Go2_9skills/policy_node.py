#!/usr/bin/env python3
"""Dora Go2 九技能策略节点，含本地 HTTP 控制接口。"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np
import yaml
from dora import Node
from forge_msgs import SimControl

from messages import (
    build_action,
    build_control_profile,
    build_status,
    parse_policy_state,
)
from runtime import Go2SkillRuntime


REQUIRED_POLICIES = {
    "velocity",
    "stairs_blind",
    "footstand",
    "handstand",
    "getup",
    "bound",
    "pronk",
}


class SharedControl:
    def __init__(self, initial_status: dict[str, Any]):
        self._lock = threading.Lock()
        self._pending_skill: str | int | None = None
        self._pending_reset = False
        self._velocity = np.zeros(3, dtype=np.float32)
        self._status = initial_status

    def request_skill(self, skill: str | int) -> None:
        with self._lock:
            self._pending_skill = skill

    def take_skill(self) -> str | int | None:
        with self._lock:
            value = self._pending_skill
            self._pending_skill = None
            return value

    def request_reset(self) -> None:
        with self._lock:
            self._pending_reset = True

    def take_reset(self) -> bool:
        with self._lock:
            value = self._pending_reset
            self._pending_reset = False
            return value

    def set_velocity(self, vx: float, vy: float, wz: float) -> None:
        with self._lock:
            self._velocity[:] = [vx, vy, wz]

    def velocity(self) -> np.ndarray:
        with self._lock:
            return self._velocity.copy()

    def update_status(self, status: dict[str, Any]) -> None:
        with self._lock:
            self._status = dict(status)

    def status(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._status)
            result["pending_skill"] = self._pending_skill
            return result


def _handler_class(control: SharedControl) -> type[BaseHTTPRequestHandler]:
    class SkillHandler(BaseHTTPRequestHandler):
        def _json_response(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _request_data(self) -> tuple[str, dict[str, list[str]], dict[str, Any]]:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            payload: dict[str, Any] = {}
            length = int(self.headers.get("Content-Length", "0"))
            if length:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            return parsed.path, query, payload

        def _handle(self) -> None:
            try:
                path, query, payload = self._request_data()
                if path == "/status":
                    self._json_response(200, control.status())
                    return

                if path == "/skill" or path.startswith("/skill/"):
                    name: str | int | None = payload.get("name")
                    if name is None:
                        name = query.get("name", [None])[0]
                    if name is None and path.startswith("/skill/"):
                        name = path.removeprefix("/skill/")
                    if name is None:
                        self._json_response(400, {"error": "缺少技能名称"})
                        return
                    control.request_skill(name)
                    self._json_response(
                        202,
                        {"requested_skill": name, "status": control.status()},
                    )
                    return

                if path == "/velocity":
                    def number(name: str) -> float:
                        raw = payload.get(name)
                        if raw is None:
                            raw = query.get(name, [0.0])[0]
                        return float(raw)

                    control.set_velocity(number("vx"), number("vy"), number("wz"))
                    self._json_response(200, control.status())
                    return

                if path == "/reset":
                    control.request_reset()
                    self._json_response(202, {"reset": "requested"})
                    return

                self._json_response(
                    200,
                    {
                        "endpoints": {
                            "status": "GET /status",
                            "skill": "POST /skill/{name}",
                            "velocity": "POST /velocity?vx=0.3&vy=0&wz=0",
                            "reset": "POST /reset",
                        }
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._json_response(400, {"error": str(exc)})

        def do_GET(self) -> None:  # noqa: N802
            self._handle()

        def do_POST(self) -> None:  # noqa: N802
            self._handle()

        def log_message(self, format_string: str, *args: object) -> None:
            print(f"[go2_policy_http] {format_string % args}")

    return SkillHandler


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Go2 九技能策略节点")
    parser.add_argument("--config", required=True)
    return parser.parse_args()


def _resolve(path: str, base_dir: Path) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = base_dir / resolved
    resolved = resolved.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _load_runtime(
    config_path: Path,
) -> tuple[Go2SkillRuntime, SharedControl, str, int]:
    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    base_dir = config_path.parent

    policy_raw = config.get("policies", {})
    missing = REQUIRED_POLICIES.difference(policy_raw)
    if missing:
        raise ValueError(f"缺少策略配置: {sorted(missing)}")

    policy_configs: dict[str, tuple[Path, Path]] = {}
    for name in REQUIRED_POLICIES:
        item = policy_raw[name]
        policy_configs[name] = (
            _resolve(item["onnx"], base_dir),
            _resolve(item["deploy"], base_dir),
        )

    runtime = Go2SkillRuntime(
        policy_configs,
        initial_skill=config.get("initial_skill", "fixstand"),
    )
    initial_command = np.asarray(
        config.get("initial_velocity", [0.0, 0.0, 0.0]),
        dtype=np.float32,
    )
    control = SharedControl(runtime.status(initial_command))
    control.set_velocity(*initial_command)
    return (
        runtime,
        control,
        str(config.get("http_host", "127.0.0.1")),
        int(config.get("http_port", 8770)),
    )


def main() -> int:
    args = _parse_args()
    config_path = Path(args.config).resolve()
    runtime, control, host, port = _load_runtime(config_path)

    server = ThreadingHTTPServer((host, port), _handler_class(control))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[go2_policy] HTTP 控制接口: http://{host}:{port}")

    node = Node()
    try:
        for event in node:
            match event["type"]:
                case "INPUT":
                    if event["id"] != "policy_state":
                        continue
                    state = parse_policy_state(event["value"])
                    if control.take_reset():
                        runtime.reset("fixstand")
                        node.send_output(
                            "sim_control",
                            SimControl(action="RESET").to_arrow(),
                        )
                        continue
                    requested_skill = control.take_skill()
                    if requested_skill is not None:
                        try:
                            runtime.transition(requested_skill, state)
                        except ValueError as exc:
                            runtime.last_error = str(exc)

                    velocity = control.velocity()
                    target, kp, kd = runtime.step(state, velocity)
                    status = runtime.status(velocity, state)
                    control.update_status(status)

                    node.send_output(
                        "control_profile",
                        build_control_profile(kp, kd),
                    )
                    node.send_output("action", build_action(target))
                    node.send_output("skill_status", build_status(status))

                case "STOP":
                    break
                case "ERROR":
                    print(f"[go2_policy] Dora error: {event.get('error')}")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
