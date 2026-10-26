#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${PACKAGE_DIR}/dist"
WORK_DIR="${PACKAGE_DIR}/build/pyinstaller"
VENV_DIR="${PACKAGE_DIR}/.venv_build"
REQUIREMENTS_FILE="${PACKAGE_DIR}/.venv_build.requirements.txt"
CYCLONEDDS_PREFIX="${CYCLONEDDS_HOME:-${PACKAGE_DIR}/.deps/cyclonedds}"

cd "${PACKAGE_DIR}"
test -f vendor/unitree_sdk2_python/setup.py || {
  echo "Unitree SDK submodule is missing; run git submodule update --init" >&2
  exit 1
}
test -f "${CYCLONEDDS_PREFIX}/lib/libddsc.so" || {
  echo "Cyclone DDS is missing; run ./scripts/build_cyclonedds.sh" >&2
  exit 1
}
mkdir -p "${DIST_DIR}" "${WORK_DIR}"
rm -rf "${VENV_DIR}"
rm -f "${REQUIREMENTS_FILE}" "${DIST_DIR}/robots_unitree_go2"

cleanup() {
  rm -rf "${VENV_DIR}"
  rm -f "${REQUIREMENTS_FILE}"
}
trap cleanup EXIT

uv venv --no-workspace "${VENV_DIR}" --python 3.11
uv export \
  --project "${PACKAGE_DIR}" \
  --no-dev \
  --frozen \
  --no-hashes \
  --no-emit-project \
  --output-file "${REQUIREMENTS_FILE}"
CYCLONEDDS_HOME="${CYCLONEDDS_PREFIX}" \
  uv pip sync --python "${VENV_DIR}/bin/python" "${REQUIREMENTS_FILE}"
uv pip install --python "${VENV_DIR}/bin/python" pyinstaller==6.16.0
export LD_LIBRARY_PATH="${CYCLONEDDS_PREFIX}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
"${VENV_DIR}/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --distpath "${DIST_DIR}" \
  --workpath "${WORK_DIR}" \
  "${SCRIPT_DIR}/robots_unitree_go2.spec"
test -x "${DIST_DIR}/robots_unitree_go2"
echo "OK: ${DIST_DIR}/robots_unitree_go2"
