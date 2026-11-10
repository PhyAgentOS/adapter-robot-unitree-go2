"""Use the native DDS runtime embedded in the executable."""
import os
import sys
from pathlib import Path

os.environ["CYCLONEDDS_HOME"] = str(Path(sys._MEIPASS) / "cyclonedds_runtime")
