#!/usr/bin/env python3
"""Create a deterministic, single-executable local Node artifact."""
import gzip
import hashlib
import io
import json
import tarfile
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
binary = root / "dist/robots_unitree_go2"
version = tomllib.loads((root / "packaging/pyproject.toml").read_text())["project"]["version"]
target = root / f"dist/robots_unitree_go2-{version}-linux-x86_64.tar.gz"
with target.open("wb") as stream:
    with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            data = binary.read_bytes()
            item = tarfile.TarInfo("robots_unitree_go2")
            item.size, item.mode = len(data), 0o755
            tar.addfile(item, io.BytesIO(data))
facts = {"artifact_id": f"robots_unitree_go2-{version}-linux-x86_64-tar-gz",
         "version": version, "entrypoint": "robots_unitree_go2",
         "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
         "size": target.stat().st_size, "archive": str(target),
         "source": json.loads((root / "packaging/forge-source.json").read_text())["commit"],
         "entry_source": "example/03_workflows/real/high_level/node.py",
         "distribution": "local build; not registered or published"}
(target.parent / "node-build.json").write_text(json.dumps(facts, indent=2) + "\n")
print(json.dumps(facts, indent=2))
