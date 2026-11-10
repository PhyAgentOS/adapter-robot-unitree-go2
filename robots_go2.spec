# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

ROOT_DIR = Path.cwd()
SRC_DIR = ROOT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))

a = Analysis(
    ["src/robots_go2/main.py"],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        ("config/go2_config.yaml", "config"),
    ],
    hiddenimports=[
        "robots_go2",
        "robots_go2.config",
        "robots_go2.driver",
        "robots_go2.network",
        "robots_go2.main",
        "dora",
        "dora_rs",
        "typer",
        "yaml",
        "numpy",
        "pydantic",
        "click",
        "rich",
        "shellingham",
        "annotated_types",
        "typing_extensions",
        "packaging",
        "forge_common",
        "forge_msgs",
        "forge_robot",
        "unitree_sdk2py",
        "unitree_sdk2py.core.channel",
        "unitree_sdk2py.utils.crc",
        "unitree_sdk2py.idl.unitree_go.msg.dds_",
        "unitree_sdk2py.idl.default",
        "unitree_sdk2py.comm.motion_switcher.motion_switcher_client",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="robots_go2",
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
    icon=None,
)
