"""Unit tests for MCP server protocol."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMCPServer(unittest.TestCase):
    def test_mcp_protocol(self):
        proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "tripadvisorintel" / "mcp_server.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(PROJECT_ROOT)
        )

        # 1. Initialize
        init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
        proc.stdin.write(init_req)
        proc.stdin.flush()
        init_resp = json.loads(proc.stdout.readline())
        self.assertEqual(init_resp.get("result", {}).get("serverInfo", {}).get("name"), "tripadvisor-intel")

        # 2. List tools
        list_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
        proc.stdin.write(list_req)
        proc.stdin.flush()
        list_resp = json.loads(proc.stdout.readline())
        tool_names = [t["name"] for t in list_resp.get("result", {}).get("tools", [])]
        self.assertIn("tripadvisor_search", tool_names)
        self.assertIn("tripadvisor_place_details", tool_names)
        self.assertIn("tripadvisor_analyze_dossier", tool_names)

        # 3. Unknown tool error check
        err_req = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "non_existent", "arguments": {}}}) + "\n"
        proc.stdin.write(err_req)
        proc.stdin.flush()
        err_resp = json.loads(proc.stdout.readline())
        self.assertIn("error", err_resp)

        proc.terminate()


if __name__ == "__main__":
    unittest.main()
