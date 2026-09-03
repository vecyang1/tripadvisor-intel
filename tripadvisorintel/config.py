"""Central configuration for tripadvisor-intel.

Handles API key discovery, caching paths, and provider resolution.
Zero keys hardcoded.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TRIPADVISOR_DATA_DIR", PROJECT_DIR / "data"))
DB_PATH = DATA_DIR / "tripadvisor.db"

# Well-known external skill env paths for automatic key discovery
_FLIGHT_SEARCH_ENV = Path.home() / ".gemini/antigravity/skills/mcp-flight-search/.env"
_READ_MEDIA_ENV = Path.home() / ".claude/skills/Read-Media-Gemini/.env"
_EMBED_SKILL_ENV = Path.home() / ".claude/skills/gemini-embedding-2-guide/.env"
_SERPAPI_MCP_JSON = Path.home() / ".claude/skills/serpapi-mcp/.mcp.json"


def _parse_env_file(path: Path, key: str) -> Optional[str]:
    """Safely extract key from a .env file if it exists."""
    if not path.exists():
        return None
    try:
        match = re.search(rf"^{key}=(.+)$", path.read_text(), flags=re.MULTILINE)
        return match.group(1).strip().strip('"').strip("'") if match else None
    except Exception:
        return None


def serpapi_api_key() -> Optional[str]:
    """Discover primary SerpAPI key from environment, project .env, or skill configs."""
    # 1. Direct environment variable
    key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERP_API_KEY")
    if key:
        return key

    # 2. Project-local .env
    local_env = PROJECT_DIR / ".env"
    if local_env.exists():
        key = _parse_env_file(local_env, "SERPAPI_API_KEY") or _parse_env_file(local_env, "SERP_API_KEY")
        if key:
            return key

    # 3. Flight search skill .env
    key = _parse_env_file(_FLIGHT_SEARCH_ENV, "SERP_API_KEY") or _parse_env_file(_FLIGHT_SEARCH_ENV, "SERPAPI_API_KEY")
    if key:
        return key

    # 4. serpapi-mcp skill config
    if _SERPAPI_MCP_JSON.exists():
        try:
            mcp = json.loads(_SERPAPI_MCP_JSON.read_text())
            env_val = mcp.get("mcpServers", {}).get("serpapi-mcp", {}).get("env", {}).get("SERPAPI_API_KEY")
            if env_val and not env_val.startswith("op://"):
                return env_val
        except Exception:
            pass

    return None


def serpapi_api_keys() -> List[str]:
    """Discover all SerpAPI keys from environment, .env, or multi-key pool."""
    keys: List[str] = []
    seen = set()

    def _add(k: Optional[str]):
        if k and k not in seen and len(k) > 10:
            keys.append(k)
            seen.add(k)

    # 1. SERPAPI_API_KEYS (comma-separated env)
    raw_env = os.getenv("SERPAPI_API_KEYS")
    if raw_env:
        for piece in raw_env.split(","):
            _add(piece.strip())

    # 2. Project-local .env
    local_env = PROJECT_DIR / ".env"
    if local_env.exists():
        raw_local = _parse_env_file(local_env, "SERPAPI_API_KEYS")
        if raw_local:
            for piece in raw_local.split(","):
                _add(piece.strip())

    # 3. Primary discovered key
    _add(serpapi_api_key())

    return keys


def google_api_key() -> Optional[str]:
    """Discover Google/Gemini API key."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if key and key.startswith("AIza"):
        return key
    for p in [_READ_MEDIA_ENV, _EMBED_SKILL_ENV, PROJECT_DIR / ".env"]:
        candidate = _parse_env_file(p, "GOOGLE_API_KEY") or _parse_env_file(p, "GEMINI_API_KEY")
        if candidate and candidate.startswith("AIza"):
            return candidate
    return None


def vectorengine_api_key() -> Optional[str]:
    """Discover VectorEngine API key for cost-effective reasoning."""
    key = os.getenv("VECTORENGINE_API_KEY")
    if key and key.startswith("sk-"):
        return key
    for p in [_READ_MEDIA_ENV, _EMBED_SKILL_ENV, PROJECT_DIR / ".env"]:
        candidate = _parse_env_file(p, "VECTORENGINE_API_KEY")
        if candidate and candidate.startswith("sk-"):
            return candidate
    return None


def llm_credentials() -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Resolve (api_key, client_options) prioritizing VectorEngine > Google."""
    ve_key = vectorengine_api_key()
    if ve_key:
        return ve_key, {
            "base_url": os.getenv("VECTORENGINE_BASE_URL", "https://api.vectorengine.ai"),
            "api_version": "v1beta",
        }
    g_key = google_api_key()
    if g_key:
        return g_key, None
    return None, None


# Cache settings
CACHE_ENABLED = os.getenv("TRIPADVISOR_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
CACHE_TTL_HOURS = int(os.getenv("TRIPADVISOR_CACHE_TTL_HOURS", "48"))  # 48 hour cache TTL


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def google_search_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Discover Google Custom Search API key and CX engine ID."""
    key = os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")
    if key and cx:
        return key, cx

    local_env = PROJECT_DIR / ".env"
    if local_env.exists():
        k = _parse_env_file(local_env, "GOOGLE_SEARCH_API_KEY")
        c = _parse_env_file(local_env, "GOOGLE_SEARCH_CX")
        if k and c:
            return k, c

    return None, None
