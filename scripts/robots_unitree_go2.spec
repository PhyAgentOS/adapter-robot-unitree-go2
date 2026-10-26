# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa: F821

from __future__ import annotations

import os
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_package_dir = os.path.dirname(_spec_dir)
_src_dir = os.path.join(_package_dir, "src")
_sdk_dir = os.path.join(_package_dir, "vendor", "unitree_sdk2_python")
_cyclonedds_prefix = os.environ.get(
    "CYCLONEDDS_HOME", os.path.join(_package_dir, ".deps", "cyclonedds")
)

sys.path.insert(0, _sdk_dir)
sdk_data = [
    (
        os.path.join(_sdk_dir, "unitree_sdk2py", "utils", "lib", "crc_amd64.so"),
        "unitree_sdk2py/utils/lib",
    )
]
cyclonedds_binaries = collect_dynamic_libs("cyclonedds")
cyclonedds_binaries.append(
    (
        os.path.join(_cyclonedds_prefix, "lib", "libddsc.so"),
        "cyclonedds_runtime/lib",
    )
)

a = Analysis(
    [os.path.join(_src_dir, "robots_unitree_go2", "main.py")],
    pathex=[_src_dir, _sdk_dir, _package_dir],
    binaries=cyclonedds_binaries,
    datas=sdk_data,
    hiddenimports=collect_submodules("unitree_sdk2py")
    + collect_submodules("cyclonedds")
    + ["dora", "dora_rs", "numpy", "pyarrow", "yaml"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(_spec_dir, "runtime_cyclonedds.py")],
    excludes=["pytest", "unittest", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="robots_unitree_go2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
