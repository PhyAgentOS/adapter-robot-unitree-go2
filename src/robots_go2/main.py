#!/usr/bin/env python3
"""Unitree Go2 Forge Dora node entry (BaseRobotDriver + forge_robot runner)."""

from __future__ import annotations

import math
import signal
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "robots_go2"

import typer
from forge_msgs import JointState
from forge_robot import run_dora_robot_node

from robots_go2.config import load_config
from robots_go2.driver import Go2Driver

app = typer.Typer(
    name="robots-go2",
    help="Unitree Go2 Forge node and low-level driver tools.",
    no_args_is_help=False,
)


def _make_driver(config_path: str | None) -> Go2Driver:
    config = load_config(config_path)
    return Go2Driver(
        network_interface=config.network_interface,
        move_duration=config.move_duration,
        control_hz=config.control_hz,
        state_timeout=config.state_timeout,
        low_level_output_enabled=config.low_level_output_enabled,
        auto_connect=True,
        debug=config.debug,
    )


def _install_shutdown_handlers(driver: Go2Driver) -> None:
    def handle(signum: int, _frame: object) -> None:
        print(f"\nReceived signal {signum}; stopping Go2 driver.", flush=True)
        driver.disconnect()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)


def _format_state_degrees(state: JointState) -> str:
    by_name = dict(zip(state.name, state.position, strict=False))
    parts = [
        f"{name}={math.degrees(by_name[name]):.3f}deg"
        for name in state.name
        if name in by_name
    ]
    return ", ".join(parts)


def _run_node(config_path: str | None) -> int:
    config = load_config(config_path)
    driver = _make_driver(config_path)
    _install_shutdown_handlers(driver)
    print(
        f"[robots-go2] ready | interface={config.network_interface} "
        f"joints={len(driver.joint_order)} control_hz={config.control_hz} "
        f"output_enabled={config.low_level_output_enabled}",
        flush=True,
    )
    try:
        return run_dora_robot_node(
            driver,
            joint_order=driver.joint_order,
            is_follower=bool(config.is_follower),
            debug=bool(config.debug),
        )
    finally:
        driver.disconnect()


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None, "--config", "-c", help="Go2 YAML config path"
    ),
) -> None:
    """No subcommand: run the Forge Dora robot node."""
    if ctx.invoked_subcommand is not None:
        return
    raise typer.Exit(_run_node(config_path=config))


@app.command()
def run(
    config: str | None = typer.Option(
        None, "--config", "-c", help="Go2 YAML config path"
    ),
) -> None:
    """Run the Go2 Dora robot node."""
    raise typer.Exit(_run_node(config_path=config))


@app.command("print-state")
def print_state(
    config: str | None = typer.Option(
        None, "--config", "-c", help="Go2 YAML config path"
    ),
    seconds: float = typer.Option(2.0, "--seconds", min=0.1),
) -> None:
    """Connect, print joint state for a few seconds, then exit."""
    import time

    driver = _make_driver(config)
    _install_shutdown_handlers(driver)
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = driver.get_state()
            print(_format_state_degrees(state), flush=True)
            time.sleep(0.2)
    finally:
        driver.disconnect()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
