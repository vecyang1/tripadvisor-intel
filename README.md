# tripadvisor-intel

> Production-grade agentic TripAdvisor data acquisition, structured extraction, and AI reasoning engine.

`tripadvisor-intel` delivers a complete, autonomous loop for querying TripAdvisor, extracting verified place rankings, subratings, and review histories, and synthesizing actionable travel intelligence dossiers (Value-to-Price audit, acute red flags, traveler persona fit, and walk-in negotiation baselines).

---

## Key Features

- **Anti-Bot Resilient Egress**: Built on SerpApi's managed TripAdvisor engines (`tripadvisor` & `tripadvisor_place`), bypassing DataDome challenges and TLS fingerprinting.
- **Dual-Layer Reasoning Engine**:
  - *Layer 1 (Algorithmic / Ground Truth)*: Value Discrepancy Index, Rank Dominance Percentile, Acute Red Flag Scanning (cleanliness, noise, billing scams, negative ratio), and Persona Scoring (Solo Nomad, Couples, Family).
  - *Layer 2 (LLM Synthesis)*: Deep contextual synthesis powered by Gemini / VectorEngine with a strict **fail-open guarantee** (runs deterministically even when LLM is unavailable).
- **SQLite Persistent Caching**: 48-hour TTL cache in `data/tripadvisor.db` for instant ($0 marginal cost) replays.
- **Three Unified Surfaces**:
  1. **CLI**: Rich, human-friendly tables or clean JSON output (`tripadvisor-intel`).
  2. **Python SDK**: Typed Pydantic models (`from tripadvisorintel import TripAdvisorClient`).
  3. **FastMCP Server**: Standard JSON-RPC stdio server for Antigravity, Claude Code, and Codex subagents.

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/vecyang1/tripadvisor-intel.git
cd tripadvisor-intel

# Install dependencies or editable package
pip install -e .
# Or run standalone via bin/tripadvisor-intel
```

Or symlink to your local bin:
```bash
ln -sf $(pwd)/bin/tripadvisor-intel ~/.local/bin/tripadvisor-intel
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and set your keys:
```bash
cp .env.example .env
# Set SERPAPI_API_KEY=your_key
```

### 3. Diagnostics & Health Check

```bash
tripadvisor-intel doctor --live
```

---

## CLI Usage

### Search Places
Search hotels, restaurants, or attractions:
```bash
tripadvisor-intel search "Hoi An" --category hotels --limit 5
tripadvisor-intel search "Tokyo sushi" --category restaurants --json
tripadvisor-intel search "Da Nang" --category attractions
```

### Inspect Place Details & Subratings
Pass a numeric Place ID or full TripAdvisor URL:
```bash
tripadvisor-intel place 7182682
tripadvisor-intel place "https://www.tripadvisor.com/Hotel_Review-g298082-d7182682-Reviews-Hotel_Royal_Hoi_An.html"
tripadvisor-intel place 7182682 --reviews-pages 2 --json -o /tmp/hotel_royal.json
```

### Paginate Reviews (with SQLite Persistence)
Fetch and locally cache reviews (up to 800+ reviews):
```bash
# Fetch 40 reviews (default)
tripadvisor-intel reviews 5979069

# Fetch up to 100 or 800 reviews
tripadvisor-intel reviews 5979069 --max-reviews 100
tripadvisor-intel reviews "https://www.tripadvisor.com/Hotel_Review-g298082-d7182682-Reviews-Hotel_Royal_Hoi_An.html" --max-reviews 200 --json
```

### Generate AI Travel Intelligence Dossier
Generate deep reasoning, authenticity audit, red flag analysis, and negotiation baselines by Place ID, URL, or business name:
```bash
# By Place ID or URL (analyzing up to 100 reviews)
tripadvisor-intel reason 7182682 --max-reviews 100
tripadvisor-intel reason "https://www.tripadvisor.com/Restaurant_Review-g298082-d1121828-Reviews-Mango_Rooms-Hoi_An.html" --persona solo_nomad -o /tmp/mango_dossier.txt

# By Name search
tripadvisor-intel reason "Hotel Royal Hoi An" --persona couples --json
```

### Cache Management
```bash
tripadvisor-intel cache
tripadvisor-intel cache --clear
```

---

## Python SDK Example

```python
from tripadvisorintel import TripAdvisorClient

client = TripAdvisorClient()

# 1. Search
places = client.search("Hoi An", category="hotels", limit=5)
for p in places:
    print(f"#{p.position} {p.title} ({p.rating}★, {p.reviews} reviews) -> ID: {p.place_id}")

# 2. Get Details (numeric ID or full URL)
place = client.get_place("7182682")
print("Ranking:", place.ranking)
print("Subratings:", [(sr.category, sr.score) for sr in place.subratings])

# 3. Paginate Reviews (persisted to SQLite)
reviews = client.get_reviews("7182682", max_reviews=100)
print(f"Loaded {len(reviews)} reviews from cache or API")

# 4. Generate Intelligence Dossier
dossier = client.analyze("7182682", persona="solo_nomad", max_reviews=100)
print("Authenticity Score:", dossier.authenticity_score)
print("Walk-in Brief:", dossier.walk_in_brief)
print("Nomad Score:", dossier.persona_fits["solo_nomad"].score)
print("Red Flags:", [f.description for f in dossier.red_flags])
```

---

## Model Context Protocol (MCP) Server

To wire `tripadvisor-intel` into your MCP client (Claude Code, Antigravity, Cursor, etc.):

```json
{
  "mcpServers": {
    "tripadvisor-intel": {
      "command": "python3",
      "args": ["-m", "tripadvisorintel.mcp_server"]
    }
  }
}
```

Exposed Tools:
- `tripadvisor_search`: Search destinations, hotels, restaurants, attractions.
- `tripadvisor_place_details`: Retrieve full rankings, subratings, and review histories (supports URL or ID).
- `tripadvisor_place_reviews`: Retrieve paginated reviews with SQLite persistence.
- `tripadvisor_analyze_dossier`: Generate full AI travel intelligence reports with review authenticity audits.

---

## Verification & Testing

```bash
# Run unit tests (31 tests in ~0.5s)
python3 run_tests.py

# Run live integration tests against TripAdvisor (5 tests against real endpoints)
python3 tests/test_e2e_live.py
```

---

## License

AGPL-3.0-or-later. Copyright (c) 2026 V.
