#!/usr/bin/env bash
# 使用 monorepo 内 robot_asset_pipeline 从 MJCF 生成 GLB + 归一化 MJCF（交付用）
# 默认使用 miniforge Python；可用 ELFIN5L_PIPELINE_PYTHON 覆盖。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(cd "$ROOT/../.." && pwd)"
PIPE="$WORKSPACE/robot_asset_pipeline"
PYTHON_BIN="${ELFIN5L_PIPELINE_PYTHON:-/home/donglinghan/miniforge3/bin/python}"
IN_XML="$ROOT/assets/mjcf/Elfin5L.xml"
OUT_DIR="${ELFIN5L_GLB_OUT:-$ROOT/assets/glb}"
NAME="${ELFIN5L_GLB_NAME:-elfin5l}"
SKIP_PREVIEW="${ELFIN5L_SKIP_PREVIEW:-1}"

if [[ ! -f "$IN_XML" ]]; then
  echo "Missing input: $IN_XML" >&2
  exit 1
fi
if [[ ! -f "$PIPE/main.py" ]]; then
  echo "robot_asset_pipeline not found at: $PIPE" >&2
  exit 1
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

extra=()
if [[ "$SKIP_PREVIEW" == "1" ]]; then
  extra+=(--skip-preview)
fi

mkdir -p "$OUT_DIR"
cd "$PIPE"
"$PYTHON_BIN" main.py "$IN_XML" -o "$OUT_DIR" -n "$NAME" "${extra[@]}"
echo "Done: $OUT_DIR/${NAME}.glb and ${NAME}.xml (preview skipped unless ELFIN5L_SKIP_PREVIEW=0 and Blender installed)"
