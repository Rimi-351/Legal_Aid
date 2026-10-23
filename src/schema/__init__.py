"""
src/schema/__init__.py
----------------------
Public interface for the Legal Aid BD research data schema.

Exports:
- Entities: Source, Document, Version, Provision, Chunk, AmendmentRelation, BenchmarkCase
- Enums: DocumentType, LegalDomain, Language, AmendmentType, ReviewStatus
- Exceptions: SchemaValidationError, ForeignKeyError, DuplicateKeyError, TraceabilityError
- Registry: LegalDataRegistry, Lineage
"""

from .entities import (
    DocumentType,
    LegalDomain,
    Language,
    AmendmentType,
    ReviewStatus,
    SchemaValidationError,
    ForeignKeyError,
    DuplicateKeyError,
    TraceabilityError,
    Source,
    Document,
    Version,
    Provision,
    Chunk,
    AmendmentRelation,
    BenchmarkCase,
)
from .registry import (
    LegalDataRegistry,
    Lineage,
)

__all__ = [
    "DocumentType",
    "LegalDomain",
    "Language",
    "AmendmentType",
    "ReviewStatus",
    "SchemaValidationError",
    "ForeignKeyError",
    "DuplicateKeyError",
    "TraceabilityError",
    "Source",
    "Document",
    "Version",
    "Provision",
    "Chunk",
    "AmendmentRelation",
    "BenchmarkCase",
    "LegalDataRegistry",
    "Lineage",
]
