#!/usr/bin/env python3
"""Single Dora node: SportClient control + local HTTP operator API."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pyarrow as pa
from dora import Node

from sport_client import Config, SportClientController


def _bool_query(query: dict[str, list[str]], name: str) -> bool:
    return query.get(name, ["false"])[0].lower() in {"1", "true", "yes"}


def start_http(
    controller: SportClientController,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    skill_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _run(self, fn) -> None:
            try:
                self._send(200, fn())
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:
                self._send(409, {"error": str(exc)})

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/status":
                self._send(200, controller.status())
            elif path == "/preflight":
                self._run(controller.preflight)
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            path = parsed.path
            if path == "/arm":
                self._run(controller.arm)
            elif path == "/disarm":
                self._run(controller.disarm)
            elif path in {"/stop", "/emergency_stop"}:
                self._run(controller.emergency_stop)
            elif path.startswith("/skill/"):
                skill = path.removeprefix("/skill/")

                def _skill() -> dict[str, Any]:
                    if not skill_lock.acquire(blocking=False):
                        raise RuntimeError(
                            "另一个技能仍在执行；当前仅接受 /stop"
                        )
                    try:
                        return controller.request_skill(skill)
                    finally:
                        skill_lock.release()

                self._run(_skill)
            elif path == "/velocity":
                try:
                    vx = float(query.get("vx", ["0"])[0])
                    vy = float(query.get("vy", ["0"])[0])
                    wz = float(query.get("wz", ["0"])[0])
                except ValueError as exc:
                    self._send(400, {"error": str(exc)})
                    return
                self._run(lambda: controller.set_velocity(vx, vy, wz))
            else:
                self._send(404, {"error": "not found"})

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    threading.Thread(
        target=server.serve_forever,
        name="go2-sport-http",
        daemon=True,
    ).start()
    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="realrobotconfig.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = Config.from_yaml(Path(args.config).resolve())
    controller = SportClientController(config)
    server = start_http(controller, args.host, args.port)
    print(
        f"[go2_high_level] SportClient example: "
        f"http://{args.host}:{args.port}"
    )

    node = Node()
    try:
        for event in node:
            if event["type"] == "INPUT" and event["id"] == "tick":
                try:
                    controller.check_process()
                except Exception as exc:
                    print(f"[go2_high_level] tick: {exc}", file=sys.stderr)
                status = controller.status()
                node.send_output(
                    "status",
                    pa.RecordBatch.from_pydict(
                        {"json": [json.dumps(status, ensure_ascii=False)]}
                    ),
                )
            elif event["type"] in {"STOP", "ERROR"}:
                break
    finally:
        controller.disarm()
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
