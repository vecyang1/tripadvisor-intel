import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure agent-search-sdk is discoverable
SDK_PATH = "/Users/vecsatfoxmailcom/Documents/A-coding/26.09.03-agent-search-sdk"
if os.path.exists(SDK_PATH) and SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

if "search_sdk" not in sys.modules:
    try:
        import search_sdk
    except ImportError:
        import types
        dummy = types.ModuleType("search_sdk")
        dummy.search = MagicMock()
        sys.modules["search_sdk"] = dummy

from tripadvisorintel.transports.google_search import GoogleSearchResolver


class TestGoogleSearchResolver(unittest.TestCase):
    def test_resolver_missing_credentials(self):
        resolver = GoogleSearchResolver(api_key=None, cx=None)
        results = resolver.search_tripadvisor("Monkey Island", use_agent_sdk=False)
        self.assertEqual(results, [])

    @patch("urllib.request.urlopen")
    def test_resolver_url_and_place_id_parsing(self, mock_urlopen):
        fake_response = {
            "items": [
                {
                    "title": "Monkey Island (Cat Ba) - All You Need to Know BEFORE You Go - Tripadvisor",
                    "link": "https://www.tripadvisor.com/Attraction_Review-g5979069-d5979069-Reviews-Monkey_Island-Cat_Ba_Hai_Phong_Province.html",
                    "snippet": "Monkey Island in Cat Ba offers boat tours and hiking..."
                },
                {
                    "title": "Hotel Royal Hoi An - Mgallery - Tripadvisor",
                    "link": "https://www.tripadvisor.com/Hotel_Review-g298082-d7182682-Reviews-Hotel_Royal_Hoi_An.html",
                    "snippet": "Luxury riverside hotel in Hoi An..."
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = str(fake_response).replace("'", '"').encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        resolver = GoogleSearchResolver(api_key="test-key", cx="test-cx")
        results = resolver.search_tripadvisor("Monkey Island", use_agent_sdk=False)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].place_id, "5979069")
        self.assertEqual(results[0].title, "Monkey Island (Cat Ba) - All You Need to Know BEFORE You Go")
        self.assertEqual(results[1].place_id, "7182682")

    @patch("search_sdk.search")
    def test_resolver_via_agent_search_sdk(self, mock_search):
        mock_item = MagicMock()
        mock_item.title = "Monkey Island - All You SHOULD Know - Tripadvisor"
        mock_item.url = "https://www.tripadvisor.com/Attraction_Review-g737051-d5979069-Reviews-Monkey_Island.html"
        mock_item.snippet = "A very beautiful island in Cat Ba"

        mock_resp = MagicMock()
        mock_resp.results = [mock_item]
        mock_search.return_value = mock_resp

        resolver = GoogleSearchResolver()
        results = resolver.search_tripadvisor("Monkey Island")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].place_id, "5979069")
        self.assertEqual(results[0].title, "Monkey Island - All You SHOULD Know")


if __name__ == "__main__":
    unittest.main()
