"""Test runner for tripadvisor-intel."""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from tests.test_models import TestModels
from tests.test_parsers import TestParsers
from tests.test_rules import TestRules
from tests.test_cache import TestCache
from tests.test_client import TestClient
from tests.test_cli import TestCLI
from tests.test_mcp import TestMCPServer
from tests.test_reviews import TestReviews
from tests.test_direct_api import TestDirectApiTransport
from tests.test_e2e_evolution import TestE2EEvolution


def suite():
    s = unittest.TestSuite()
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestModels))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestParsers))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestRules))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestCache))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestClient))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestCLI))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestMCPServer))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestReviews))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestDirectApiTransport))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestE2EEvolution))
    return s


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite())
    sys.exit(0 if result.wasSuccessful() else 1)
