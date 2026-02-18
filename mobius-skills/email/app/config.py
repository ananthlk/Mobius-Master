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
    load_dotenv(_repo_root / ".env", override=True)

# System sender identity (Gmail)
MOBIUS_EMAIL_FROM = os.getenv("MOBIUS_EMAIL_FROM", "mobiushealthai@gmail.com")

# Gmail API: path to OAuth2 token (after first run of desktop OAuth flow)
GMAIL_OAUTH_TOKEN_PATH = os.getenv("GMAIL_OAUTH_TOKEN_PATH", "")
# Or path to credentials.json for OAuth client
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", str(_repo_root / "credentials.json"))

# SMTP fallback (Gmail app password)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
GMAIL_APP_PASSWORD = (os.getenv("GMAIL_APP_PASSWORD") or "").strip()

# LLM for crafting subject/body (OpenAI or Vertex)
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
VERTEX_PROJECT_ID = (os.getenv("VERTEX_PROJECT_ID") or "").strip()
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-1.5-flash")

# Limits
EMAIL_MAX_SUBJECT_LEN = int(os.getenv("EMAIL_MAX_SUBJECT_LEN", "500"))
EMAIL_MAX_BODY_LEN = int(os.getenv("EMAIL_MAX_BODY_LEN", "100000"))
