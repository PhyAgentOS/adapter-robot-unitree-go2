# Go2（Forge 机器人交付包）

[English](README.md) | [简体中文](README_zh.md)

## BREAKING CHANGE：Forge 2.x / Dora 1.x 迁移

本次从 Forge 1.x / Dora 0.4.x 升级需要协同部署。节点对接前必须对齐 Forge 包、Dora CLI/coordinator/daemon、本节点及上下游节点的版本；不支持在 Forge 1.x 部署中只替换单个节点。可执行产物也需要使用匹配环境重新构建和部署。仍使用旧技术栈的部署请保留在 `stable/1.x`。

本轮验证的 Python 基线为 `forge-msgs==2.1.0`、`Pillow==13.0.0`、`forge-common==2.1.0`、按需使用的 `forge-robot` / `forge-policy` / `forge-kinematics` / `forge-tool` 为 `2.0.0`，以及 `dora-rs==1.0.1`。同时遵守本仓库的 Python 和 SDK 平台要求。Forge 各包族独立发布，无需强行使用同一个版本号。Rust 节点继续使用已发布的 `forge_msgs` crate `2.0.0` 和 Dora `1.0.1`；Python Msgs `2.1.0` 不要求升级到尚未发布的 Rust `2.1.0`。消息命名空间 `forge_msgs.v1` 保持不变。

这里的 breaking change 指旧技术栈的部署迁移，不代表真机、真实模型或长时间运行已完成验收。实际测试和未完成项见[本轮验证报告](migration/msgs-2.1.0-report.json)。

[查看机器人构型说明](description.md)

## 交付内容

| 内容 | 路径 |
|------|------|
| **MJCF + meshes** | `assets/mjcf/`，仿真入口为 `scene.xml`，主模型为 `Go2.xml` |
| **GLB / 可视化资产** | `assets/glb/`，由 `robot_asset_pipeline` 生成
| **Forge 标准仿真 / 全关节验收** | `example/03_workflows/simulator/mujoco_Go2_joint_sweep/` |
| **九技能仿真示例** | `example/03_workflows/simulator/mujoco_Go2_9skills/` |
| **标准真机 driver** | `src/robots_go2/` + `example/03_workflows/real/low_level/` |
| **打包** | `pyproject.toml`、`robots_go2.spec`、`scripts/build_pyinstaller.sh` |
| **配置与标定模板** | `config/`（含 `go2_config.yaml`） |

标准 Forge 仿真接入见 `example/03_workflows/simulator/mujoco_Go2_joint_sweep/`
（通用 mujoco 节点）；九技能见 `mujoco_Go2_9skills/`。模型均指向本仓
`assets/mjcf/scene.xml`。

## 目录结构

| 路径 | 说明 |
|------|------|
| `assets/mjcf/` | MJCF、`scene.xml`、模型图片等 |
| `assets/glb/` | Web / 可视化 GLB |
| `assets/urdf/` | URDF 预留目录；当前上游资产包未提供 URDF |
| `example/01_sdk_tests/` | 直连厂商/底层驱动的最小测试（与 Forge 解耦） |
| `example/02_dora_tests/` | Dora 节点与 Topic 集成测试 |
| `example/03_workflows/` | 端到端 Forge workflow（仿真 / 真机 / 同构 / VR） |
| `src/robots_go2/` | Forge 标准 driver（`BaseRobotDriver`）与 Dora 入口 |
| `src/` | 九技能策略、专用 MuJoCo、Skill Manager 等节点 |
| `scripts/` | PyInstaller 打包、GLB 构建、历史资产导入 |
| `config/` | `go2_config.yaml`、相机、VR 标定等 |

## 资产状态

Go2 的 MJCF、mesh 与 GLB 已完成同步并落盘到本仓，后续仿真与交付以本仓 `assets/` 下内容为准：

- `assets/mjcf/`：MuJoCo 仿真入口，使用 `scene.xml`，`attach` 前缀为 `item_1/`
- `assets/glb/Go2.glb`：Web / 可视化交付资产（pipeline 产物）
- `assets/urdf/`：URDF与mjcf对应，可直接可视化

历史同步脚本 `scripts/sync_mjcf_from_robot_mj_model.sh` 与 `scripts/sync_glb_from_upstream.sh` 仅用于追溯或必要时重新导入外部资产；常规开发、CI 与仿真示例不再依赖 `robot-mj-model` 仓库。

## 厂商资料与版本出处

本仓不复制宇树版权 PDF；以下记录官方手册、SDK 说明、关节参数与依赖版本，
作为交付归档入口。

### 手册与官方入口

| 资料 | 出处 |
|------|------|
| 宇树支持站 / 产品文档 | https://support.unitree.com/ |
| Go2 开发者文档（含 High Level / Low Level） | https://support.unitree.com/home/zh/developer |
| Go2 App / `sport_mode`、机载网络说明 | 宇树支持站 Go2 用户手册与开发指南 |

真机有线网段按官方约定使用 `192.168.123.0/24`；本仓默认
`network_interface: auto`。

### SDK 说明

| 项目 | 版本 / 出处 |
|------|-------------|
| Python SDK | https://github.com/unitreerobotics/unitree_sdk2_python |
| High Level API | `unitree_sdk2py.go2.sport.sport_client.SportClient` |
| Low Level 话题 | `rt/lowstate`、`rt/lowcmd` |
| 官方 Low Level 示例 | `example/go2/low_level/go2_stand_example.py`；文档中的 `go2_low_level` 腿部摆动示例 |
| 模式互斥 | `MotionSwitcherClient`（`sport_mode` / `mcf`） |
| C++ SDK（参考） | https://github.com/unitreerobotics/unitree_sdk2 |

安装要求：保留 SDK 源码目录并以 editable 模式安装（普通 wheel 会漏掉
`crc_amd64.so`）。见
`example/03_workflows/real/high_level/requirements.txt`。

### 关节参数表

仿真与验收使用的关节顺序（FL → FR → RL → RR）：

```text
FL_hip FL_thigh FL_calf
FR_hip FR_thigh FR_calf
RL_hip RL_thigh RL_calf
RR_hip RR_thigh RR_calf
```

单位均为弧度、位置控制。限位与 `home` 来自本仓 `assets/mjcf/Go2.xml` /
`scene.xml`：

| 关节类型 | min (rad) | max (rad) | home (rad) | 出处 |
|----------|-----------|-----------|------------|------|
| hip（外摆） | -1.0472 | 1.0472 | ±0.1 | MJCF `abduction` |
| 前大腿 | -1.5708 | 3.4907 | 0.9 | MJCF `front_hip` |
| 后大腿 | -0.5236 | 4.5379 | 0.9 | MJCF `back_hip` |
| calf（小腿） | -2.7227 | -0.83776 | -1.8 | MJCF `knee` |

说明：

- 真机 SDK 消息顺序为 `FR → FL → RR → RL`（见 `src/robots_go2`）；
  仿真策略顺序为上表 FL 优先，见
  `example/.../mujoco_Go2_9skills/runtime.py`。
- 小腿限位全部为负；验收“归零”指回到 `home`，不是数学 `0rad`。
- 真机 Low Level 软件限位见 `src/robots_go2`
  （小腿下界放宽到 `-2.9`，用于官方摆动示例；仿真仍以 MJCF 为准）。

### 资产与依赖版本

| 内容 | 本仓路径 / 外部依赖 | 出处说明 |
|------|---------------------|----------|
| MuJoCo 模型 | `assets/mjcf/Go2.xml`、`scene.xml`、`assets/mjcf/assets/` | 本仓维护的仿真 SSOT |
| GLB | `assets/glb/Go2.glb` | `robot_asset_pipeline` 产物 |
| USD | `assets/usd/Go2/` | 可视化资产 |
| Forge 消息 / 运行时 | 同级 `forge_runtime/` | 复用环境与 `image_viewer`，不改其源码 |
| 九技能 ONNX | 同级 `unitree-rl/.../deploy/robots/go2/config/policy/` | 不复制进本仓；路径见 `policyconfig.yaml` |
| 标准真机 driver | `src/robots_go2/`、`example/03_workflows/real/low_level/` | `BaseRobotDriver` |
| 真机 High Level 技能 | `example/03_workflows/real/high_level/` | 封装 `SportClient` |
| 真机 Low Level（Forge driver） | `example/03_workflows/real/low_level/` | `robots_go2` + JointCommand 序列 |
| Forge 通用 MuJoCo / 全关节验收 | `example/03_workflows/simulator/mujoco_Go2_joint_sweep/` | `forge_runtime` mujoco |
| 仿真全关节验收 | `example/03_workflows/simulator/mujoco_Go2_joint_sweep/` | MJCF min/max/home |

升级 SDK、MJCF 或策略文件后，应同步更新本表中的 commit / 路径，并在 MR
中记录变更原因。

## 仿真接入流程

分步说明、与 `forge_runtime` 对接要点及复现命令见：

**`example/03_workflows/simulator/SIMULATION_INTEGRATION.md`**

摘要：资产齐 → 对齐约定 → 先跑 **`mujoco_Go2_joint_sweep/`**（通用
`forge_runtime` mujoco / 全关节验收）→ 再跑 **`mujoco_Go2_9skills/`**
（九技能）→ 与真机对表。

九状态强化学习示例使用 `mujoco_Go2_9skills/dataflow.yaml`，已接入 Idle、
FixStand、Velocity、Stairs-Blind、Footstand、Handstand、Getup、Bound 和
Pronk；通过本地 `http://127.0.0.1:8770` 切换技能与速度。七个 ONNX 不进仓，
运行时从同级 `unitree-rl/.../deploy/robots/go2/config/policy/` 读取。

## 安装与打包

```bash
# 仓库根；需同级 unitree_sdk2_python（editable，保留 crc_amd64.so）
uv sync
uv run robots-go2 --help

# PyInstaller 单文件（产物 dist/robots_go2）
./scripts/build_pyinstaller.sh
```

## `src/` 与 Forge 节点

**标准交付入口**为 `src/robots_go2/`：`Go2Driver` 继承
`forge_robot.BaseRobotDriver`，消息为 `JointState` / `JointCommand`，
`main.py` 调用 `forge_robot.run_dora_robot_node`。依赖
`forge-msgs` + `forge-robot`（见 `pyproject.toml` /
`real/low_level/requirements.txt`）。
配置为 `config/go2_config.yaml`（默认 `low_level_output_enabled: false`）。
示例工作流：`example/03_workflows/real/low_level/`。

九技能策略与仿真节点均在
`example/03_workflows/simulator/mujoco_Go2_9skills/`（`forge_runtime`
mujoco + 目录内 `policy_node.py`）。标准全关节验收见
`example/03_workflows/simulator/mujoco_Go2_joint_sweep/`。

Low Level 真机已收敛到 `robots_go2`（见 `real/low_level/`）。
High Level SportClient 仅为 `example/.../real/high_level/` 单节点示例
（不接入 `robots_go2` driver / `main`）。

## 交付与验收（摘要）

当前交付覆盖仿真资产、厂商资料入口、Forge 标准仿真/driver 骨架，以及
技能向真机工作流。单关节 low-level 测试必须按工作流 README 完成架空、急停
和逐项验证。VR/同构参数及实机方向、零位、限位现场复核属于后续阶段。

## Forge 2.x 迁移

本分支准备节点版本 `2.0.0`，适配 Dora 1.x，迁移验证锁定 Dora `1.0.1`。使用正式 Forge 2.x 分发包；Common 至少为 `2.1.0`。此次更新包括依赖锁文件与各独立可执行入口。

每轮报告必须列出仓库、改动和测试证据，包括各节点的 `dora run` 记录，以及包含 `adapter-forge-gateway` 的串联测试。缺少硬件或模型的验收项保持待验证。源码 PR 不等于正式发布；整体验收通过后再同步 GitLab。
