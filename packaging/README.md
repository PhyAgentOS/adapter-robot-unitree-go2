# Go2 高层节点构建

仓库根目录是 Forge `unitree_go2` 完整源码包，保留 `src/`、`example/`、
`assets/`、配置、原始 pyproject 和构建脚本。新增构建文件全部位于 `packaging/`。
`forge-source.json` 记录原始 91 个文件的摘要和来源提交；`verify_source.py`
验证原有实现没有被替换。

本构建直接以原有 `example/03_workflows/real/high_level/node.py` 为入口，
生成 `robots_unitree_go2`。没有新增替代驱动，也没有改写原有控制器。
启动参数与该文件相同：`--config`、`--host`、`--port`。原有根目录构建脚本
仍对应低层关节节点，不能混用。

`packaging/vendor/` 使用固定提交的官方 Unitree SDK 与 Cyclone DDS 子模块，
来源记录在 `dependencies.json`。`pyproject.toml` 与 `uv.lock` 只描述高层
构建依赖，避免改写原始机器人包的项目文件。

```bash
git submodule update --init --recursive
python3 packaging/verify_source.py
bash packaging/build.sh
./dist/robots_unitree_go2 --help
```

构建脚本在原始 Cyclone DDS 提交上应用 `patches/` 中的上游 tracing 修复；
本地依赖已应用相同补丁时会验证并复用。补丁来源和摘要见 `dependencies.json`。

构建产物为独立单文件节点和单入口 tar.gz，事实记录在 `dist/node-build.json`。
已发布版本的入口、整包 SHA256、大小和来源提交见
[`releases/1.0.1.json`](releases/1.0.1.json)。该预编译包在 Ubuntu 24.04 x86_64
构建并验收，未进行 Ubuntu 20.04 CI 构建；其他系统应先核对兼容性或从源码构建。
正常运行由 Skill 的 Dora dataflow 启动，HTTP 只绑定本机。启动不 arm；原始
客户端 `play_go2_real_skill.py` 可继续用作人工验收工具。
