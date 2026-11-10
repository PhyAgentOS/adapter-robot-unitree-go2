"""Go2 low-level driver implementing forge_robot.BaseRobotDriver."""

from __future__ import annotations

import math
import threading
import time
from typing import Any

from forge_common import get_logger
from forge_msgs import JointCommand, JointState
from forge_robot import BaseRobotDriver
from forge_robot.actuator_spec import (
    ActuatorSpec,
    clip_and_validate_command,
    specs_by_name,
)

from .config import (
    DEFAULT_KD,
    DEFAULT_KP,
    JOINT_LIMITS,
    JOINT_NAMES,
)

logger = get_logger(__name__)

LOW_CMD_TOPIC = "rt/lowcmd"
LOW_STATE_TOPIC = "rt/lowstate"
POS_STOP_F = 2.146e9
VEL_STOP_F = 16000.0


def smooth_step(ratio: float) -> float:
    ratio = max(0.0, min(1.0, ratio))
    return ratio * ratio * (3.0 - 2.0 * ratio)


def _build_actuator_specs() -> tuple[ActuatorSpec, ...]:
    return tuple(
        ActuatorSpec(
            name=name,
            kind="revolute",
            mode="position",
            min_position=float(JOINT_LIMITS[index][0]),
            max_position=float(JOINT_LIMITS[index][1]),
        )
        for index, name in enumerate(JOINT_NAMES)
    )


ACTUATOR_SPECS = _build_actuator_specs()


class Go2Driver(BaseRobotDriver):
    """Read and optionally position-control the 12 Go2 leg joints."""

    def __init__(
        self,
        network_interface: str = "auto",
        *,
        move_duration: float = 2.0,
        control_hz: int = 500,
        state_timeout: float = 5.0,
        low_level_output_enabled: bool = False,
        auto_connect: bool = True,
        debug: bool = False,
    ) -> None:
        self.network_interface = network_interface
        self.move_duration = move_duration
        self.control_hz = control_hz
        self.state_timeout = state_timeout
        self.low_level_output_enabled = low_level_output_enabled
        self.debug = debug
        self._specs = specs_by_name(ACTUATOR_SPECS)
        self._name_to_index = {name: index for index, name in enumerate(JOINT_NAMES)}

        self._crc: Any = None
        self._lock = threading.RLock()
        self._state_ready = threading.Event()
        self._low_state: Any = None
        self._connected = False
        self._control_active = False
        self._disconnecting = False
        self._resolved_network = ""

        self._subscriber: Any = None
        self._publisher: Any = None
        self._command_thread: threading.Thread | None = None
        self._command_stop = threading.Event()
        self._write_count = 0
        self._write_failures = 0
        self._low_cmd: Any = None

        self._start_q = [0.0] * len(JOINT_NAMES)
        self._target_q = [0.0] * len(JOINT_NAMES)
        self._command_q = [0.0] * len(JOINT_NAMES)
        self._kp = list(DEFAULT_KP)
        self._kd = list(DEFAULT_KD)
        self._motion_started_at = 0.0
        self._warned_output_disabled = False

        if auto_connect:
            self.connect()

    @property
    def joint_order(self) -> list[str]:
        return list(JOINT_NAMES)

    @property
    def control_active(self) -> bool:
        return self._control_active

    def connect(self) -> None:
        if self._connected:
            return

        from unitree_sdk2py.core.channel import (  # type: ignore[import-not-found]
            ChannelFactoryInitialize,
            ChannelPublisher,
            ChannelSubscriber,
        )
        from unitree_sdk2py.idl.default import (  # type: ignore[import-not-found]
            unitree_go_msg_dds__LowCmd_,
        )
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import (  # type: ignore[import-not-found]
            LowCmd_,
            LowState_,
        )
        from unitree_sdk2py.utils.crc import CRC  # type: ignore[import-not-found]

        from .network import resolve_robot_network

        self._resolved_network = resolve_robot_network(self.network_interface)
        logger.info(
            "Initializing Unitree DDS on interface %s", self._resolved_network
        )
        ChannelFactoryInitialize(0, self._resolved_network)

        self._crc = CRC()
        self._low_cmd = unitree_go_msg_dds__LowCmd_()
        self._prepare_stop_frame()

        self._publisher = ChannelPublisher(LOW_CMD_TOPIC, LowCmd_)
        self._publisher.Init()
        self._subscriber = ChannelSubscriber(LOW_STATE_TOPIC, LowState_)
        self._subscriber.Init(self._low_state_handler, 1)
        self._connected = True

        if not self._state_ready.wait(self.state_timeout):
            self.disconnect()
            raise RuntimeError(
                f"No valid {LOW_STATE_TOPIC} within {self.state_timeout:.1f}s; "
                "check network_interface and robot DDS connection"
            )
        positions = self._current_positions()
        with self._lock:
            self._start_q = positions
            self._target_q = positions
            self._command_q = positions
        logger.info(
            "Go2 connected in read-only mode (output_enabled=%s)",
            self.low_level_output_enabled,
        )

    def disconnect(self) -> None:
        if self._disconnecting:
            return
        self._disconnecting = True
        try:
            self._control_active = False
            if self._command_thread is not None:
                self._command_stop.set()
                self._command_thread.join(timeout=1.0)
                self._command_thread = None
            if self._subscriber is not None:
                self._subscriber.Close()
                self._subscriber = None
            if self._publisher is not None:
                self._publisher.Close()
                self._publisher = None
        finally:
            self._connected = False
            self._disconnecting = False
            logger.info("Go2 driver disconnected")

    def _prepare_stop_frame(self) -> None:
        self._low_cmd.head[0] = 0xFE
        self._low_cmd.head[1] = 0xEF
        self._low_cmd.level_flag = 0xFF
        self._low_cmd.gpio = 0
        for motor in self._low_cmd.motor_cmd:
            motor.mode = 0x01
            motor.q = POS_STOP_F
            motor.dq = VEL_STOP_F
            motor.kp = 0.0
            motor.kd = 0.0
            motor.tau = 0.0

    def _low_state_handler(self, message: Any) -> None:
        try:
            if int(message.crc) != int(self._crc.Crc(message)):
                logger.warning("Ignoring %s with invalid CRC", LOW_STATE_TOPIC)
                return
        except Exception:
            return
        with self._lock:
            self._low_state = message
        self._state_ready.set()

    def _current_positions(self) -> list[float]:
        with self._lock:
            state = self._low_state
            if state is None:
                raise RuntimeError("No valid Go2 low state is available")
            return [float(state.motor_state[index].q) for index in range(12)]

    def _current_velocities(self) -> list[float]:
        with self._lock:
            state = self._low_state
            if state is None:
                raise RuntimeError("No valid Go2 low state is available")
            return [float(state.motor_state[index].dq) for index in range(12)]

    def get_state(self) -> JointState:
        if not self._connected:
            raise RuntimeError("Go2 driver is not connected")
        return JointState(
            name=list(JOINT_NAMES),
            position=self._current_positions(),
            velocity=self._current_velocities(),
            effort=[],
        )

    def set_command(self, command: JointCommand) -> None:
        if not self._connected:
            raise RuntimeError("Go2 driver is not connected")
        if not self.low_level_output_enabled:
            if not self._warned_output_disabled:
                logger.error(
                    "low_level_output_enabled=false；忽略 action，不写 rt/lowcmd。"
                    "架空验收前请在 go2_config.yaml 中显式打开。"
                )
                self._warned_output_disabled = True
            return

        if command.mode not in {"position", "hybrid"}:
            raise ValueError(
                f"Go2 low-level driver only supports position/hybrid, got {command.mode!r}"
            )
        if not command.position:
            raise ValueError("Go2 JointCommand requires position values")

        clipped = clip_and_validate_command(command, self._specs)
        if not clipped.name:
            raise ValueError("Go2 JointCommand contains no known joints")

        for value in clipped.position:
            if not math.isfinite(float(value)):
                raise ValueError("JointCommand position contains a non-finite value")

        if not self._control_active:
            self._activate_low_level_control()

        current = self._current_positions()
        with self._lock:
            # Sparse update: omitted joints keep previous command targets.
            target = list(self._target_q)
            kp = list(self._kp)
            kd = list(self._kd)
            for index, name in enumerate(clipped.name):
                joint_index = self._name_to_index.get(name)
                if joint_index is None:
                    continue
                target[joint_index] = float(clipped.position[index])
                if clipped.kp:
                    kp[joint_index] = float(clipped.kp[index])
                if clipped.kd:
                    kd[joint_index] = float(clipped.kd[index])
            self._start_q = current
            self._target_q = target
            self._command_q = current
            self._kp = kp
            self._kd = kd
            self._motion_started_at = time.monotonic()
        logger.info("Accepted Go2 JointCommand for %d joints", len(clipped.name))

    def _activate_low_level_control(self) -> None:
        self._release_motion_mode()
        with self._lock:
            current = self._current_positions()
            self._start_q = current
            self._target_q = current
            self._command_q = current
            self._motion_started_at = time.monotonic()
            self._control_active = True
        self._command_stop.clear()
        self._write_count = 0
        self._write_failures = 0
        self._command_thread = threading.Thread(
            target=self._command_loop,
            name="go2_lowcmd",
            daemon=True,
        )
        self._command_thread.start()
        logger.warning("Go2 low-level control is active (rt/lowcmd publishing)")

    def _release_motion_mode(self) -> None:
        from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (  # type: ignore[import-not-found]
            MotionSwitcherClient,
        )

        client = MotionSwitcherClient()
        client.SetTimeout(5.0)
        client.Init()
        for _ in range(10):
            status, result = client.CheckMode()
            if status != 0:
                raise RuntimeError(
                    f"MotionSwitcher CheckMode failed with code {status}"
                )
            if not result or not result.get("name"):
                return
            logger.info("Releasing Unitree motion mode %s", result.get("name"))
            code, _ = client.ReleaseMode()
            if code != 0:
                raise RuntimeError(
                    f"MotionSwitcher ReleaseMode failed with code {code}"
                )
            time.sleep(1.0)
        raise RuntimeError(
            "MotionSwitcher mode remained active after 10 release attempts"
        )

    def _command_loop(self) -> None:
        period = 1.0 / float(self.control_hz)
        next_write = time.monotonic()
        while not self._command_stop.is_set():
            try:
                self._write_low_command()
            except Exception:
                logger.exception("Go2 low-command writer stopped after an exception")
                self._control_active = False
                return
            next_write += period
            delay = next_write - time.monotonic()
            if delay <= 0:
                next_write = time.monotonic()
                continue
            self._command_stop.wait(delay)

    def _write_low_command(self) -> None:
        if not self._control_active or self._publisher is None:
            return
        with self._lock:
            elapsed = time.monotonic() - self._motion_started_at
            blend = smooth_step(elapsed / self.move_duration)
            self._command_q = [
                start + blend * (target - start)
                for start, target in zip(self._start_q, self._target_q, strict=True)
            ]
            command_q = list(self._command_q)
            kp = list(self._kp)
            kd = list(self._kd)

        self._prepare_stop_frame()
        for index in range(12):
            motor = self._low_cmd.motor_cmd[index]
            motor.mode = 0x01
            motor.q = command_q[index]
            motor.dq = 0.0
            motor.tau = 0.0
            motor.kp = kp[index]
            motor.kd = kd[index]
        self._low_cmd.crc = self._crc.Crc(self._low_cmd)
        if self._publisher.Write(self._low_cmd):
            self._write_count += 1
            if self._write_count == 1:
                logger.info("Publishing Go2 %s at %d Hz", LOW_CMD_TOPIC, self.control_hz)
            return
        self._write_failures += 1
        if self._write_failures == 1 or self._write_failures % self.control_hz == 0:
            logger.warning(
                "Failed to publish Go2 %s (%d failures)",
                LOW_CMD_TOPIC,
                self._write_failures,
            )
