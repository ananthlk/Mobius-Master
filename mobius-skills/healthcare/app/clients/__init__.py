"""Healthcare API clients: CMS Coverage, NPI Registry, ICD-10."""

from app.clients.icd10 import lookup_icd10_code, search_icd10
from app.clients.npi import lookup_npi, search_npi
from app.clients.cms import get_coverage_document, search_coverage

__all__ = [
    "search_icd10",
    "lookup_icd10_code",
    "lookup_npi",
    "search_npi",
    "search_coverage",
    "get_coverage_document",
]
