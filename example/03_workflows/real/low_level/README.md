# Go2 Low Level — Forge 标准 driver

本目录真机节点只跑 **`src/robots_go2/`**（`Go2Driver` +
`run_dora_robot_node`），与 LeKiwi / R1 规范对齐。

- 读状态：`rt/lowstate` → Dora `state`（`forge_msgs.JointState`）
- 写电机：本目录 `joint_sequence_source.py` 发 `JointCommand` → `action`
  （需 `go2_config.yaml` 中 `low_level_output_enabled: true`）
- 节点循环：`forge_robot.run_dora_robot_node`（非本地兼容层）

High Level SportClient 示例在 `../high_level/`（单节点，不接 driver）。
本目录不再使用旧的 `go2_joint_sequence_source`。

## 安全要求

1. 机器人必须仰面可靠固定，四脚完全离地，所有关节摆动范围内无障碍物。
2. 必须关闭 `sport_mode` 并通过 `MotionSwitcherClient.ReleaseMode()`
   释放 `mcf`；driver 在首次写电机时会尝试 ReleaseMode。
3. 操作者必须始终手持原厂遥控器，并先验证 `L2+B` 硬件急停。
4. 首次运行或参数变更后必须逐关节验证，不得直接落地运行。
5. 默认 `go2_config.yaml` 中 `low_level_output_enabled: false`：拒绝
   `rt/lowcmd`。写电机前临时改为 `true`，测完改回。

电脑有线网卡应配置为 `192.168.123.x/24`。

真机 low_level 需要带 `JointState` / `JointCommand` /
`forge_robot` 的 Forge 包（见 `requirements.txt`）。仿真若仍用旧
`forge_msgs`，请用**单独 venv** 跑本目录，不要和旧仿真环境混装。

```bash
source "$HOME/robots/forge_runtime/.venv/bin/activate"   # 或专用 venv
cd "$HOME/robots/go2/example/03_workflows/real/low_level"
CYCLONEDDS_HOME=/usr/local uv pip install -r requirements.txt
```

**不要加 `--uv`**（会落到不完整的 `go2/.venv`）。

## 12 关节小幅序列（架空）

确认安全条件全部满足后，临时将 `go2_config.yaml` 中的
`low_level_output_enabled` 改为 `true`，再运行：

```bash
dora build dataflow.yaml
dora run dataflow.yaml
```

流程：

```text
等待 5s 并采集 baseline（来自 go2/state）
→ 按 FR→FL→RR→RL 逐关节：baseline ± 0.2rad → 保持 → 回 baseline
→ 结束保持
```

髋 `Kp=15`，大腿/小腿 `Kp=10`，`Kd=1`。

测试结束后必须立即将：

```yaml
low_level_output_enabled: false
```

恢复为安全默认值。不得同时运行 High Level Dataflow 或任何其他
`rt/lowcmd` 发布程序。

## 配置

| 文件 | 说明 |
|------|------|
| `dataflow.yaml` | `robots_go2` + 12 关节序列 |
| `go2_config.yaml` | driver 配置（含输出开关） |
| `realrobotconfig.yaml` | 旧配置，已弃用，仅作对照 |
