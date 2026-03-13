"""Config from environment."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

BQ_PROJECT = os.environ.get("BQ_PROJECT", "mobius-os-dev")
BQ_MARTS_MEDICAID_DATASET = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
