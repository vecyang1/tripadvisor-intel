"""Unit tests for GoogleSearchResolver."""

import unittest
from unittest.mock import patch, MagicMock
from tripadvisorintel.transports.google_search import GoogleSearchResolver


class TestGoogleSearchResolver(unittest.TestCase):
    def test_resolver_missing_credentials(self):
        resolver = GoogleSearchResolver(api_key=None, cx=None)
        results = resolver.search_tripadvisor("Monkey Island")
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
        results = resolver.search_tripadvisor("Monkey Island")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].place_id, "5979069")
        self.assertEqual(results[0].title, "Monkey Island (Cat Ba) - All You Need to Know BEFORE You Go")
        self.assertEqual(results[1].place_id, "7182682")


if __name__ == "__main__":
    unittest.main()
