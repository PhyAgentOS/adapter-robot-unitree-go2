"""Point Cyclone DDS at the library bundled in the PyInstaller image."""

from __future__ import annotations

import os
import sys
from pathlib import Path


bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
os.environ["CYCLONEDDS_HOME"] = str(bundle_root / "cyclonedds_runtime")
