"""
src/ingestion/parser.py
-----------------------
Section-aware legal document parser for Bangladesh legislative sources.
Extracts Acts, Sections, Headings, Subsections, and provenance metadata.
"""

import os
import re
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional, Tuple

from .normalizer import (
    normalize_bengali_english_text,
    detect_suspect_bijoy,
    detect_language
)

# Optional BeautifulSoup for rich HTML parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


class FixtureIngestionError(ValueError):
    """Raised when fixture data is detected when building a production corpus or benchmark."""
    pass


def is_fixture_source(filepath_or_record: Any) -> bool:
    """Returns True if the file path or manifest/provision record indicates a test fixture."""
    if isinstance(filepath_or_record, dict):
        if filepath_or_record.get("provenance") == "fixture":
            return True
        path_str = str(filepath_or_record.get("filepath", "") or filepath_or_record.get("source_file", ""))
    else:
        path_str = str(filepath_or_record)
    normalized = path_str.replace("\\", "/").lower()
    return "tests/fixtures" in normalized or "fixtures/" in normalized or "sample_audit_files" in normalized


@dataclass
class Provision:
    """Represents a discrete statutory legal provision (Section/Dhara)."""
    provision_id: str
    doc_id: str
    act_title: str
    act_no: Optional[str]
    section_number: str
    section_heading: str
    subsections: List[str]
    text: str
    language: str
    source_file: str
    source_sha256: str
    publication_date: Optional[str] = None
    commencement_date: Optional[str] = None
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    provenance: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def derive_act_code(act_title: str, filepath: Path) -> str:
    """Derives a short, stable mnemonic code for the Act."""
    clean_title = f"{act_title} {filepath.stem}".lower()
    if "contract" in clean_title:
        return "CA1872"
    elif "consumer" in clean_title or "ভোক্তা" in clean_title:
        return "CRPA2009"
    elif "labour" in clean_title or "শ্রম" in clean_title:
        if "amendment" in clean_title or "সংশোধন" in clean_title:
            return "BLAA2013"
        return "BLA2006"
    elif "rent" in clean_title or "ভাড়া" in clean_title:
        return "PRCA1991"
    elif "property" in clean_title or "সম্পত্তি" in clean_title:
        return "TPA1882"
    elif "specific relief" in clean_title:
        return "SRA1877"
    else:
        # Fallback to sanitized filename stem
        stem = re.sub(r"[^A-Za-z0-9]", "", filepath.stem).upper()
        return stem[:8] if stem else "ACTGEN"


class LegalDocumentParser:
    """
    Parses HTML, text, and extractable statutory files into structured,
    section-level Provision records with deterministic IDs.
    """

    def __init__(self):
        # Regex patterns for fallback text parsing
        self.re_act_no_en = re.compile(r"Act\s+No\.?\s*([IVXLCDM\d]+)\s+of\s+(\d{4})", re.IGNORECASE)
        self.re_act_no_bn = re.compile(r"(\d{4}|[০-৯]{4})\s*সনের\s*([০-৯\d]+)\s*নং\s*আইন")
        self.re_date_bracket = re.compile(r"\[\s*([^\]]+)\s*\]")
        self.re_sec_heading_en = re.compile(r"^(?:Section\s+)?(\d+[A-Z]?)\.\s*(.*)$")
        self.re_sec_heading_bn = re.compile(r"^(?:ধারা\s+)?([০-৯\d]+[ক-হ]?)\।\s*(.*)$")
        self.re_subsection = re.compile(r"\(([০-৯\d]+|[a-z]|[ক-হ])\)")

    def guard_fixture_record(self, record_or_path: Any, building_corpus_or_benchmark: bool = True) -> None:
        """Refuses fixture records when building a corpus or benchmark."""
        if building_corpus_or_benchmark and is_fixture_source(record_or_path):
            identifier = getattr(record_or_path, "name", str(record_or_path))
            if isinstance(record_or_path, dict):
                identifier = record_or_path.get("filename") or record_or_path.get("filepath") or identifier
            raise FixtureIngestionError(
                f"Ingestion guard rejected fixture source '{identifier}': "
                "fixture records are strictly prohibited when building a production corpus or benchmark."
            )

    def parse_file(self, filepath: Path, for_corpus_or_benchmark: bool = False) -> List[Provision]:
        """Parses a single legal document file and returns all extracted provisions."""
        if for_corpus_or_benchmark:
            self.guard_fixture_record(filepath, building_corpus_or_benchmark=True)

        if not filepath.exists() or not filepath.is_file():
            return []

        raw_bytes = filepath.read_bytes()
        sha256 = compute_sha256(filepath)
        filename = filepath.name
        ext = filepath.suffix.lower()

        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = raw_bytes.decode("windows-1252", errors="replace")
            except Exception:
                raw_text = raw_bytes.decode("latin-1", errors="replace")

        # Check for Bijoy Encoding Quarantine
        is_bijoy, bijoy_sigs = detect_suspect_bijoy(raw_text)
        if is_bijoy:
            return [Provision(
                provision_id=f"QUARANTINED_BIJOY_{filepath.stem}",
                doc_id=f"DOC_{filepath.stem}",
                act_title=filepath.stem,
                act_no=None,
                section_number="0",
                section_heading="Quarantined Legacy Bijoy Document",
                subsections=[],
                text=normalize_bengali_english_text(raw_text[:500]),
                language="undetermined",
                source_file=str(filepath.as_posix()),
                source_sha256=sha256,
                is_quarantined=True,
                quarantine_reason=f"Suspect legacy ANSI/Bijoy encoding detected (Signatures: {bijoy_sigs})"
            )]

        # Check for Low-Confidence Scanned OCR Notice
        if "OCR QUARANTINE" in raw_text or "UNRELIABLE TEXT EXTRACTION" in raw_text:
            return [Provision(
                provision_id=f"QUARANTINED_OCR_{filepath.stem}",
                doc_id=f"DOC_{filepath.stem}",
                act_title=filepath.stem,
                act_no=None,
                section_number="0",
                section_heading="Quarantined Scanned OCR Output",
                subsections=[],
                text=normalize_bengali_english_text(raw_text[:500]),
                language="undetermined",
                source_file=str(filepath.as_posix()),
                source_sha256=sha256,
                is_quarantined=True,
                quarantine_reason="Low-confidence or uncorrected scanned OCR output requiring manual verification"
            )]

        # If HTML, parse with DOM structure
        if ext in [".html", ".htm"] and BS4_AVAILABLE:
            return self._parse_html(raw_text, filepath, sha256)
        else:
            return self._parse_plain_text(raw_text, filepath, sha256)

    def _parse_html(self, html_content: str, filepath: Path, sha256: str) -> List[Provision]:
        """Parses HTML statutory files with DOM hierarchy."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Document-level title: prioritize <h1> if available, else clean <title>
        h1_tag = soup.find("h1")
        title_tag = soup.find("title")
        if h1_tag and h1_tag.get_text().strip():
            act_title = h1_tag.get_text().strip()
        elif title_tag and title_tag.get_text().strip():
            raw_title = title_tag.get_text().strip()
            # Only strip trailing parenthetical Act No suffix like (২০১৩ সনের ৩০ নং আইন) or (Act No. IX of 1872)
            act_title = re.sub(r"\s*\((?:\d{4}|[০-৯]{4}|Act\s+No).*?\)\s*$", "", raw_title)
        else:
            act_title = filepath.stem

        # Act No
        act_no = None
        h3_tag = soup.find("h3")
        if h3_tag:
            act_no = h3_tag.get_text().strip()

        # Date
        pub_date = None
        date_p = soup.find("p", string=self.re_date_bracket)
        if date_p:
            match = self.re_date_bracket.search(date_p.get_text())
            if match:
                pub_date = match.group(1).strip()

        doc_id = f"DOC_{filepath.stem.upper()}"
        act_code = derive_act_code(act_title, filepath)

        provisions: List[Provision] = []

        # Look for section divs: <div class="section" id="sec-X">
        section_divs = soup.find_all("div", class_="section")

        if section_divs:
            for div in section_divs:
                heading_tag = div.find(["h4", "h5", "h3"])
                heading_text = heading_tag.get_text().strip() if heading_tag else ""
                
                # Extract section number and title
                sec_num, sec_title = self._extract_sec_num_and_title(heading_text)
                if not sec_num:
                    div_id = div.get("id", "")
                    sec_num = div_id.replace("sec-", "") if "sec-" in div_id else "UNKNOWN"
                    sec_title = heading_text

                # Gather paragraph text
                paragraphs = [p.get_text().strip() for p in div.find_all("p")]
                full_body = "\n".join(paragraphs)
                normalized_body = normalize_bengali_english_text(full_body)

                subsections = self.re_subsection.findall(normalized_body)
                lang = detect_language(normalized_body + " " + sec_title)

                prov_id = f"{act_code}_S{sec_num}"

                provisions.append(Provision(
                    provision_id=prov_id,
                    doc_id=doc_id,
                    act_title=act_title,
                    act_no=act_no,
                    section_number=sec_num,
                    section_heading=sec_title,
                    subsections=subsections,
                    text=normalized_body,
                    language=lang,
                    source_file=str(filepath.as_posix()),
                    source_sha256=sha256,
                    publication_date=pub_date,
                    is_quarantined=False,
                    quarantine_reason=None
                ))
        else:
            # Fallback to plain text extraction from HTML
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            return self._parse_plain_text(text, filepath, sha256, act_title=act_title, act_no=act_no, pub_date=pub_date)

        return provisions

    def _parse_plain_text(self, text: str, filepath: Path, sha256: str,
                          act_title: Optional[str] = None, act_no: Optional[str] = None,
                          pub_date: Optional[str] = None) -> List[Provision]:
        """Fallback parser using regex boundaries across lines."""
        normalized_text = normalize_bengali_english_text(text)
        lines = normalized_text.splitlines()

        if not act_title:
            act_title = lines[0].strip() if lines else filepath.stem

        doc_id = f"DOC_{filepath.stem.upper()}"
        act_code = derive_act_code(act_title, filepath)

        provisions: List[Provision] = []
        current_sec_num = None
        current_sec_heading = ""
        current_sec_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            sec_num, sec_heading = self._extract_sec_num_and_title(stripped)
            if sec_num:
                # Flush previous section
                if current_sec_num:
                    body_text = "\n".join(current_sec_lines).strip()
                    lang = detect_language(body_text + " " + current_sec_heading)
                    provisions.append(Provision(
                        provision_id=f"{act_code}_S{current_sec_num}",
                        doc_id=doc_id,
                        act_title=act_title,
                        act_no=act_no,
                        section_number=current_sec_num,
                        section_heading=current_sec_heading,
                        subsections=self.re_subsection.findall(body_text),
                        text=body_text,
                        language=lang,
                        source_file=str(filepath.as_posix()),
                        source_sha256=sha256,
                        publication_date=pub_date,
                        is_quarantined=False,
                        quarantine_reason=None
                    ))
                current_sec_num = sec_num
                current_sec_heading = sec_heading
                current_sec_lines = []
            else:
                if current_sec_num:
                    current_sec_lines.append(stripped)

        # Flush last section
        if current_sec_num:
            body_text = "\n".join(current_sec_lines).strip()
            lang = detect_language(body_text + " " + current_sec_heading)
            provisions.append(Provision(
                provision_id=f"{act_code}_S{current_sec_num}",
                doc_id=doc_id,
                act_title=act_title,
                act_no=act_no,
                section_number=current_sec_num,
                section_heading=current_sec_heading,
                subsections=self.re_subsection.findall(body_text),
                text=body_text,
                language=lang,
                source_file=str(filepath.as_posix()),
                source_sha256=sha256,
                publication_date=pub_date,
                is_quarantined=False,
                quarantine_reason=None
            ))

        return provisions

    def _extract_sec_num_and_title(self, heading: str) -> Tuple[Optional[str], str]:
        """Extracts section number and title from English or Bangla heading strings."""
        # Try English: 1. Short title, extent, commencement
        m_en = self.re_sec_heading_en.match(heading)
        if m_en:
            return m_en.group(1), m_en.group(2).strip()

        # Try Bangla: ১। সংক্ষিপ্ত শিরোনাম ও প্রবর্তন
        m_bn = self.re_sec_heading_bn.match(heading)
        if m_bn:
            return m_bn.group(1), m_bn.group(2).strip()

        return None, heading

    def parse_directory(
        self,
        dir_path: Path,
        output_file: Path,
        manifest_file: Path,
        for_corpus_or_benchmark: bool = False
    ) -> Dict[str, Any]:
        """Parses all documents in a directory and writes processed JSONL output."""
        if for_corpus_or_benchmark:
            self.guard_fixture_record(dir_path, building_corpus_or_benchmark=True)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.parent.mkdir(parents=True, exist_ok=True)

        files = sorted([f for f in dir_path.iterdir() if f.is_file() and not f.name.startswith(".")])
        all_provisions: List[Provision] = []
        manifest_entries = []

        total_files = len(files)
        quarantined_count = 0
        valid_provisions_count = 0

        for f in files:
            if for_corpus_or_benchmark:
                self.guard_fixture_record(f, building_corpus_or_benchmark=True)

            provisions = self.parse_file(f, for_corpus_or_benchmark=for_corpus_or_benchmark)
            file_quarantined = any(p.is_quarantined for p in provisions)
            if file_quarantined:
                quarantined_count += 1
            else:
                valid_provisions_count += len(provisions)

            all_provisions.extend(provisions)

            is_fixture = is_fixture_source(f)
            manifest_entries.append({
                "filename": f.name,
                "filepath": str(f.as_posix()),
                "source_url": None,
                "acquired_at": None,
                "sha256": compute_sha256(f),
                "license_note": None,
                "provenance": "fixture" if is_fixture else "official_source",
                "provisions_extracted": len([p for p in provisions if not p.is_quarantined]),
                "is_quarantined": file_quarantined,
                "quarantine_reason": provisions[0].quarantine_reason if provisions and provisions[0].is_quarantined else None
            })

        # Write provisions.jsonl
        with open(output_file, "w", encoding="utf-8") as out_f:
            for p in all_provisions:
                out_f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")

        # Write processed_manifest.jsonl
        with open(manifest_file, "w", encoding="utf-8") as man_f:
            for entry in manifest_entries:
                man_f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        stats = {
            "total_source_files": total_files,
            "quarantined_files": quarantined_count,
            "valid_files": total_files - quarantined_count,
            "total_extracted_provisions": len(all_provisions),
            "valid_provisions_count": valid_provisions_count,
            "output_provisions_file": str(output_file.as_posix()),
            "manifest_file": str(manifest_file.as_posix())
        }

        # Write corpus_stats.json alongside provisions.jsonl
        stats_file = output_file.parent / "corpus_stats.json"
        with open(stats_file, "w", encoding="utf-8") as st_f:
            json.dump(stats, st_f, indent=2, ensure_ascii=False)

        return stats
