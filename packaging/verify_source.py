#!/usr/bin/env python3
"""Verify every original Forge file; build additions live alongside the source."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = json.loads((root / "packaging/forge-source.json").read_text())
maintenance = json.loads((root / "packaging/maintenance-source.json").read_text())
if maintenance["original_commit"] != source["commit"] or set(maintenance["files"]) != {"README.md", "pyproject.toml"}:
    raise SystemExit("Invalid 1.0.0 maintenance source baseline")
expected = source["files"] | maintenance["files"]
changed = [name for name, digest in expected.items()
           if not (root / name).is_file()
           or hashlib.sha256((root / name).read_bytes()).hexdigest() != digest]
if changed:
    raise SystemExit(f"Forge source differs: {changed}")
print(f"Verified {len(expected)} source files with the 1.0.0 metadata/documentation maintenance baseline")
