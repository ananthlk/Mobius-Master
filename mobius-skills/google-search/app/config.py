"""Config from environment."""
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
_config_dir = _repo_root.parent.parent / "mobius-config"
if _config_dir.exists() and str(_config_dir) not in sys.path:
    sys.path.insert(0, str(_config_dir))
try:
    from env_helper import load_env
    load_env(_repo_root)
except ImportError:
    from dotenv import load_dotenv
    env_file = _repo_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)

# Google Custom Search API (enable at https://console.cloud.google.com/apis/library/customsearch.googleapis.com)
GOOGLE_CSE_API_KEY = (os.getenv("GOOGLE_CSE_API_KEY") or "").strip()
GOOGLE_CSE_CX = (os.getenv("GOOGLE_CSE_CX") or "").strip()

# Fallback: DuckDuckGo (no API key; uses duckduckgo-search package)
USE_DUCKDUCKGO_FALLBACK = os.getenv("GOOGLE_SEARCH_USE_DUCKDUCKGO_FALLBACK", "true").lower() in ("true", "1", "yes")
