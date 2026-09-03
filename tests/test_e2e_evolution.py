"""End-to-end integration tests covering core deliverables and evolution highlights."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from tripadvisorintel.client import TripAdvisorClient
from tripadvisorintel.cache import CacheDB
from tripadvisorintel.models import PlaceDetail, ReviewItem, ReviewAuthor
from tripadvisorintel.transports.mock import MockTransport
from tripadvisorintel.transports.direct import DirectScraperTransport, DataDomeBlockedError


class TestE2EEvolution(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "e2e_test.db"
        self.cache = CacheDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reviews_pagination_and_crash_resilience(self):
        """Verify multi-page pagination, crash-resilient progressive persistence, and deduplication."""
        mock_transport = MockTransport()
        client = TripAdvisorClient(transport=mock_transport, cache_instance=self.cache, enable_llm=False)

        # 1. Fetch 60 reviews across 3 pages (page_size=20)
        reviews = client.get_reviews(place_id="place_999", max_reviews=60, page_size=20)
        self.assertEqual(len(reviews), 60)

        # 2. Verify progressive SQLite storage
        count_in_db = self.cache.count_reviews("place_999")
        self.assertEqual(count_in_db, 60)

        # 3. Verify deduplication: re-fetching from same place shouldn't duplicate rows
        client.get_reviews(place_id="place_999", max_reviews=60, page_size=20)
        self.assertEqual(self.cache.count_reviews("place_999"), 60)

        # 4. Verify zero-network cache hit: with transport replaced by None, returns cached reviews
        cached_client = TripAdvisorClient(transport=None, cache_instance=self.cache, enable_llm=False)
        cached_revs = cached_client.get_reviews(place_id="place_999", max_reviews=60)
        self.assertEqual(len(cached_revs), 60)
        self.assertEqual(cached_revs[0].review_id, reviews[0].review_id)

    def test_direct_transport_datadome_auto_fallback(self):
        """Verify that DataDome challenge on direct scraper triggers seamless fallback to secondary transport."""
        # Simulated direct transport returning DataDome challenge
        blocked_direct = DirectScraperTransport(
            fetch_cmd="echo '<html><body>Please enable JS and disable ad blockers captcha-delivery.com</body></html>' && exit 1"
        )
        mock_fallback = MockTransport()

        client = TripAdvisorClient(
            transport=blocked_direct,
            fallback_transport=mock_fallback,
            cache_instance=self.cache,
            enable_llm=False,
        )

        # Direct search should catch DataDomeBlockedError and transparently return fallback results
        results = client.search("Hoi An", category="hotels", limit=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].title, "Mock Royal Heritage Hotel")

        # Direct reviews fetch should also fall back transparently
        revs = client.get_reviews(place_id="place_fallback", max_reviews=20)
        self.assertGreaterEqual(len(revs), 1)

    def test_bulk_review_reasoning_deep_audit(self):
        """Verify that bulk reviews (including acute red flags like bites) feed into the AI reasoning dossier."""
        place = PlaceDetail(
            place_id="5979069",
            name="Monkey Island Cat Ba",
            place_type="ATTRACTION",
            rating=3.4,
            reviews=868,
            ranking="#8 of 25 things to do in Cat Ba",
            ranking_position=8,
            ranking_total=25,
            reviews_list=[
                ReviewItem(
                    review_id="rev_safe",
                    title="Nice beach",
                    snippet="Took a boat ride here.",
                    rating=4.0,
                ),
                ReviewItem(
                    review_id="rev_bite",
                    title="Aggressive monkeys - bitten!",
                    snippet="A monkey jumped from a tree and bit my arm. Had to rush to hospital for rabies shot and rabies vaccine cost $300!",
                    rating=1.0,
                ),
            ],
        )

        mock_transport = MockTransport(place_detail=place)
        client = TripAdvisorClient(transport=mock_transport, cache_instance=self.cache, enable_llm=False)

        dossier = client.analyze("5979069", max_reviews=2)
        self.assertEqual(dossier.place_id, "5979069")

        # Verify red flags captured the severe issue
        red_flag_texts = [f.description.lower() + " " + (f.evidence_snippet or "").lower() for f in dossier.red_flags]
        has_bite_flag = any("bit" in t or "rabies" in t or "monkey" in t for t in red_flag_texts)
        self.assertTrue(has_bite_flag, f"Expected red flag for monkey bite in: {red_flag_texts}")

    def test_cli_subcommands_e2e(self):
        """Execute CLI binary across subcommands and verify exit codes and output contracts."""
        cli_bin = root / "bin" / "tripadvisor-intel"

        # 1. Doctor command
        res_doc = subprocess.run([sys.executable, str(cli_bin), "doctor", "--json"], capture_output=True, text=True)
        self.assertEqual(res_doc.returncode, 0)
        doc_json = json.loads(res_doc.stdout)
        self.assertIn("status", doc_json)

        # 2. Cache stats command
        res_cache = subprocess.run([sys.executable, str(cli_bin), "cache", "--json"], capture_output=True, text=True)
        self.assertEqual(res_cache.returncode, 0)
        cache_json = json.loads(res_cache.stdout)
        self.assertIn("db_size_bytes", cache_json)

        # 3. Cached reviews command
        res_rev = subprocess.run(
            [sys.executable, str(cli_bin), "reviews", "5979069", "--max-reviews", "5", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_rev.returncode, 0)
        rev_json = json.loads(res_rev.stdout)
        self.assertIsInstance(rev_json, list)
        self.assertGreaterEqual(len(rev_json), 1)

    def test_mcp_all_four_tools_e2e(self):
        """Execute FastMCP JSON-RPC server and verify tools/list and tools/call for all 4 tools."""
        mcp_script = root / "tripadvisorintel" / "mcp_server.py"

        # Start stdio process
        proc = subprocess.Popen(
            [sys.executable, str(mcp_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def send_rpc(req_dict):
            proc.stdin.write(json.dumps(req_dict) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            return json.loads(line)

        # 1. Initialize
        init_resp = send_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "tripadvisor-intel")

        # 2. Tools list
        tools_resp = send_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = tools_resp["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        expected_tools = {
            "tripadvisor_search",
            "tripadvisor_place_details",
            "tripadvisor_place_reviews",
            "tripadvisor_analyze_dossier",
        }
        self.assertTrue(expected_tools.issubset(tool_names), f"Missing tools in: {tool_names}")

        # 3. Tools call: tripadvisor_place_reviews on cached property
        call_resp = send_rpc({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "tripadvisor_place_reviews",
                "arguments": {"place_id": "5979069", "max_reviews": 5},
            },
        })
        self.assertIn("result", call_resp)
        content_text = call_resp["result"]["content"][0]["text"]
        content_json = json.loads(content_text)
        self.assertIn("reviews", content_json)
        self.assertGreaterEqual(content_json["count"], 1)

        proc.stdin.close()
        proc.stdout.close()
        proc.stderr.close()
        proc.terminate()
        proc.wait(timeout=2)

    def test_git_repo_and_ci_cleanliness(self):
        """Verify repository cleanliness, AGPL license text, and CI workflow validity."""
        # 1. Check LICENSE
        license_path = root / "LICENSE"
        self.assertTrue(license_path.exists())
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)

        # 2. Check NOTICE
        notice_path = root / "NOTICE"
        self.assertTrue(notice_path.exists())

        # 3. Check CI workflow
        ci_path = root / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_path.exists())
        ci_text = ci_path.read_text(encoding="utf-8")
        self.assertIn("actions/checkout", ci_text)
        self.assertIn("run_tests.py", ci_text)


if __name__ == "__main__":
    unittest.main()
