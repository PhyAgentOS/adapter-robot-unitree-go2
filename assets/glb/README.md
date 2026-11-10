# GLB / 可视化（扁平：`assets/glb/` 根目录即交付物）

本目录与 Aloha / RM65 / Bobacbot 保持一致：交付相关文件直接放在 **`assets/glb/`** 下（与本 `README.md` 同级）。

## 当前文件（`robot_asset_pipeline` 生成）

| 文件 / 目录 | 说明 |
|-------------|------|
| `Go2.glb` | 由 `../mjcf/Go2.xml` 导出并压缩 |
| `Go2.xml` | **归一化后的 MJCF**（与 `../mjcf/` 中仿真用 XML **不是同一份**） |
| `assets/` | 流水线写出的网格，供上述 `Go2.xml` 引用 |


## 重新生成

在 **`robot_asset_pipeline`** 依赖可用的前提下，于本仓根目录：

```bash
./scripts/build_glb_robot_asset_pipeline.sh
```

或手动：

```bash
cd /path/to/robot_asset_pipeline
/home/donglinghan/miniforge3/bin/python main.py /path/to/robots/Go2/assets/mjcf/Go2.xml   -o /path/to/robots/Go2/assets/glb -n Go2 --skip-preview
```

需要 **1080 预览图** 时去掉 `--skip-preview` （需安装 Blender） 。

## 历史导入工具

`./scripts/sync_glb_from_upstream.sh` 仅作为历史导入工具保留，用于必要时从外部 Go2 资产源拷贝 `*.glb` 到 **`assets/glb/`**（保持相对路径）。当前交付以 pipeline 产物为准，常规开发不依赖外部资产仓。
