# Unitree Go2 adapter

`robots_unitree_go2` connects a PhyAgentOS/Dora dataflow to the Unitree Go2
high-level SportClient API. It accepts planar velocity commands, publishes the
state required by the Go2 motion policy, and stops motion when commands expire.

## Interfaces

Inputs:

- `velocity_command`: one-row Arrow record batch containing `vx`, `vy`, and
  `wz` as metres per second and radians per second.
- `tick`: refreshes the watchdog and publishes state.

Outputs:

- `policy_state`: joint position, joint velocity, base position, base
  quaternion, base angular velocity, and timestamp.
- `driver_status`: JSON status bytes for diagnostics.

## Configuration

Copy `configs/config.example.yaml` and pass it with `--config`. The host must
have exactly one interface in `192.168.123.0/24` when
`network_interface: auto` is used. `192.168.123.161` is reserved for the Go2.

```bash
uv sync --frozen --extra test
uv run robots_unitree_go2 --config configs/config.example.yaml --check-config
uv run pytest
```

Starting the node performs network and state preflight checks but does not
change posture. The first non-zero velocity command requests `BalanceStand`.
A receive-side watchdog sends `StopMove` when commands expire.

## Unitree SDK

The official `unitree_sdk2_python` repository is pinned as a Git submodule at
commit `814556d15970dd2ecf1c9984e845ca02ab07e206`. Cyclone DDS is pinned at
tag `0.10.2` (commit `9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd`). Clone
with submodules:

```bash
git clone --recurse-submodules https://github.com/PhyAgentOS/adapter-robot-unitree-go2.git
```

The build first compiles the pinned Cyclone DDS source locally. The PyInstaller
build then embeds the SDK, Cyclone DDS runtime, and the SDK's `crc_amd64.so`
into the standalone executable:

```bash
./scripts/build_cyclonedds.sh
CYCLONEDDS_HOME="$PWD/.deps/cyclonedds" uv sync --frozen --extra test
./scripts/build_pyinstaller.sh
./dist/robots_unitree_go2 --config configs/config.example.yaml --check-config
```
