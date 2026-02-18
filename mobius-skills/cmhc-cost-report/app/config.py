"""Config from environment."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
BQ_PROJECT = os.environ.get("BQ_PROJECT", "mobiusos-new")
BQ_LANDING_DATASET = os.environ.get("BQ_LANDING_DATASET", "landing_cmhc_dev")
BQ_MART_DATASET = os.environ.get("BQ_MART_DATASET", "mobius_cmhc_dev")

# CMS HCRIS download URLs (CMHC)
CMS_CMHC17_URL = "https://downloads.cms.gov/Files/hcris/CMHC17-ALL-YEARS.zip"
# Older vintage 2088-92: may be in a different zip; set CMS_CMHC92_URL if needed
CMS_CMHC92_URL = os.environ.get("CMS_CMHC92_URL", "")

GCS_RAW_PREFIX = "cmhc-hcris/raw"
