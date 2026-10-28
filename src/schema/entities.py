"""
src/schema/entities.py
----------------------
Core data entities, domain enumerations, and validation models for the Legal Aid BD
research data schema.

Implements the 7 core entities:
1. Source (institution, URL, access method, collection date)
2. Document (title, type, legal domain, language)
3. Version (publication date, effective dates, checksum)
4. Provision (act ID, section, subsection, text)
5. Chunk (provision ID, text span, page or paragraph reference)
6. AmendmentRelation (amending instrument, affected provision, supporting evidence)
7. BenchmarkCase (query, language, expected provision IDs, review status)
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Union


# =====================================================================
# Domain Enumerations
# =====================================================================

class DocumentType(str, Enum):
    """Categorization of legislative and statutory instruments."""
    ACT = "Act"
    AMENDING_ACT = "Amending Act"
    ORDINANCE = "Ordinance"
    RULES = "Rules"
    REGULATION = "Regulation"
    SRO = "SRO"  # Statutory Regulatory Order
    CONSTITUTION = "Constitution"
    ORDER = "Order"
    GAZETTE_NOTICE = "Gazette Notice"
    OTHER = "Other"


class LegalDomain(str, Enum):
    """Primary subject matter jurisdiction of Bangladesh law."""
    CONTRACT = "Contractual Obligations"
    LABOUR = "Labour & Employment"
    PROPERTY_LAND = "Land & Tenancy"
    CONSUMER = "Consumer Protection"
    CONSTITUTIONAL = "Constitutional Law"
    COMMERCIAL = "Commercial & Corporate"
    CRIMINAL = "Criminal Law"
    GENERAL = "General Legal"


class Language(str, Enum):
    """Supported linguistic modalities in the legal corpus."""
    BN = "bn"
    EN = "en"
    BANGLISH = "banglish"
    MIXED = "mixed"


class AmendmentType(str, Enum):
    """Legislative modification action types."""
    SUBSTITUTION = "substituted"
    INSERTION = "inserted"
    OMISSION = "omitted"
    AMENDMENT = "amended"
    REPEAL = "repealed"


class ReviewStatus(str, Enum):
    """Explicit review and verification tier for research benchmarks."""
    UNREVIEWED = "unreviewed"
    RESEARCHER_REVIEWED = "researcher_reviewed"
    LAWYER_REVIEWED = "lawyer_reviewed"


# =====================================================================
# Custom Exceptions
# =====================================================================

class SchemaValidationError(ValueError):
    """Raised when an entity fails structural, type, or constraint validation."""
    pass


class ForeignKeyError(KeyError):
    """Raised when a foreign key references a non-existent entity."""
    pass


class DuplicateKeyError(ValueError):
    """Raised when attempting to insert an entity with an existing primary key."""
    pass


class TraceabilityError(ValueError):
    """Raised when a provision cannot be traced back to its document, version, or source."""
    pass


# =====================================================================
# Helper Validators
# =====================================================================

def _normalize_text(text: str) -> str:
    """Consistently normalize text using Unicode NFC, preserving conjuncts."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text.strip())


def _validate_non_empty(value: Any, field_name: str, entity_name: str) -> str:
    """Ensure string field is non-null and not whitespace."""
    if value is None:
        raise SchemaValidationError(f"{entity_name}: '{field_name}' must not be null/empty.")
    val_str = str(value).strip()
    if not val_str:
        raise SchemaValidationError(f"{entity_name}: '{field_name}' must not be empty or whitespace.")
    return val_str


def _validate_checksum(checksum: str, entity_name: str) -> str:
    """Validate 64-character hexadecimal SHA-256 string."""
    cleaned = _validate_non_empty(checksum, "checksum", entity_name).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", cleaned):
        raise SchemaValidationError(
            f"{entity_name}: 'checksum' must be a valid 64-character hexadecimal SHA-256 digest, got '{cleaned}'."
        )
    return cleaned


# =====================================================================
# 1. Source Entity
# =====================================================================

@dataclass
class Source:
    """
    Source institution, portal, or physical archive provenance.

    Requirements:
    - institution: issuing authority or repository name (required).
    - url: original URL if acquired digitally, or None for physical archives.
    - access_method: e.g. 'manual_download', 'gazette_archive', 'direct_inspection'.
    - collection_date: ISO 8601 date string or None if unrecorded.
    """
    source_id: str
    institution: str
    url: Optional[str] = None
    access_method: str = "manual_download"
    collection_date: Optional[str] = None
    terms_of_access: Optional[str] = "Open Public Inspection"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.source_id = _validate_non_empty(self.source_id, "source_id", "Source")
        self.institution = _validate_non_empty(self.institution, "institution", "Source")
        self.access_method = _validate_non_empty(self.access_method, "access_method", "Source")
        if self.collection_date is not None:
            self.collection_date = str(self.collection_date).strip() or None
        if self.url is not None:
            self.url = str(self.url).strip() or None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Source:
        return cls(**data)


# =====================================================================
# 1b. Manifest Record Entity
# =====================================================================

@dataclass
class ManifestRecord:
    """
    Schema for ingested source manifests with full provenance.
    Provenance fields: source_url, acquired_at, sha256, license_note. Unknown = None (null).
    """
    filename: str
    filepath: str
    sha256: str
    source_url: Optional[str] = None
    acquired_at: Optional[str] = None
    license_note: Optional[str] = None
    provenance: Optional[str] = None
    provisions_extracted: int = 0
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.filename = _validate_non_empty(self.filename, "filename", "ManifestRecord")
        self.filepath = _validate_non_empty(self.filepath, "filepath", "ManifestRecord")
        self.sha256 = _validate_checksum(self.sha256, "ManifestRecord")
        if self.source_url is not None:
            self.source_url = str(self.source_url).strip() or None
        if self.acquired_at is not None:
            self.acquired_at = str(self.acquired_at).strip() or None
        if self.license_note is not None:
            self.license_note = _normalize_text(str(self.license_note)) or None
        if self.provenance is not None:
            self.provenance = str(self.provenance).strip() or None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ManifestRecord:
        return cls(**data)


# =====================================================================
# 2. Document Entity
# =====================================================================

@dataclass
class Document:
    """
    Legislative or regulatory work (e.g. an Act, Ordinance, or SRO).

    Requirements:
    - title: title of the legal document (e.g. 'The Contract Act, 1872').
    - type: DocumentType or recognized string category.
    - legal_domain: LegalDomain or recognized domain name.
    - language: Language or recognized ISO code.
    - source_id: foreign key to Source.
    """
    doc_id: str
    source_id: str
    title: str
    document_type: Union[DocumentType, str]
    legal_domain: Union[LegalDomain, str]
    language: Union[Language, str]
    act_no: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.doc_id = _validate_non_empty(self.doc_id, "doc_id", "Document")
        self.source_id = _validate_non_empty(self.source_id, "source_id", "Document")
        self.title = _normalize_text(_validate_non_empty(self.title, "title", "Document"))
        
        # Normalize and validate document_type
        if isinstance(self.document_type, DocumentType):
            self.document_type = self.document_type.value
        else:
            self.document_type = _validate_non_empty(self.document_type, "document_type", "Document")

        # Normalize and validate legal_domain
        if isinstance(self.legal_domain, LegalDomain):
            self.legal_domain = self.legal_domain.value
        else:
            self.legal_domain = _validate_non_empty(self.legal_domain, "legal_domain", "Document")

        # Normalize and validate language
        if isinstance(self.language, Language):
            self.language = self.language.value
        else:
            self.language = _validate_non_empty(self.language, "language", "Document").lower()

        if self.act_no:
            self.act_no = _normalize_text(str(self.act_no))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Document:
        return cls(**data)


# =====================================================================
# 3. Version Entity
# =====================================================================

@dataclass
class Version:
    """
    Specific textual release or edition of a Document at a point in time.

    Requirements:
    - doc_id: foreign key to Document.
    - publication_date: calendar date of publication or None if unknown.
    - effective_dates: start and end effective dates, or None if unknown.
    - checksum: SHA-256 digest of original artifact.
    """
    version_id: str
    doc_id: str
    checksum: str
    publication_date: Optional[str] = None
    effective_start_date: Optional[str] = None
    effective_end_date: Optional[str] = None
    version_label: Optional[str] = None
    is_consolidated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.version_id = _validate_non_empty(self.version_id, "version_id", "Version")
        self.doc_id = _validate_non_empty(self.doc_id, "doc_id", "Version")
        self.checksum = _validate_checksum(self.checksum, "Version")
        
        # Represent unknown dates strictly as None (never fabricate)
        if self.publication_date is not None:
            self.publication_date = str(self.publication_date).strip() or None
        if self.effective_start_date is not None:
            self.effective_start_date = str(self.effective_start_date).strip() or None
        if self.effective_end_date is not None:
            self.effective_end_date = str(self.effective_end_date).strip() or None
        if self.version_label is not None:
            self.version_label = _normalize_text(str(self.version_label))

    @property
    def effective_dates(self) -> Dict[str, Optional[str]]:
        """Dictionary of effective temporal boundaries; None represents unknown."""
        return {
            "start": self.effective_start_date,
            "end": self.effective_end_date,
            "is_known": self.effective_start_date is not None
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Version:
        # Support effective_dates dictionary if passed
        d = dict(data)
        if "effective_dates" in d and isinstance(d["effective_dates"], dict):
            eff = d.pop("effective_dates")
            d.setdefault("effective_start_date", eff.get("start"))
            d.setdefault("effective_end_date", eff.get("end"))
        return cls(**d)


# =====================================================================
# 4. Provision Entity
# =====================================================================

@dataclass
class Provision:
    """
    Discrete statutory unit (Section/Dhara) within a Document Version.

    Requirements:
    - act_id: foreign key to Document (Act).
    - version_id: foreign key to Version.
    - section: section number or identifier (e.g. '10', '২৭', '26A').
    - subsection: subsection identifier if applicable, or None.
    - text: full original text of the provision.
    """
    provision_id: str
    version_id: str
    act_id: str
    section: str
    text: str
    subsection: Optional[str] = None
    heading: Optional[str] = None
    language: Optional[str] = None
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.provision_id = _validate_non_empty(self.provision_id, "provision_id", "Provision")
        self.version_id = _validate_non_empty(self.version_id, "version_id", "Provision")
        self.act_id = _validate_non_empty(self.act_id, "act_id", "Provision")
        self.section = _normalize_text(_validate_non_empty(self.section, "section", "Provision"))
        self.text = _normalize_text(_validate_non_empty(self.text, "text", "Provision"))
        
        if self.subsection is not None:
            self.subsection = _normalize_text(str(self.subsection)) or None
        if self.heading is not None:
            self.heading = _normalize_text(str(self.heading)) or None
        if self.language is not None:
            self.language = str(self.language).strip().lower() or None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Provision:
        return cls(**data)


# =====================================================================
# 5. Chunk Entity
# =====================================================================

@dataclass
class Chunk:
    """
    Passage or sub-segment of a Provision for indexing or vector retrieval.

    Requirements:
    - provision_id: foreign key to Provision.
    - text_span: exact text slice of the chunk.
    - page or paragraph reference: location metadata when available.
    """
    chunk_id: str
    provision_id: str
    text_span: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    page_number: Optional[int] = None
    paragraph_reference: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.chunk_id = _validate_non_empty(self.chunk_id, "chunk_id", "Chunk")
        self.provision_id = _validate_non_empty(self.provision_id, "provision_id", "Chunk")
        self.text_span = _normalize_text(_validate_non_empty(self.text_span, "text_span", "Chunk"))

        if self.char_start is not None and self.char_end is not None:
            if self.char_start < 0:
                raise SchemaValidationError("Chunk: 'char_start' must be non-negative.")
            if self.char_end < self.char_start:
                raise SchemaValidationError(
                    f"Chunk: 'char_end' ({self.char_end}) cannot be less than 'char_start' ({self.char_start})."
                )

        if self.page_number is not None and self.page_number < 1:
            raise SchemaValidationError("Chunk: 'page_number' must be >= 1 if provided.")

        if self.paragraph_reference is not None:
            self.paragraph_reference = _normalize_text(str(self.paragraph_reference)) or None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Chunk:
        return cls(**data)


# =====================================================================
# 6. AmendmentRelation Entity
# =====================================================================

@dataclass
class AmendmentRelation:
    """
    Formal modification link between an amending instrument and an affected provision.

    Requirements:
    - amending_instrument_id: foreign key to Document (Amending Act/Ordinance).
    - affected_provision_id: foreign key to Provision.
    - supporting_evidence: mandatory textual or gazette citation.
      NEVER infer a confirmed relationship without supporting evidence.
    """
    relation_id: str
    amending_instrument_id: str
    affected_provision_id: str
    supporting_evidence: str
    amendment_type: Union[AmendmentType, str] = AmendmentType.AMENDMENT
    effective_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.relation_id = _validate_non_empty(self.relation_id, "relation_id", "AmendmentRelation")
        self.amending_instrument_id = _validate_non_empty(
            self.amending_instrument_id, "amending_instrument_id", "AmendmentRelation"
        )
        self.affected_provision_id = _validate_non_empty(
            self.affected_provision_id, "affected_provision_id", "AmendmentRelation"
        )
        
        # Rule: Record amendment evidence explicitly; do not infer without supporting evidence
        evidence = _normalize_text(self.supporting_evidence)
        if not evidence:
            raise SchemaValidationError(
                "AmendmentRelation: 'supporting_evidence' must be explicitly provided. "
                "Amendment relationships cannot be inferred without verifiable supporting evidence."
            )
        self.supporting_evidence = evidence

        if isinstance(self.amendment_type, AmendmentType):
            self.amendment_type = self.amendment_type.value
        else:
            self.amendment_type = _validate_non_empty(
                self.amendment_type, "amendment_type", "AmendmentRelation"
            )

        if self.effective_date is not None:
            self.effective_date = str(self.effective_date).strip() or None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AmendmentRelation:
        return cls(**data)


# =====================================================================
# 7. BenchmarkCase Entity
# =====================================================================

@dataclass
class BenchmarkCase:
    """
    Factual evaluation scenario query paired with gold target provisions and review status.

    Requirements:
    - query: natural-language legal query text (supports Bangla, English, Banglish).
    - language: query script/language modality.
    - expected_provision_ids: list of foreign keys to Provision.
    - review_status: explicit status in ['unreviewed', 'researcher_reviewed', 'lawyer_reviewed'].
    """
    case_id: str
    query: str
    language: Union[Language, str]
    expected_provision_ids: List[str]
    review_status: Union[ReviewStatus, str]
    scenario_id: Optional[str] = None
    split: str = "dev"
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.case_id = _validate_non_empty(self.case_id, "case_id", "BenchmarkCase")
        self.query = _normalize_text(_validate_non_empty(self.query, "query", "BenchmarkCase"))

        if isinstance(self.language, Language):
            self.language = self.language.value
        else:
            self.language = _validate_non_empty(self.language, "language", "BenchmarkCase").lower()

        # Validate expected_provision_ids
        if not isinstance(self.expected_provision_ids, (list, tuple, set)):
            raise SchemaValidationError(
                "BenchmarkCase: 'expected_provision_ids' must be a list of provision IDs."
            )
        clean_ids = [str(pid).strip() for pid in self.expected_provision_ids if str(pid).strip()]
        if not clean_ids:
            raise SchemaValidationError(
                "BenchmarkCase: 'expected_provision_ids' must contain at least one valid provision ID."
            )
        self.expected_provision_ids = clean_ids

        # Enforce explicit review status
        if isinstance(self.review_status, ReviewStatus):
            self.review_status = self.review_status.value
        else:
            status_val = str(self.review_status).strip().lower()
            allowed = {s.value for s in ReviewStatus}
            if status_val not in allowed:
                raise SchemaValidationError(
                    f"BenchmarkCase: 'review_status' must be one of {sorted(allowed)}, got '{self.review_status}'."
                )
            self.review_status = status_val

        self.split = _validate_non_empty(self.split, "split", "BenchmarkCase").lower()
        if self.scenario_id is not None:
            self.scenario_id = str(self.scenario_id).strip() or None
        if self.reviewer_id is not None:
            self.reviewer_id = str(self.reviewer_id).strip() or None
        if self.reviewer_notes is not None:
            self.reviewer_notes = _normalize_text(str(self.reviewer_notes)) or None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkCase:
        return cls(**data)
