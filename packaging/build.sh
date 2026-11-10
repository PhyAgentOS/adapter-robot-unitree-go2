#!/usr/bin/env bash
set -euo pipefail
build_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(dirname "${build_dir}")"
python3 "${build_dir}/verify_source.py"
test -f "${build_dir}/vendor/unitree_sdk2_python/setup.py"
test -f "${build_dir}/vendor/cyclonedds/CMakeLists.txt"
dds_patch="${build_dir}/patches/cyclonedds-tracing-buffer.patch"
if patch --batch --silent --dry-run -p1 -d "${build_dir}/vendor/cyclonedds" < "${dds_patch}"; then
    patch --batch --silent -p1 -d "${build_dir}/vendor/cyclonedds" < "${dds_patch}"
elif ! patch --batch --silent --dry-run -R -p1 -d "${build_dir}/vendor/cyclonedds" < "${dds_patch}"; then
    echo "Cyclone DDS source does not match the pinned tracing patch" >&2
    exit 1
fi
export CYCLONEDDS_HOME="${build_dir}/.deps/cyclonedds"
cmake -S "${build_dir}/vendor/cyclonedds" -B "${build_dir}/.build/dds" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="${CYCLONEDDS_HOME}" \
    -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF -DBUILD_IDLC=ON -DENABLE_SSL=NO
cmake --build "${build_dir}/.build/dds" --parallel 4
cmake --install "${build_dir}/.build/dds"
uv sync --project "${build_dir}" --frozen --python 3.11
export LD_LIBRARY_PATH="${CYCLONEDDS_HOME}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
"${build_dir}/.venv/bin/pyinstaller" --noconfirm --clean \
  --distpath "${root_dir}/dist" --workpath "${build_dir}/.build/pyinstaller" \
  "${build_dir}/high_level.spec"
"${root_dir}/dist/robots_unitree_go2" --help
python3 "${build_dir}/package_node.py"
