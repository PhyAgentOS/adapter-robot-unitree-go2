# go2 构型说明

## 构型概览

> 当前仓库在 `assets/mjcf/` 和 `assets/glb/` 中未发现可直接用于 Markdown 的机器人预览图。

Unitree Go2 四足机器人，具备四条三自由度腿，可用于运动控制与感知任务。

- **构型类别**：四足机器人

## 支持引擎

| 引擎 | 支持情况 | 依据 |
|---|---|---|
| 真机 | 支持 | `src/robots_go2/` |
| MuJoCo | 支持 | `assets/mjcf/scene.xml` |
| Isaac Sim / Isaac Lab | 支持 Isaac Sim 接入 | `assets/usd/Go2/Go2.usda` |

## 模型资产

- [`assets/mjcf/scene.xml`](assets/mjcf/scene.xml)
- [`assets/mjcf/Go2.xml`](assets/mjcf/Go2.xml)
- [`assets/glb/Go2.glb`](assets/glb/Go2.glb)
- [`assets/usd/Go2/Go2.usda`](assets/usd/Go2/Go2.usda)


> “支持”仅表示仓库中存在对应驱动、模型或可执行工作流；实际运行仍需满足硬件、SDK 与运行环境要求。
