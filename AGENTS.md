<!-- Scope: project-local -->
# AGENTS.md — tripadvisor-intel

> Scope: project-local — this file governs the tripadvisor-intel codebase and autonomous agent workflows.

## Read Order
1. This file → 2. `README.md` → 3. `run_tests.py`.

## Core Principles & Hard Rules
1. **Multi-layer Egress**:
   - Primary: SerpApi TripAdvisor engine (`SerpApiTransport`) for zero-captcha, high-stability structured extraction.
   - Secondary / Direct: `curl_cffi` TLS client impersonation with DataDome awareness.
   - Mock: `MockTransport` for deterministic, offline testing without burning API credits.
2. **Fail-Open Reasoning Guarantee**:
   - Rule-based algorithmic metrics (Value Discrepancy Index, Rank Dominance, Acute Red Flag Scanning, Persona Suitability) MUST ALWAYS run first.
   - LLM synthesis (Gemini / VectorEngine) enriches the dossier with natural language insights when API keys are available, but a dead LLM or missing key MUST NEVER crash the pipeline.
3. **No Keys in Code**:
   - API keys are discovered at runtime from environment variables, project `.env`, or well-known skill configs (`mcp-flight-search`, `Read-Media-Gemini`, `gemini-embedding-2-guide`).
4. **Cache Before Egress**:
   - Every search, place lookup, and dossier report is cached in SQLite (`data/tripadvisor.db`) with a 48h TTL.
   - Use `--refresh` to force live bypass.
5. **Surface Convergence**:
   - All capabilities converge on `tripadvisorintel`:
     - CLI: `bin/tripadvisor-intel <command>`
     - Python: `from tripadvisorintel import TripAdvisorClient`
     - FastMCP: `tripadvisorintel/mcp_server.py`

## Verification Gates
- Unit tests: `python3 run_tests.py` (23/23 passing)
- Live E2E tests: `python3 tests/test_e2e_live.py` (3/3 passing)
- Health check: `python3 bin/tripadvisor-intel doctor --live`
