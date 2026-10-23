"""
src/ingestion - Legal Document Ingestion & Section-Aware Extraction
"""
from .normalizer import normalize_bengali_english_text, detect_suspect_bijoy
from .parser import LegalDocumentParser, Provision

__all__ = [
    "normalize_bengali_english_text",
    "detect_suspect_bijoy",
    "LegalDocumentParser",
    "Provision",
]
