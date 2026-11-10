# 模型对齐记录

## 结论

- 仿真入口：`assets/mjcf/scene.xml`
- 主模型：`assets/mjcf/Elfin5L.xml`
- attach 前缀：`item_1/`
- 场景位置：`scene.xml` 中 `body name="item_1"` 位于 `pos="0.0 0.0 0.0"`
- 场景相机：`overview_cam`、`side_cam` 为本仓交付场景补充，用于图像流 smoke check
- GLB：`assets/glb/elfin5l.glb`，仅作为 Web / 可视化交付资产

## 记录

- 2026-05-12：按 Aloha / RM65 / Bobacbot 交付结构建立 Elfin5L 仿真资产与 workflow 配置；仿真 SSOT 以 `assets/mjcf/scene.xml` 为准。真机方向、零位、限位待后续实机资料复核。
