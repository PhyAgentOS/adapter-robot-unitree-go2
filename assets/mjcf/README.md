# MJCF（MuJoCo）

仿真用 **`scene.xml` / `Go2.xml` ** 等直接放在 **`assets/mjcf/` 本目录**（与 `README.md` 同级），不再使用额外子包名。

## 资产状态

MJCF 已完成导入并作为本仓交付资产维护。运行所需 OBJ mesh 位于
`assets/mjcf/assets/`，常规仿真、CI 与示例不再依赖外部
`robot-mj-model` 仓库。

`scripts/sync_mjcf_from_robot_mj_model.sh` 仅作为历史导入工具保留；重新导入外部资产前需确认来源版本，并在根 `README.md` 或 MR 中记录变更原因。

## 场景入口

| 文件 | 说明 |
|------|------|
| `scene.xml` | 地面 + 机器狗，`attach` 前缀 `item_1/` |
| `Go2.xml` | 机器狗主体 |

## 与 GLB 的关系

见 `assets/glb/README.md`。仿真入口使用 `assets/mjcf/scene.xml`，不要把 `assets/glb/Go2.xml`（pipeline 归一化产物）误当仿真入口。
