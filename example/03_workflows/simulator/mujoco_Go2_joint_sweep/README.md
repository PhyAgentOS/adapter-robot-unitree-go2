# Go2 仿真全关节 min / max / 归零

本工作流使用 **`forge_runtime` 通用 mujoco 节点**，
配合本目录 `joint_sweep_source.py` 做全关节验收。不依赖 ONNX / `policy_state`。

按仿真关节顺序逐个驱动 12 个关节完成：

```text
home hold
→ min → hold
→ max → hold
→ home（归零）→ hold
```

非活动关节始终保持 `scene.xml` 的 `home` 姿态，不会把小腿拉到非法的 `0rad`。

## 节点

| 节点 | 路径 |
|------|------|
| mujoco | `forge_runtime/packages/nodes/simulators/mujoco/main.py` |
| 动作源 | 本目录 `joint_sweep_source.py` |
| 配置 | 本目录 `simulator.yaml`（`mujococonfig.yaml` 为同内容兼容副本） |

## 关节顺序与限位

| 关节 | min (rad) | max (rad) | home (rad) |
|------|-----------|-----------|------------|
| `FL/FR/RL/RR_hip_joint` | -1.0472 | 1.0472 | ±0.1 |
| `FL/FR_thigh_joint` | -1.5708 | 3.4907 | 0.9 |
| `RL/RR_thigh_joint` | -0.5236 | 4.5379 | 0.9 |
| `*_calf_joint` | -2.7227 | -0.83776 | -1.8 |

限位来自 `assets/mjcf/Go2.xml`。Go2 小腿限位全部为负值，验收中的“归零”
指回到 home，而不是数学零位。

## 运行

先激活 **`forge_runtime` 的 venv**（内含 `mujoco` 与完整 `forge_msgs`），
在本目录执行 `dora build` / `dora run`。**不要加 `--uv`**：`--uv` 会改用
仓库根下的 `go2/.venv`，常见报错是 `No module named mujoco` 或
`cannot import name 'Action'`。

```bash
source "$HOME/robots/forge_runtime/.venv/bin/activate"
cd "$HOME/robots/go2/example/03_workflows/simulator/mujoco_Go2_joint_sweep"
dora build dataflow.yaml
dora run dataflow.yaml
```

默认整轮约 83 秒：启动先保持 home 2 秒，之后每个关节约
`1.5 + 0.75 + 1.5 + 0.75 + 1.5 + 0.75 = 6.75` 秒。结束后继续保持 home。

循环重放可在 `dataflow.yaml` 的 `args` 中追加 `--loop`。

观察 `image/overview`：每个关节应先到下限、再到上限、最后回到 home；
其余关节无明显异常抖动。检查记录写到上级目录
`JOINT_SWEEP_CHECKLIST.md`。
