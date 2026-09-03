"""Unit tests for CLI commands in tripadvisorintel."""

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestCLI(unittest.TestCase):
    def test_cli_doctor(self):
        cmd = [sys.executable, str(PROJECT_ROOT / "bin" / "tripadvisor-intel"), "doctor", "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"doctor failed: {res.stderr}")
        self.assertIn('"status": "healthy"', res.stdout)

    def test_cli_cache_stats(self):
        cmd = [sys.executable, str(PROJECT_ROOT / "bin" / "tripadvisor-intel"), "cache", "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"cache failed: {res.stderr}")
        self.assertIn('"cache_enabled": true', res.stdout)

    def test_cli_output_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json") as tf:
            cmd = [sys.executable, str(PROJECT_ROOT / "bin" / "tripadvisor-intel"), "cache", "--json", "-o", tf.name]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            with open(tf.name, "r") as f:
                content = f.read()
            self.assertIn('"cache_enabled": true', content)


if __name__ == "__main__":
    unittest.main()
