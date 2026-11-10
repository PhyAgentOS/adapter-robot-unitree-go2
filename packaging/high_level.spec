# Build the original Forge high-level node, without a replacement driver.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

build = Path(SPEC).resolve().parent
root = build.parent
sdk = build / "vendor/unitree_sdk2_python"
dds = Path(os.environ["CYCLONEDDS_HOME"])
high = root / "example/03_workflows/real/high_level"
a = Analysis(
    [str(high / "node.py")], pathex=[str(high), str(sdk)],
    binaries=collect_dynamic_libs("cyclonedds") + [
        (str(dds / "lib/libddsc.so"), "cyclonedds_runtime/lib")],
    datas=[(str(sdk / "unitree_sdk2py/utils/lib/crc_amd64.so"),
            "unitree_sdk2py/utils/lib")],
    hiddenimports=collect_submodules("unitree_sdk2py") +
                  collect_submodules("cyclonedds") + ["sport_client", "dora", "pyarrow", "yaml"],
    runtime_hooks=[str(build / "runtime_cyclonedds.py")],
    excludes=["pytest", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="robots_unitree_go2",
          console=True, strip=False, upx=False)
