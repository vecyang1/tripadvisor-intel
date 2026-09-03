# Changelog — tripadvisor-intel

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-09-03

### Added
- **Review Authenticity & Astroturfing Audit**:
  - Review author credibility analysis (throwaway account detection).
  - Bimodal polarization scoring (detecting unnatural 5★ vs 1★ splits).
  - Overall rating vs subratings disparity audit.
- **Defensive Multi-Lingual & URL Parsing**:
  - `extract_place_id`: Directly extracts Place IDs from full TripAdvisor URLs (`/Hotel_Review-g...-d12345-...`), query strings, or numeric IDs.
  - `parse_ranking_string`: Extended with multi-lingual regex matching for English, French, Vietnamese, and Chinese formats.
  - `safe_float` & `safe_int`: Support European comma decimals (`4,8` -> 4.8), bubble strings (`bubble_45` -> 4.5), and star strings (`4.5 of 5 stars`).
- **Expanded Adversarial Threat Vectors ("测遍会说谎的那一半")**:
  - Added regex threat vectors for bait-and-switch room transfers, food poisoning / acute gastrointestinal illness, broken air conditioning / infrastructure failure, unusable Wi-Fi, and review bribery / coercion.
  - Dynamically penalizes persona scores and injects warning caveats when acute red flags are detected.
- **Multi-Page Review Pagination & File Export**:
  - Added `reviews_pages` argument across SDK, CLI (`--reviews-pages`), and MCP server.
  - Added `--output / -o` argument to all CLI subcommands for direct file saving.
- **Expanded Test Suite**:
  - Expanded unit test suite to 31 tests in `run_tests.py` (100% pass).
  - Expanded live E2E test suite to 5 tests in `tests/test_e2e_live.py` (verifying live URL resolution, multi-vertical support, and review pagination).

## [1.0.0] - 2026-09-03

### Added
- **Core Architecture**:
  - `SerpApiTransport` integration supporting `engine=tripadvisor` and `engine=tripadvisor_place`.
  - Pydantic domain models: `PlaceSummary`, `PlaceDetail`, `Subrating`, `PriceRange`, `ReviewItem`, `ReviewDistribution`, `DossierReport`, `RedFlagItem`, `PersonaFitScore`.
  - Defensive parsers in `parsers.py` supporting comma-separated rank numbers, multi-format review distributions, and dictionary/string room features.
  - SQLite persistent cache with 48-hour TTL in `data/tripadvisor.db`.
- **Reasoning Engine**:
  - Value Discrepancy Index auditing property rating vs Value subrating.
  - Acute Red Flag regex scanner covering cleanliness, noise, scams/billing, and safety.
  - Multi-persona suitability evaluation (Solo Nomad, Couples, Family).
  - Optional fail-open Gemini / VectorEngine LLM natural language synthesis.
  - Actionable walk-in brief and negotiation baseline generation.
- **Surfaces**:
  - Command-line interface `bin/tripadvisor-intel` with `search`, `place`, `reason`, `doctor`, and `cache` subcommands.
  - Python SDK `TripAdvisorClient`.
  - Standard JSON-RPC FastMCP server in `mcp_server.py`.
- **Verification**:
  - 23 unit tests in `run_tests.py` (100% pass).
  - 3 live E2E integration tests in `tests/test_e2e_live.py` against real TripAdvisor properties.
