import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SourceBaselineTests(unittest.TestCase):
    def check(self, tamper=None, extra_override=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'packaging').mkdir()
            source = {}
            for name in ['README.md', 'pyproject.toml', 'driver.py']:
                path = root / name
                path.write_text('original')
                source[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / 'packaging/forge-source.json').write_text(json.dumps({'commit': 'original', 'files': source}))
            maintenance = {}
            for name in ['README.md', 'pyproject.toml']:
                (root / name).write_text('reviewed maintenance')
                maintenance[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
            if extra_override:
                maintenance['driver.py'] = source['driver.py']
            (root / 'packaging/maintenance-source.json').write_text(json.dumps({'original_commit': 'original', 'files': maintenance}))
            if tamper:
                (root / tamper).write_text('unexpected change')
            target = root / 'packaging/verify_source.py'
            target.write_text(Path(__file__).with_name('verify_source.py').read_text())
            return subprocess.run([sys.executable, str(target)], capture_output=True, text=True).returncode

    def test_approved_metadata_and_docs(self):
        self.assertEqual(self.check(), 0)

    def test_driver_tampering_rejected(self):
        self.assertNotEqual(self.check(tamper='driver.py'), 0)

    def test_runtime_override_rejected(self):
        self.assertNotEqual(self.check(extra_override=True), 0)


if __name__ == '__main__':
    unittest.main()
