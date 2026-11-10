# Go2 High Level — Forge 示例（SportClient）

最小 Forge/Dora 示例：单节点封装 Unitree `SportClient`，用本地 HTTP
操作技能。**不接入** `robots_go2` driver / `main`；关节低层控制见
`../low_level/`。

## 本目录文件

```text
dataflow.yaml          # 单节点 Dora 图
node.py                # Dora 节点 + HTTP(:8770)
sport_client.py        # SportClient / 急停 / 速度看门狗
play_go2_real_skill.py # 操作脚本
realrobotconfig.yaml
requirements.txt
```

## 依赖

```bash
source "$HOME/robots/forge_runtime/.venv/bin/activate"
cd "$HOME/robots/go2/example/03_workflows/real/high_level"
CYCLONEDDS_HOME=/usr/local uv pip install -r requirements.txt
```

电脑有线网卡应配置为 `192.168.123.x/24`。默认
`network_interface: auto` 仅在恰好找到一个该网段网卡时通过。

## 启动

机器人应处于正常落地姿态，并在 App 中启用 `sport_mode`。

```bash
source "$HOME/robots/forge_runtime/.venv/bin/activate"
cd "$HOME/robots/go2/example/03_workflows/real/high_level"
dora run dataflow.yaml
```

另一个终端：

```bash
python3 play_go2_real_skill.py preflight
python3 play_go2_real_skill.py arm
python3 play_go2_real_skill.py status
python3 play_go2_real_skill.py stand_up
python3 play_go2_real_skill.py balance_stand
python3 play_go2_real_skill.py hello
python3 play_go2_real_skill.py sit
python3 play_go2_real_skill.py rise_sit
python3 play_go2_real_skill.py recovery_stand
python3 play_go2_real_skill.py stand_down
python3 play_go2_real_skill.py damp
```

`velocity` 会先进入 `BalanceStand`，再按 5Hz 刷新 `Move`（限幅
`|vx|≤0.3`、`|vy|≤0.2`、`|wz|≤0.5`）：

```bash
python3 play_go2_real_skill.py velocity \
  --vx 0.1 --vy 0 --wz 0 --duration 2
```

`damp` 只允许在 `stand_down` 之后。`arm` 只建连并等待新鲜
`rt/lowstate`，不会自行触发动作。

## 停止

```bash
python3 play_go2_real_skill.py stop
python3 play_go2_real_skill.py disarm
```

软件急停持续发送 `StopMove → StandDown`。原厂手柄 `L2+B` 始终是首选
硬件急停。
