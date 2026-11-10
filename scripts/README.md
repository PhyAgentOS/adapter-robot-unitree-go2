# 脚本

## 常规使用

| 脚本 | 作用 |
|------|------|
| `build_glb_robot_asset_pipeline.sh` | 调用 `robot_asset_pipeline` 输出到 `assets/glb/`（`Go2.glb`、`Go2.xml`、`meshes/`；默认 `--skip-preview`） |
| `build_pyinstaller.sh` | 隔离 venv + PyInstaller 打包 `robots_go2` → `dist/robots_go2` |
| `build_pyinstall.sh` | 兼容别名，转发到 `build_pyinstaller.sh` |

打包依赖根目录 `pyproject.toml` 与 `robots_go2.spec`。首次建议：

```bash
uv sync
./scripts/build_pyinstaller.sh
```

## 历史导入工具

以下脚本用于追溯或必要时重新导入外部资产。当前 Go2 资产已经落盘到本仓，常规开发、CI 与仿真示例不再依赖 `robot-mj-model` 仓库。

| 脚本 | 作用 |
|------|------|
| `sync_mjcf_from_robot_mj_model.sh` | 从 `robot-mj-model/models/Go2` 导入到 `assets/mjcf/`（排除 `*.glb`，protect `README.md`） |
| `sync_glb_from_upstream.sh` | 从外部 Go2 资产源拷贝所有 `*.glb` 到 `assets/glb/`（保持相对路径；源目录用 `ELFIN5L_MJCF_SRC`） |
