#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${PACKAGE_DIR}/vendor/cyclonedds"
BUILD_DIR="${PACKAGE_DIR}/build/cyclonedds"
PREFIX_DIR="${PACKAGE_DIR}/.deps/cyclonedds"

test -f "${SOURCE_DIR}/CMakeLists.txt" || {
  echo "Cyclone DDS submodule is missing; run git submodule update --init" >&2
  exit 1
}

cmake -S "${SOURCE_DIR}" -B "${BUILD_DIR}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${PREFIX_DIR}" \
  -DBUILD_EXAMPLES=OFF \
  -DBUILD_TESTING=OFF \
  -DBUILD_IDLC=ON \
  -DENABLE_SSL=NO
cmake --build "${BUILD_DIR}" --parallel
cmake --install "${BUILD_DIR}"
echo "OK: ${PREFIX_DIR}"
