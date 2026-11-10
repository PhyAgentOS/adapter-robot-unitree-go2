#!/usr/bin/env bash
# 兼容 unitree_r1 / 既有命名：转发到 build_pyinstaller.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/build_pyinstaller.sh" "$@"
