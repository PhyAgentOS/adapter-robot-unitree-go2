# 03 — Forge 端到端 workflow

**Forge 标准仿真 / 全关节验收**：`simulator/mujoco_Go2_joint_sweep/` ——
`forge_runtime` 通用 mujoco + `joint_sweep_source.py`，模型为本仓
`assets/mjcf/scene.xml`（`prefix: item_1/`）。检查记录见
`simulator/JOINT_SWEEP_CHECKLIST.md`。

**九技能仿真**：`simulator/mujoco_Go2_9skills/` —— `forge_runtime` mujoco +
目录内 `policy_node.py`（ONNX）；图像用 `image_viewer`。

**真机 — Forge driver / Low Level**：`real/low_level/` ——
跑 `src/robots_go2/`（`BaseRobotDriver` + `run_dora_robot_node`）。
架空 12 关节序列见 `real/low_level/dataflow.yaml`。

**真机 — High Level 技能示例**：`real/high_level/` —— 单节点
`SportClient` + HTTP，不接入 `robots_go2` driver。

仿真交付记录见 `simulator/SIMULATION_INTEGRATION.md`。
