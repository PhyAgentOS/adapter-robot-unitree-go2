# Go2 九技能仿真 — Forge 示例

本目录自包含策略节点（`policy_node.py` + `runtime.py` + `messages.py`），
仿真用 **`forge_runtime` 通用 mujoco**，图像用 `image_viewer`。
**不放在 `src/`**，也不使用本仓旧的 `go2_mujoco`。

## 前置目录

不复制 Unitree 策略文件，要求同级：

```text
$HOME/robots/
├── forge_runtime/
├── go2/
└── unitree-rl/
```

七个 ONNX 与部署参数从
`unitree-rl/unitree_rl_mjlab/deploy/robots/go2/config/policy/` 读取，
路径见 `policyconfig.yaml`（`velocity`、`stairs_blind`、`footstand`、
`handstand`、`getup`、`bound`、`pronk`）。
相关链接: https://gitlab.ex-ai.cn/meta-emt/algorithms/unitree-rl
https://c8nm9x81r8.feishu.cn/wiki/H7eVwIRQ9iYVl0kviQrcw7FYnjR

## 本目录文件

```text
dataflow.yaml       # forge mujoco + policy_node + image_viewer
policy_node.py      # ONNX / FSM / HTTP(:8770)
runtime.py
messages.py
play_go2_skill.py
simulator.yaml      # mujoco 配置（含 policy_state）
policyconfig.yaml
```

## 安装与运行

```bash
cd "$HOME/robots/forge_runtime"
uv sync --all-packages
uv pip install onnxruntime
```

```bash
source "$HOME/robots/forge_runtime/.venv/bin/activate"
cd "$HOME/robots/go2/example/03_workflows/simulator/mujoco_Go2_9skills"
dora build dataflow.yaml
dora run dataflow.yaml
```

另开终端：

```bash
cd "$HOME/robots/go2/example/03_workflows/simulator/mujoco_Go2_9skills"
python3 play_go2_skill.py stairs_blind
```

技能：`passive`、`fixstand`、`velocity`、`stairs_blind`、`footstand`、
`handstand`、`getup`、`bound`、`pronk`。
