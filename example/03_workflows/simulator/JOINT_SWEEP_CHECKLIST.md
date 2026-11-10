# Go2 仿真全关节 min / max / 归零检查记录

本文件记录 `mujoco_Go2_joint_sweep` 工作流下的人工观察结果。它是逐关节
验收表：每个关节依次到达 MJCF 下限、上限，再回到 home。

## 检查前提

- 工作流：`example/03_workflows/simulator/mujoco_Go2_joint_sweep/`
- 模型：`assets/mjcf/scene.xml`（`item_1/` 前缀，12 个位置执行器）
- 动作源：`mujoco_Go2_joint_sweep/joint_sweep_source.py`
- 非活动关节保持 home，不强制数学零位（小腿限位全部为负）

## 关节验收表

| 关节 | min | max | home | 到位 | 回 home | 备注 |
|------|-----|-----|------|------|---------|------|
| FL_hip_joint | -1.0472 | 1.0472 | -0.1 | ☐ | ☐ | |
| FL_thigh_joint | -1.5708 | 3.4907 | 0.9 | ☐ | ☐ | |
| FL_calf_joint | -2.7227 | -0.83776 | -1.8 | ☐ | ☐ | 归零=home |
| FR_hip_joint | -1.0472 | 1.0472 | 0.1 | ☐ | ☐ | |
| FR_thigh_joint | -1.5708 | 3.4907 | 0.9 | ☐ | ☐ | |
| FR_calf_joint | -2.7227 | -0.83776 | -1.8 | ☐ | ☐ | 归零=home |
| RL_hip_joint | -1.0472 | 1.0472 | -0.1 | ☐ | ☐ | |
| RL_thigh_joint | -0.5236 | 4.5379 | 0.9 | ☐ | ☐ | |
| RL_calf_joint | -2.7227 | -0.83776 | -1.8 | ☐ | ☐ | 归零=home |
| RR_hip_joint | -1.0472 | 1.0472 | 0.1 | ☐ | ☐ | |
| RR_thigh_joint | -0.5236 | 4.5379 | 0.9 | ☐ | ☐ | |
| RR_calf_joint | -2.7227 | -0.83776 | -1.8 | ☐ | ☐ | 归零=home |

## 运行命令

```bash
source "$HOME/robots/forge_runtime/.venv/bin/activate"
cd "$HOME/robots/go2/example/03_workflows/simulator/mujoco_Go2_joint_sweep"
dora run dataflow.yaml
```

## 检查记录

- 待填：运行 `mujoco_Go2_joint_sweep` 后，按上表勾选每个关节是否到达
  min/max 并回到 home；记录机身是否跌倒、穿模或控制抖动。
