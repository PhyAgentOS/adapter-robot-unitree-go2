#!/usr/bin/env python3
"""Verify every original Forge file; build additions live alongside the source."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = json.loads((root / "packaging/forge-source.json").read_text())
changed = [name for name, digest in source["files"].items()
           if not (root / name).is_file()
           or hashlib.sha256((root / name).read_bytes()).hexdigest() != digest]
if changed:
    raise SystemExit(f"Forge source differs: {changed}")
print(f"Verified {len(source['files'])} original files at {source['commit']}")
