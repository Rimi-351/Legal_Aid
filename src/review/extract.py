"""
src/review/extract.py
---------------------
Document extraction for legal agreements (PDF and DOCX formats).
Preserves page numbers, clause IDs, and character offsets.

Flagging rules:
- Scanned documents or pages with no text layer -> needs_manual_correction=True
- Corrupt, unmapped, or garbled font encoding -> needs_manual_correction=True
- Clauses with needs_manual_correction=True must produce NO downstream findings.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None


@dataclass
class ExtractedClause:
    """Represents a segment/clause extracted from a legal document."""
    doc_id: str
    page: int
    clause_id: str
    char_start: int
    char_end: int
    text: str
    needs_manual_correction: bool = False
    ocr_confidence: Optional[float] = None
    extraction_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "page": self.page,
            "clause_id": self.clause_id,
            "char_span": [self.char_start, self.char_end],
            "text": self.text,
            "needs_manual_correction": self.needs_manual_correction,
            "ocr_confidence": self.ocr_confidence,
            "extraction_note": self.extraction_note,
        }


def is_garbled_text(text: str) -> bool:
    """
    Detects whether extracted text layer is corrupt, unmapped, or garbled.
    Indicators:
    - High ratio of unicode replacement characters (\\ufffd)
    - High frequency of unmapped font markers like (cid:XX)
    - Excessive non-printable control characters
    - High density of random symbols with minimal readable words
    """
    if not text:
        return False

    clean_len = len(text)
    if clean_len == 0:
        return False

    # Check for replacement characters
    replacement_count = text.count("\ufffd")
    if replacement_count / clean_len > 0.05 or replacement_count > 5:
        return True

    # Check for unmapped CID tokens
    cid_matches = re.findall(r"\(cid:\d+\)", text)
    if len(cid_matches) > 3 or (len(cid_matches) * 7) / clean_len > 0.15:
        return True

    # Check for excessive unprintable control characters
    control_chars = sum(1 for c in text if ord(c) < 32 and c not in ("\n", "\r", "\t"))
    if control_chars / clean_len > 0.10:
        return True

    # Check for synthetic garbled / corrupt text markers
    if "[GARBLED_UNREADABLE_SCAN]" in text or "[NO_TEXT_LAYER]" in text:
        return True

    return False


def _split_text_into_clauses(
    text: str, doc_id: str, page_num: int
) -> List[ExtractedClause]:
    """
    Splits continuous page text into distinct clauses by identifying
    clause numbering, headings, or paragraph boundaries.
    Preserves exact character offsets.
    """
    clauses: List[ExtractedClause] = []
    if not text.strip():
        return clauses

    # Pattern identifying numbered clauses or standard legal headers:
    # e.g., '1.', '1.1', 'Clause 1', 'Section 2', 'Article 3', '(a)'
    pattern = re.compile(
        r"(?:^|\n\n+)(?=(?:(?:Clause|Section|Article)\s+\d+[\.:]?|\d+[\.\)]\s+|\[[A-Z0-9_\-]+\]\s*))",
        re.IGNORECASE,
    )

    splits = [m.start() for m in pattern.finditer(text)]
    if not splits or splits[0] != 0:
        splits.insert(0, 0)
    splits.append(len(text))

    clause_counter = 1
    for i in range(len(splits) - 1):
        start = splits[i]
        end = splits[i + 1]
        chunk = text[start:end].strip()
        if not chunk:
            continue

        # Find exact character span in original text
        chunk_start = text.find(chunk, start)
        chunk_end = chunk_start + len(chunk)

        # Detect clause identifier
        id_match = re.match(
            r"^(?:(?:Clause|Section|Article)\s+(\d+)|(\d+)[\.\)])",
            chunk,
            re.IGNORECASE,
        )
        if id_match:
            c_num = id_match.group(1) or id_match.group(2)
            c_id = f"clause_{c_num}"
        else:
            c_id = f"clause_{clause_counter}"

        clauses.append(
            ExtractedClause(
                doc_id=doc_id,
                page=page_num,
                clause_id=c_id,
                char_start=chunk_start,
                char_end=chunk_end,
                text=chunk,
                needs_manual_correction=False,
            )
        )
        clause_counter += 1

    return clauses


def extract_docx(
    file_path: Union[str, Path], doc_id: Optional[str] = None
) -> List[ExtractedClause]:
    """
    Extracts clauses from a DOCX file preserving character offsets.
    """
    if docx is None:
        raise ImportError("python-docx is required for DOCX extraction")

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    doc_id = doc_id or p.stem
    doc = docx.Document(str(p))

    full_text_parts: List[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            full_text_parts.append(t)

    combined_text = "\n\n".join(full_text_parts)

    if not combined_text.strip():
        return [
            ExtractedClause(
                doc_id=doc_id,
                page=1,
                clause_id="clause_empty",
                char_start=0,
                char_end=0,
                text="",
                needs_manual_correction=True,
                extraction_note="Empty DOCX file",
            )
        ]

    if is_garbled_text(combined_text):
        return [
            ExtractedClause(
                doc_id=doc_id,
                page=1,
                clause_id="clause_garbled",
                char_start=0,
                char_end=len(combined_text),
                text=combined_text,
                needs_manual_correction=True,
                extraction_note="Garbled or corrupt text in DOCX",
            )
        ]

    # Split combined document text into clauses
    clauses = _split_text_into_clauses(combined_text, doc_id=doc_id, page_num=1)
    if not clauses:
        # Fallback to single clause
        clauses = [
            ExtractedClause(
                doc_id=doc_id,
                page=1,
                clause_id="clause_1",
                char_start=0,
                char_end=len(combined_text),
                text=combined_text,
                needs_manual_correction=False,
            )
        ]

    return clauses


def extract_pdf(
    file_path: Union[str, Path], doc_id: Optional[str] = None
) -> List[ExtractedClause]:
    """
    Extracts clauses from a PDF file preserving page number and character offsets.
    Detects scanned pages with missing text layer or corrupt encodings.
    """
    if pypdf is None:
        raise ImportError("pypdf is required for PDF extraction")

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    doc_id = doc_id or p.stem
    try:
        reader = pypdf.PdfReader(str(p))
    except Exception as e:
        return [
            ExtractedClause(
                doc_id=doc_id,
                page=1,
                clause_id="page_1_malformed",
                char_start=0,
                char_end=0,
                text="",
                needs_manual_correction=True,
                extraction_note=f"Malformed or unreadable PDF: {e}",
            )
        ]

    all_clauses: List[ExtractedClause] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as e:
            # Corrupt page extraction
            all_clauses.append(
                ExtractedClause(
                    doc_id=doc_id,
                    page=page_idx,
                    clause_id=f"page_{page_idx}_corrupt",
                    char_start=0,
                    char_end=0,
                    text="",
                    needs_manual_correction=True,
                    extraction_note=f"Extraction failure: {e}",
                )
            )
            continue

        stripped = page_text.strip()

        # 1. Scanned / image-only page with no text layer
        if len(stripped) == 0:
            all_clauses.append(
                ExtractedClause(
                    doc_id=doc_id,
                    page=page_idx,
                    clause_id=f"page_{page_idx}_scanned",
                    char_start=0,
                    char_end=0,
                    text="",
                    needs_manual_correction=True,
                    extraction_note="Scanned page / missing text layer",
                )
            )
            continue

        # 2. Corrupt or garbled text layer
        if is_garbled_text(page_text):
            all_clauses.append(
                ExtractedClause(
                    doc_id=doc_id,
                    page=page_idx,
                    clause_id=f"page_{page_idx}_garbled",
                    char_start=0,
                    char_end=len(page_text),
                    text=page_text,
                    needs_manual_correction=True,
                    extraction_note="Garbled or unmapped font encodings",
                )
            )
            continue

        # 3. Valid text layer -> parse into clauses
        page_clauses = _split_text_into_clauses(page_text, doc_id=doc_id, page_num=page_idx)
        if not page_clauses:
            page_clauses = [
                ExtractedClause(
                    doc_id=doc_id,
                    page=page_idx,
                    clause_id=f"page_{page_idx}_clause_1",
                    char_start=0,
                    char_end=len(page_text),
                    text=page_text,
                    needs_manual_correction=False,
                )
            ]
        all_clauses.extend(page_clauses)

    return all_clauses


def extract_document(
    file_path: Union[str, Path], doc_id: Optional[str] = None
) -> List[ExtractedClause]:
    """
    Universal document extractor entry point.
    Dispatches to DOCX or PDF extractor based on file extension.
    """
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".docx":
        return extract_docx(p, doc_id=doc_id)
    elif ext == ".pdf":
        return extract_pdf(p, doc_id=doc_id)
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Supported: .pdf, .docx")

