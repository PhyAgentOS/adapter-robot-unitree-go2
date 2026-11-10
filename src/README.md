# Forge 机器人节点源码（`src/`）

本目录是 Go2 专用 Forge 节点源码的归宿。

当前节点：

- **`robots_go2/`**（Forge 标准交付入口）
  - `driver.py`：`Go2Driver(BaseRobotDriver)`，
    `connect` / `disconnect` / `get_state`→`JointState` /
    `set_command`→`JointCommand`
  - `main.py`：调用 `forge_robot.run_dora_robot_node`
  - 配置：`config/go2_config.yaml`
  - 依赖：`forge-msgs` + `forge-robot`（见根目录 `pyproject.toml`）

仿真九技能与 High Level SportClient 示例在 `example/03_workflows/`，
不放在本目录。
