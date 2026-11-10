# Go2 仿真交付记录

本文件记录 Go2 仿真资产、MuJoCo 配置与 Dora workflow 的交付状态。

**Forge 标准仿真接入 / 全关节验收**：`mujoco_Go2_joint_sweep/`
（`forge_runtime` 通用 mujoco + `mujoco_Go2_joint_sweep/joint_sweep_source.py`）。
**九技能示例**：`mujoco_Go2_9skills/`（`forge_runtime` mujoco + 目录内
`policy_node.py` / ONNX）。

---

## 1. 资产整理（MJCF / GLB）

**结论**：仿真只依赖本仓 MJCF + mesh；交付另备 GLB。当前上游资产包未提供 URDF。

| 资产 | 本仓路径 | 状态自检 |
|------|-----------|----------|
| MJCF + mesh | **`assets/mjcf/`** 根目录 | 已落盘，仿真入口为 `scene.xml` |
| GLB（Web/交付） | `assets/glb/elfin5l.glb` | 已由 `robot_asset_pipeline` 生成 |
| URDF | `assets/urdf/` | 当前无 URDF，目录预留 |

---

## 2. MJCF 核查（名称、顺序、单位、限位、层级、mesh）

**结论**：模型入口、前缀、执行器与 `mujoco_elfin5l/simulator.yaml` 已按以下约定整理。

- **前缀**：`scene.xml` 使用 `attach` 前缀 `item_1/`，故模型内机械臂关节全名形如 `item_1/joint1`。Forge 配置里写无前缀的逻辑名 + `robots[].prefix: item_1/`。
- **执行器**：`Elfin5L.xml` 中 `<actuator>` 共 **9** 个（3 个虚拟底盘 velocity、6 个六轴机械臂 position），与 `simulator.yaml` / `task_robot.yaml` 的 `actuator_order` 一致。
- **夹爪**：当前主模型未包含夹爪执行器。
- **相机**：上游主场景未包含相机；本仓 `scene.xml` 补充 `overview_cam` 与 `side_cam` 两个场景级固定相机，在 `simulator.yaml` 的 `image_forward` 中直接使用相机名。

---

## 3. 模型对齐（原点、朝向、缩放）

**结论**：仿真入口以 `assets/mjcf/scene.xml` 为准；GLB 仅作为 Web / 可视化交付资产。

- **仿真 SSOT**：以 **`assets/mjcf/`** 为准。
- **留痕记录**：模型对齐记录见 **`MODEL_ALIGNMENT_NOTES.md`**。

---

## 4. Workflow 与节点（Forge / Dora）

**结论**：本仓已提供 Dora workflow 配置，MuJoCo 节点可通过该配置加载本仓模型，`task_robot` 的关节顺序与仿真配置一致。

1. **仿真配置示例**：本仓已提供 **`simulation/mujoco_elfin5l/`**（`simulator.yaml`、`task_robot.yaml`、`dataflow.test_action_source.yaml`、`stream_viewer.yaml`、`README.md`）。模型路径只依赖本仓 `assets/mjcf/`；`dataflow` 中节点脚本路径指向与工作区并列的 **`forge_runtime/packages/nodes/...`**（见该目录 README）。
2. **`simulator.yaml` 关键约定**：
   - `model_path`：指向本仓 **`assets/mjcf/scene.xml`**（相对路径以该 YAML 所在目录为基准）。
   - `control_hz`：与 `dataflow` 里 `mujoco` 的 `tick` 一致。
   - `robots`：`prefix: item_1/`，`actuator_order` 与 **`Elfin5L.xml` 中 `<actuator>` 的 `name` 顺序**一致。
   - 顶层 **`joints:`**：为每个被控制的关节配置 `mode` 与 `unit`。
   - **`image_forward`**：键为模型中的相机名，值为输出 topic 配置。
3. **`task_robot.yaml` / `policy.yaml`**：`task_robot.yaml` 已与 `simulator.yaml` 对齐；后续接 policy 时沿用相同 `actuator_order` 与相机 topic。

**运行记录**：

- 2026-05-12：激活 `forge_runtime/.venv` 后执行 `dora build dataflow.test_action_source.yaml --uv` 通过；随后使用 `timeout 12s dora run dataflow.test_action_source.yaml --uv` 做短时间 smoke test。`mujoco`、`task_robot`、`test_action_source`、`image_viewer`、`stream_viewer` 均 ready。MuJoCo 成功映射 9 个 actuator，`task_robot` 持续收发 `proprio_state`、`action`、`image/overview`、`image/side`；两路场景相机图像 topic 均约 30 FPS。超时退出前未见 dataflow 配置错误。
- 2026-05-12：使用原生 MuJoCo viewer 手动调整控制量，虚拟底盘与 `joint1` ~ `joint6` 均可正常响应，未见异常抖动、方向异常、明显穿模、飞出或模型爆炸。

---

## 5. 仿真关节 / 执行器检查

**结论**：已完成自动 sweep smoke test 与原生 MuJoCo GUI 手动检查，两路场景相机图像 topic 正常；虚拟底盘与六轴机械臂控制均未见明显异常。详细记录见 `JOINT_SWEEP_CHECKLIST.md`。

---

## 6. 真机 / 文档对照边界

**结论**：本次交付覆盖仿真资产与仿真 workflow 配置；真机方向、零位、限位属于后续实机复核项，不阻塞当前仿真接入骨架。

- 后续拿到厂商 / 现场标定记录后，再更新 MJCF 或 `simulator.yaml` 裁剪范围。
- 真机复核结论应记入 `config/` 与根 `README.md`（版本、日期、责任人）。

## 交付复现命令

1. 进入 **`examples/03_workflows/simulation/mujoco_elfin5l/`**，按该目录 **`README.md`** 执行 `dora build` / `dora run`（需已并列克隆 **`forge_runtime`** 并完成 `uv sync --all-packages`）。
2. 复核 **`mujoco_elfin5l/simulator.yaml`** 与 **`mujoco_elfin5l/task_robot.yaml`** 的 `actuator_order`、关节映射与相机 topic。
