"""Config from environment."""
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent  # healthcare/
_config_dir = Path(_repo_root) / "mobius-config"
if _config_dir.exists() and str(_config_dir) not in sys.path:
    sys.path.insert(0, str(_config_dir))
try:
    from env_helper import load_env
    load_env(_repo_root)
except ImportError:
    try:
        from dotenv import load_dotenv
        load_dotenv(_repo_root / ".env", override=True)
    except Exception:
        pass

# API base URLs (public, no auth for ICD-10 and NPI; CMS may need token for some endpoints)
CMS_COVERAGE_BASE = os.getenv("CMS_COVERAGE_BASE", "https://api.coverage.cms.gov")
NPPES_NPI_BASE = os.getenv("NPPES_NPI_BASE", "https://npiregistry.cms.hhs.gov/api")
ICD10_NLM_BASE = os.getenv("ICD10_NLM_BASE", "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3")

# CMS Coverage API: license agreement token (from /v1/metadata/license-agreement/) - optional for reports
CMS_LICENSE_TOKEN = (os.getenv("CMS_LICENSE_TOKEN") or "").strip()

# LLM for synthesizing answers (anthropic or vertex)
HEALTHCARE_LLM_PROVIDER = (os.getenv("HEALTHCARE_LLM_PROVIDER") or "vertex").strip().lower()
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
VERTEX_PROJECT_ID = (os.getenv("VERTEX_PROJECT_ID") or os.getenv("CHAT_VERTEX_PROJECT_ID") or "").strip()
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
