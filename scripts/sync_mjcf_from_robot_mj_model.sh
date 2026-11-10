#!/usr/bin/env bash
# 历史导入工具：从 robot-mj-model 导入 Elfin5L MJCF 到 assets/mjcf/。
# 当前交付资产已落盘到本仓；常规开发、CI 与仿真示例不再需要运行本脚本。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_SRC="$(cd "$ROOT/../.." && pwd)/robot-mj-model/models/Elfin5L"
SRC="${ELFIN5L_MJCF_SRC:-$DEFAULT_SRC}"
DST="$ROOT/assets/mjcf"

if [[ ! -d "$SRC" ]]; then
  echo "Source not found: $SRC" >&2
  echo "Set ELFIN5L_MJCF_SRC to your robot-mj-model/models/Elfin5L path." >&2
  exit 1
fi

mkdir -p "$DST"
rsync -a --delete --exclude='*.glb' --filter='protect README.md' "$SRC/" "$DST/"
echo "Synced MJCF assets:"
echo "  from: $SRC"
echo "  to:   $DST"
