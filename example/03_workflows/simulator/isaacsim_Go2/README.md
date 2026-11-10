# Go2 Isaac Sim USD 示例

本示例将 `assets/mjcf/Go2.xml` 转换成 Isaac Sim 6 可用的 USD，并在独立
Stage 中加入地面、PhysX 场景、Dome/Sphere 光照、第三人称相机和随 Go2
base link 运动的第一视角相机。

## 当前资产

完整的 Isaac Sim 资产入口：

```text
assets/usd/Go2/Go2.usda
```

场景入口：

```text
example/03_workflows/simulator/isaacsim_Go2/go2_scene.usda
```

几何已通过 `--merge-mesh` 合并进 USD 层；迁移时仍需整体保留
`assets/usd/Go2/`，包括 `payloads/` 下的物理、材质和实例层。

## 重新转换

```bash
ISAAC_SIM="$HOME/下载/isaac-sim-standalone-6.0.1-linux-x86_64"

mkdir -p "$HOME/robots/go2/assets/usd"
"$ISAAC_SIM/python.sh" \
  "$ISAAC_SIM/standalone_examples/api/isaacsim.asset.importer.mjcf/mjcf_import.py" \
  --mjcf "$HOME/robots/go2/assets/mjcf/Go2.xml" \
  --usd-path "$HOME/robots/go2/assets/usd" \
  --no-import-scene \
  --no-fix-base \
  --merge-mesh
```

`--merge-mesh` 不能省略：当前 Isaac Sim 6.0.1 的非合并转换会生成引用
`geometries.usd` 的层，但不会保留该文件。

## Forge Isaac Sim双节点示例

`dataflow.yaml` 将同一套 RL 控制拆成两个独立 Dora 节点：

- `isaacsim`：直接运行独立节点
  `../../../../../issac_sim/src/issac_sim/main.py`，以200 Hz推进PhysX，
  使用Forge标准`Action`并输出标准`ProprioState`、`sim_status`；
- `go2_policy`：根据 `policy_state` 执行 50 Hz ONNX 推理，输出 12 关节
  Forge `Action`以及RL专用PD参数。

Go2场景、关节映射、初始状态和`policy_sync`参数位于
`simulator.yaml`；策略选择和速度指令仍位于`doraconfig.yaml`。运行前设置
Isaac Sim根目录：

```bash
cd "$HOME/robots/go2/example/03_workflows/simulator/isaacsim_Go2"
export ISAAC_SIM_ROOT="$HOME/下载/isaac-sim-standalone-6.0.1-linux-x86_64"
export FORGE_RUNTIME="$HOME/robots/forge_runtime"
"$HOME/robots/forge_runtime/.venv/bin/dora" run dataflow.yaml
```

## 运行流程

用户运行步骤：

1. 在`doraconfig.yaml`中选择策略和速度指令；
2. 在`simulator.yaml`中配置Go2初始姿态和仿真周期；
3. 运行上述`dora run dataflow.yaml`命令；
4. Forge Isaac Sim加载Go2场景并开始执行ONNX策略；
5. 按`Ctrl+C`停止数据流和仿真。

程序内部的数据流：

```text
Dora 启动Forge isaacsim与go2_policy节点
  → Forge isaacsim加载go2_scene.usda和Go2 Articulation
  → go2_policy 加载 policy.onnx 与 deploy.yaml
  → isaacsim 读取关节、机体姿态和角速度并发送 policy_state
  → go2_policy执行ONNX推理并返回Forge Action与control_profile
  → Forge isaacsim应用关节位置目标和PD参数
  → PhysX 执行 4 个 0.005 秒物理步
  → 输出ProprioState、policy_state和sim_status并循环
```

PhysX 以 200 Hz 运行，ONNX 策略以 50 Hz 运行。每个策略动作对应 4 个
物理步；姿态策略使用同步状态—动作控制，避免通信延迟导致失稳。

按`Ctrl+C`停止。当前`simulator.yaml`使用`gui: true`显示界面；服务器
运行时将其改为`gui: false`。

Stage 中可选择：

- `/World/Cameras/Overview`：第三人称相机；
- `/World/Go2/Geometry/base/BaseCamera`：绑定 base link 的第一视角相机；
- `/World/Lights/Dome`、`/World/Lights/Key`：环境光与主光源；
- `/World/Ground`：带碰撞的地面。
