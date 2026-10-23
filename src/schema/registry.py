"""
src/schema/registry.py
----------------------
Relational in-memory research repository and provenance tracker for Legal Aid BD.

Enforces:
1. Primary key uniqueness for all entities.
2. Foreign key integrity across sources, documents, versions, provisions, chunks,
   amendments, and benchmark cases.
3. Strict end-to-end provenance: No provision can exist without a traceable
   document version and source.
4. Multilingual Unicode preservation during JSON/JSONL serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from .entities import (
    Source,
    Document,
    Version,
    Provision,
    Chunk,
    AmendmentRelation,
    BenchmarkCase,
    DuplicateKeyError,
    ForeignKeyError,
    TraceabilityError,
    SchemaValidationError,
)


@dataclass
class Lineage:
    """Complete provenance chain and relational context for a legal provision."""
    provision: Provision
    version: Version
    document: Document
    source: Source
    chunks: List[Chunk] = field(default_factory=list)
    amendments: List[AmendmentRelation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provision": self.provision.to_dict(),
            "version": self.version.to_dict(),
            "document": self.document.to_dict(),
            "source": self.source.to_dict(),
            "chunks": [c.to_dict() for c in self.chunks],
            "amendments": [a.to_dict() for a in self.amendments],
        }


class LegalDataRegistry:
    """
    In-memory relational registry enforcing structural integrity and provenance.
    Acts as the research database for statutory provisions and evaluation cases.
    """

    def __init__(self):
        self.sources: Dict[str, Source] = {}
        self.documents: Dict[str, Document] = {}
        self.versions: Dict[str, Version] = {}
        self.provisions: Dict[str, Provision] = {}
        self.chunks: Dict[str, Chunk] = {}
        self.amendments: Dict[str, AmendmentRelation] = {}
        self.benchmark_cases: Dict[str, BenchmarkCase] = {}

    # -----------------------------------------------------------------
    # Entity Registration with Foreign Key & Uniqueness Validation
    # -----------------------------------------------------------------

    def add_source(self, source: Source) -> None:
        """Register a Source. Enforces unique source_id."""
        if not isinstance(source, Source):
            raise SchemaValidationError(f"Expected Source instance, got {type(source).__name__}")
        if source.source_id in self.sources:
            raise DuplicateKeyError(f"Source with id '{source.source_id}' already exists.")
        self.sources[source.source_id] = source

    def add_document(self, document: Document) -> None:
        """Register a Document. Enforces unique doc_id and valid source foreign key."""
        if not isinstance(document, Document):
            raise SchemaValidationError(f"Expected Document instance, got {type(document).__name__}")
        if document.doc_id in self.documents:
            raise DuplicateKeyError(f"Document with id '{document.doc_id}' already exists.")
        if document.source_id not in self.sources:
            raise ForeignKeyError(
                f"Document '{document.doc_id}' references non-existent Source '{document.source_id}'."
            )
        self.documents[document.doc_id] = document

    def add_version(self, version: Version) -> None:
        """Register a Document Version. Enforces unique version_id and valid document foreign key."""
        if not isinstance(version, Version):
            raise SchemaValidationError(f"Expected Version instance, got {type(version).__name__}")
        if version.version_id in self.versions:
            raise DuplicateKeyError(f"Version with id '{version.version_id}' already exists.")
        if version.doc_id not in self.documents:
            raise ForeignKeyError(
                f"Version '{version.version_id}' references non-existent Document '{version.doc_id}'."
            )
        self.versions[version.version_id] = version

    def add_provision(self, provision: Provision) -> None:
        """
        Register a Provision.
        
        Strict Acceptance Criterion:
        No provision can exist without a traceable document version AND source.
        Enforces:
        - unique provision_id
        - version_id exists in self.versions
        - act_id matches the Document referenced by Version
        - document has an existing valid Source
        """
        if not isinstance(provision, Provision):
            raise SchemaValidationError(f"Expected Provision instance, got {type(provision).__name__}")
        if provision.provision_id in self.provisions:
            raise DuplicateKeyError(f"Provision with id '{provision.provision_id}' already exists.")
        
        # 1. Foreign key: Version must exist
        if provision.version_id not in self.versions:
            raise ForeignKeyError(
                f"Provision '{provision.provision_id}' references non-existent Version '{provision.version_id}'."
            )
        version = self.versions[provision.version_id]

        # 2. Foreign key: Document must match
        if version.doc_id not in self.documents:
            raise TraceabilityError(
                f"Version '{provision.version_id}' points to non-existent Document '{version.doc_id}'."
            )
        if provision.act_id != version.doc_id:
            raise ForeignKeyError(
                f"Provision act_id '{provision.act_id}' does not match Version doc_id '{version.doc_id}'."
            )
        document = self.documents[version.doc_id]

        # 3. Provenance check: Document must point to a valid Source
        if document.source_id not in self.sources:
            raise TraceabilityError(
                f"Document '{document.doc_id}' points to non-existent Source '{document.source_id}'."
            )

        self.provisions[provision.provision_id] = provision

    def add_chunk(self, chunk: Chunk) -> None:
        """Register a Chunk. Enforces unique chunk_id and valid provision foreign key."""
        if not isinstance(chunk, Chunk):
            raise SchemaValidationError(f"Expected Chunk instance, got {type(chunk).__name__}")
        if chunk.chunk_id in self.chunks:
            raise DuplicateKeyError(f"Chunk with id '{chunk.chunk_id}' already exists.")
        if chunk.provision_id not in self.provisions:
            raise ForeignKeyError(
                f"Chunk '{chunk.chunk_id}' references non-existent Provision '{chunk.provision_id}'."
            )
        self.chunks[chunk.chunk_id] = chunk

    def add_amendment(self, amendment: AmendmentRelation) -> None:
        """
        Register an AmendmentRelation.
        
        Enforces:
        - unique relation_id
        - amending_instrument_id exists as a Document
        - affected_provision_id exists as a Provision
        - supporting_evidence is non-empty
        """
        if not isinstance(amendment, AmendmentRelation):
            raise SchemaValidationError(f"Expected AmendmentRelation instance, got {type(amendment).__name__}")
        if amendment.relation_id in self.amendments:
            raise DuplicateKeyError(f"AmendmentRelation with id '{amendment.relation_id}' already exists.")
        if amendment.amending_instrument_id not in self.documents:
            raise ForeignKeyError(
                f"AmendmentRelation '{amendment.relation_id}' references non-existent "
                f"amending instrument Document '{amendment.amending_instrument_id}'."
            )
        if amendment.affected_provision_id not in self.provisions:
            raise ForeignKeyError(
                f"AmendmentRelation '{amendment.relation_id}' references non-existent "
                f"affected Provision '{amendment.affected_provision_id}'."
            )
        self.amendments[amendment.relation_id] = amendment

    def add_benchmark_case(self, case: BenchmarkCase) -> None:
        """
        Register a BenchmarkCase.
        
        Enforces:
        - unique case_id
        - all expected_provision_ids exist in provisions
        - explicit review_status
        """
        if not isinstance(case, BenchmarkCase):
            raise SchemaValidationError(f"Expected BenchmarkCase instance, got {type(case).__name__}")
        if case.case_id in self.benchmark_cases:
            raise DuplicateKeyError(f"BenchmarkCase with id '{case.case_id}' already exists.")
        for pid in case.expected_provision_ids:
            if pid not in self.provisions:
                raise ForeignKeyError(
                    f"BenchmarkCase '{case.case_id}' references non-existent expected Provision '{pid}'."
                )
        self.benchmark_cases[case.case_id] = case

    # -----------------------------------------------------------------
    # Traceability & Lineage Inspection
    # -----------------------------------------------------------------

    def get_provision_lineage(self, provision_id: str) -> Lineage:
        """
        Retrieve complete provenance lineage for a statutory provision.
        Raises KeyError if provision_id is not found.
        Raises TraceabilityError if the chain of custody to Document or Source is broken.
        """
        if provision_id not in self.provisions:
            raise KeyError(f"Provision '{provision_id}' not found in registry.")

        provision = self.provisions[provision_id]
        if provision.version_id not in self.versions:
            raise TraceabilityError(
                f"Traceability broken: Version '{provision.version_id}' missing for Provision '{provision_id}'."
            )
        version = self.versions[provision.version_id]

        if version.doc_id not in self.documents:
            raise TraceabilityError(
                f"Traceability broken: Document '{version.doc_id}' missing for Version '{version.version_id}'."
            )
        document = self.documents[version.doc_id]

        if document.source_id not in self.sources:
            raise TraceabilityError(
                f"Traceability broken: Source '{document.source_id}' missing for Document '{document.doc_id}'."
            )
        source = self.sources[document.source_id]

        # Gather related chunks and amendments
        related_chunks = [c for c in self.chunks.values() if c.provision_id == provision_id]
        related_amendments = [a for a in self.amendments.values() if a.affected_provision_id == provision_id]

        return Lineage(
            provision=provision,
            version=version,
            document=document,
            source=source,
            chunks=related_chunks,
            amendments=related_amendments,
        )

    def verify_all_provisions_traceable(self) -> Tuple[bool, List[str]]:
        """
        Audit all registered provisions for complete provenance.
        Returns (is_valid, list_of_error_messages).
        """
        errors = []
        for pid in self.provisions:
            try:
                self.get_provision_lineage(pid)
            except (KeyError, TraceabilityError) as e:
                errors.append(f"Provision '{pid}': {str(e)}")
        return (len(errors) == 0, errors)

    # -----------------------------------------------------------------
    # Serialization and Deserialization (UTF-8 Unicode Safe)
    # -----------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Export all registry contents into a structured Python dictionary."""
        return {
            "sources": [s.to_dict() for s in self.sources.values()],
            "documents": [d.to_dict() for d in self.documents.values()],
            "versions": [v.to_dict() for v in self.versions.values()],
            "provisions": [p.to_dict() for p in self.provisions.values()],
            "chunks": [c.to_dict() for c in self.chunks.values()],
            "amendments": [a.to_dict() for a in self.amendments.values()],
            "benchmark_cases": [b.to_dict() for b in self.benchmark_cases.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LegalDataRegistry:
        """Construct and validate a registry from a dictionary."""
        registry = cls()
        for s in data.get("sources", []):
            registry.add_source(Source.from_dict(s))
        for d in data.get("documents", []):
            registry.add_document(Document.from_dict(d))
        for v in data.get("versions", []):
            registry.add_version(Version.from_dict(v))
        for p in data.get("provisions", []):
            registry.add_provision(Provision.from_dict(p))
        for c in data.get("chunks", []):
            registry.add_chunk(Chunk.from_dict(c))
        for a in data.get("amendments", []):
            registry.add_amendment(AmendmentRelation.from_dict(a))
        for b in data.get("benchmark_cases", []):
            registry.add_benchmark_case(BenchmarkCase.from_dict(b))
        return registry

    def export_jsonl(self, directory: Path) -> None:
        """
        Export entities into individual JSONL files with strict UTF-8 encoding.
        Preserves Bangla and Banglish characters cleanly without ASCII escape sequences.
        """
        directory.mkdir(parents=True, exist_ok=True)
        entities_map = {
            "sources.jsonl": self.sources.values(),
            "documents.jsonl": self.documents.values(),
            "versions.jsonl": self.versions.values(),
            "provisions.jsonl": self.provisions.values(),
            "chunks.jsonl": self.chunks.values(),
            "amendments.jsonl": self.amendments.values(),
            "benchmark_cases.jsonl": self.benchmark_cases.values(),
        }
        for filename, items in entities_map.items():
            filepath = directory / filename
            with open(filepath, "w", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def import_jsonl(cls, directory: Path) -> LegalDataRegistry:
        """Load and reconstruct a validated registry from a JSONL directory."""
        registry = cls()
        
        # Load in strict topological order to satisfy foreign keys
        def _read(filename: str) -> List[Dict[str, Any]]:
            filepath = directory / filename
            if not filepath.exists():
                return []
            records = []
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            return records

        for s in _read("sources.jsonl"):
            registry.add_source(Source.from_dict(s))
        for d in _read("documents.jsonl"):
            registry.add_document(Document.from_dict(d))
        for v in _read("versions.jsonl"):
            registry.add_version(Version.from_dict(v))
        for p in _read("provisions.jsonl"):
            registry.add_provision(Provision.from_dict(p))
        for c in _read("chunks.jsonl"):
            registry.add_chunk(Chunk.from_dict(c))
        for a in _read("amendments.jsonl"):
            registry.add_amendment(AmendmentRelation.from_dict(a))
        for b in _read("benchmark_cases.jsonl"):
            registry.add_benchmark_case(BenchmarkCase.from_dict(b))

        return registry
