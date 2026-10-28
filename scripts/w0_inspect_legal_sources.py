#!/usr/bin/env python3
"""
scripts/w0_inspect_legal_sources.py
-----------------------------------
Task 0.2: Automated file, encoding, and metadata inspector for Bangladesh
legal sources.

Scans local legal files (HTML, PDF, TXT) downloaded from official portals:
  - bdlaws.minlaw.gov.bd
  - legislativediv.gov.bd

Detects:
  1. Format: HTML, Unicode PDF, Scanned PDF, or Plain Text.
  2. Suspect legacy non-Unicode encodings (e.g., ANSI/ASCII Bijoy glyphs).
  3. Structural extractability: Act numbers, Sections/Dharas, Subsections.
  4. Language breakdown: Bangla Unicode, Latin ASCII, or Mixed.
  5. Publication dates, effective dates, and amendment notices.
  6. Computes SHA-256 checksums and emits structured JSONL audit logs.

Usage:
    python scripts/w0_inspect_legal_sources.py [--input-dir data/raw/sample_audit_files]
                                               [--output data/manifests/week0_source_audit_log.jsonl]
                                               [--summary-json data/manifests/week0_source_summary.json]
                                               [--verbose]
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import json
import hashlib
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Optional PDF libraries with graceful fallback
PDF_EXTRACTOR = None
try:
    import pypdf
    PDF_EXTRACTOR = "pypdf"
except ImportError:
    try:
        import pdfplumber
        PDF_EXTRACTOR = "pdfplumber"
    except ImportError:
        pass

# Optional BeautifulSoup for HTML parsing
BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    pass

# Regular expressions for Bangladesh legal structure
RE_ACT_NO_EN = re.compile(r"(?:Act\s+No\.?\s*([IVXLCDM\d]+)\s+of\s+(\d{4})|(\d{4})\s*:\s*Act\s+([IVXLCDM\d]+))", re.IGNORECASE)
RE_ACT_NO_BN = re.compile(r"(\d{4}|[০-৯]{4})\s*সনের\s*([০-৯\d]+)\s*নং\s*আইন")
RE_SECTION_EN = re.compile(r"(?:^|\n)\s*(?:Section\s+)?(\d+[A-Z]?)\.\s+([A-Z][^\n]+)", re.MULTILINE)
RE_SECTION_BN = re.compile(r"(?:^|\n)\s*(?:ধারা\s+)?([০-৯\d]+[ক-হ]?)\।\s+([^\n]+)", re.MULTILINE)
RE_SUBSECTION = re.compile(r"\(([০-৯\d]+|[a-z]|[ক-হ])\)")

# Date patterns (publication, effective dates, gazette notices)
RE_DATE_EN = re.compile(r"(?:\[\s*(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})\s*\]|dated\s+the\s+(\d{1,2}\w*\s+\w+,\s+\d{4}))", re.IGNORECASE)
RE_DATE_BN = re.compile(r"(\d{1,2}|[০-৯]{1,2})\s*(?:ই|শে)?\s*(জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|বৈশাখ|জ্যৈষ্ঠ|আষাঢ়|শ্রাবণ|ভাদ্র|আশ্বিন|কার্তিক|অগ্রহায়ণ|পৌষ|মাঘ|ফাল্গুন|চৈত্র),?\s*(\d{4}|[০-৯]{4})")
RE_AMENDMENT_KEYWORDS = re.compile(r"(?:Substituted by|Inserted by|Omitted by|Amended by|প্রতিস্থাপিত|সংযোজিত|বিলুপ্ত|সংশোধিত)", re.IGNORECASE)

# Known Bijoy ASCII/ANSI signature substrings (common Bengali words rendered in SutonnyMJ/Bijoy layout)
BIJOY_SIGNATURES = [
    "AvBb",      # আইন
    "m¤úwË",     # সম্পত্তি
    "evsjv‡`k",  # বাংলাদেশ
    "ধারা",       # (if mixed)
    "AvBbvbyhvqx", # আইনানুযায়ী
    "wba©vwiZ",  # নির্ধারিত
    "weavb",     # বিধান
    "cÖavb",     # প্রধান
    "RvZxq",     # জাতীয়
    "ms‡kvab",   # সংশোধন
]


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def detect_bijoy_encoding_markers(raw_bytes: bytes, text: str) -> Tuple[bool, int, List[str]]:
    """
    Detects whether a file appears to contain legacy non-Unicode (Bijoy/SutonnyMJ)
    encoded Bengali text disguised as Latin-1/ASCII.
    """
    found_signatures = []
    for sig in BIJOY_SIGNATURES:
        if sig in text:
            found_signatures.append(sig)

    # Heuristic: High frequency of special characters combined with Latin letters
    # where Bengali Unicode character count is 0, but common English stopwords are absent.
    has_bijoy = len(found_signatures) >= 2
    return has_bijoy, len(found_signatures), found_signatures


def analyze_character_distribution(text: str) -> Dict[str, Any]:
    """Analyzes character breakdown between Bangla Unicode, Latin ASCII, and symbols."""
    total_chars = len(text)
    if total_chars == 0:
        return {"total_chars": 0, "bangla_ratio": 0.0, "latin_ratio": 0.0, "primary_language": "empty"}

    bangla_count = 0
    latin_count = 0
    digit_count = 0
    whitespace_count = 0

    for ch in text:
        cp = ord(ch)
        if 0x0980 <= cp <= 0x09FF:
            bangla_count += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            latin_count += 1
        elif ch.isdigit() or (0x09E6 <= cp <= 0x09EF):
            digit_count += 1
        elif ch.isspace():
            whitespace_count += 1

    bangla_ratio = round(bangla_count / total_chars, 4)
    latin_ratio = round(latin_count / total_chars, 4)

    if bangla_ratio > 0.40:
        primary_lang = "bn"
    elif latin_ratio > 0.40:
        primary_lang = "en"
    elif bangla_ratio > 0.05 and latin_ratio > 0.05:
        primary_lang = "bilingual_mixed"
    else:
        primary_lang = "undetermined"

    return {
        "total_chars": total_chars,
        "bangla_chars": bangla_count,
        "latin_chars": latin_count,
        "bangla_ratio": bangla_ratio,
        "latin_ratio": latin_ratio,
        "primary_language": primary_lang
    }


def extract_text_from_html(raw_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """Extracts text and structured metadata from HTML legal sources."""
    meta = {"parser": "regex_fallback"}
    try:
        decoded = raw_bytes.decode("utf-8")
        encoding_used = "utf-8"
    except UnicodeDecodeError:
        try:
            decoded = raw_bytes.decode("windows-1252", errors="replace")
            encoding_used = "windows-1252"
        except Exception:
            decoded = raw_bytes.decode("latin-1", errors="replace")
            encoding_used = "latin-1"

    meta["detected_encoding"] = encoding_used

    if BS4_AVAILABLE:
        meta["parser"] = "beautifulsoup4"
        soup = BeautifulSoup(decoded, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        meta["html_title"] = title
    else:
        # Fallback regex tag stripper
        text = re.sub(r"<style.*?</style>", "", decoded, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "\n", text)
        meta["html_title"] = None

    return text, meta


def extract_text_from_pdf(filepath: Path) -> Tuple[str, Dict[str, Any]]:
    """Extracts text from PDF and evaluates whether it is Unicode-searchable or Scanned (image-only)."""
    meta = {
        "extractor": PDF_EXTRACTOR or "none",
        "num_pages": 0,
        "is_scanned_pdf": False,
        "page_char_counts": []
    }
    extracted_text = []

    if PDF_EXTRACTOR == "pypdf":
        try:
            reader = pypdf.PdfReader(str(filepath))
            meta["num_pages"] = len(reader.pages)
            for p_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                meta["page_char_counts"].append(len(page_text.strip()))
                extracted_text.append(page_text)
        except Exception as e:
            meta["extraction_error"] = str(e)

    elif PDF_EXTRACTOR == "pdfplumber":
        try:
            import pdfplumber
            with pdfplumber.open(str(filepath)) as pdf:
                meta["num_pages"] = len(pdf.pages)
                for p_idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    meta["page_char_counts"].append(len(page_text.strip()))
                    extracted_text.append(page_text)
        except Exception as e:
            meta["extraction_error"] = str(e)
    else:
        # No PDF extractor available: perform byte-level scan for Font descriptors and /Text
        raw = filepath.read_bytes()
        meta["extractor"] = "byte_heuristic"
        # Estimate page count via /Type /Page
        page_matches = len(re.findall(rb"/Type\s*/Page\b", raw))
        meta["num_pages"] = max(1, page_matches)
        meta["extraction_error"] = "Neither pypdf nor pdfplumber is installed. Install via: pip install pypdf"

    full_text = "\n\n".join(extracted_text)
    total_chars = len(full_text.strip())

    # If average characters per page is below 60, it's overwhelmingly likely an image-only / scanned PDF
    avg_chars_per_page = (total_chars / meta["num_pages"]) if meta["num_pages"] > 0 else 0
    if meta["num_pages"] > 0 and avg_chars_per_page < 60:
        meta["is_scanned_pdf"] = True

    return full_text, meta


def inspect_single_document(filepath: Path) -> Dict[str, Any]:
    """Runs end-to-end structural, linguistic, and metadata extraction audit on one legal document."""
    ext = filepath.suffix.lower()
    raw_bytes = filepath.read_bytes()
    sha256 = compute_sha256(filepath)
    file_size_bytes = len(raw_bytes)

    doc_format = "unknown"
    doc_text = ""
    extra_meta: Dict[str, Any] = {}

    if ext in [".html", ".htm"]:
        doc_format = "HTML"
        doc_text, extra_meta = extract_text_from_html(raw_bytes)
    elif ext == ".pdf":
        doc_text, extra_meta = extract_text_from_pdf(filepath)
        if extra_meta.get("is_scanned_pdf", False):
            doc_format = "Scanned PDF"
        else:
            doc_format = "Unicode PDF"
    elif ext in [".txt", ".text"]:
        doc_format = "Plain Text"
        try:
            doc_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            doc_text = raw_bytes.decode("latin-1", errors="replace")
    else:
        doc_format = f"Other ({ext})"
        doc_text = raw_bytes.decode("utf-8", errors="ignore")

    # Character Distribution & Language
    char_dist = analyze_character_distribution(doc_text)

    # Bijoy Check
    is_bijoy, bijoy_count, bijoy_sigs = detect_bijoy_encoding_markers(raw_bytes, doc_text)

    # Structural Extraction: Act Identifier
    act_no_match_en = RE_ACT_NO_EN.search(doc_text[:3000])
    act_no_match_bn = RE_ACT_NO_BN.search(doc_text[:3000])

    detected_act = None
    if act_no_match_en:
        detected_act = act_no_match_en.group(0).strip()
    elif act_no_match_bn:
        detected_act = act_no_match_bn.group(0).strip()

    # Structural Extraction: Sections / Dharas
    sections_en = RE_SECTION_EN.findall(doc_text)
    sections_bn = RE_SECTION_BN.findall(doc_text)
    total_sections_found = len(sections_en) + len(sections_bn)
    subsections_found = len(RE_SUBSECTION.findall(doc_text))

    # Dates (Publication / Effective Dates)
    dates_en = [m[0] or m[1] for m in RE_DATE_EN.findall(doc_text)]
    dates_bn = [" ".join(m) for m in RE_DATE_BN.findall(doc_text)]
    has_effective_or_pub_date = (len(dates_en) + len(dates_bn)) > 0

    # Amendments
    amendments_found = len(RE_AMENDMENT_KEYWORDS.findall(doc_text))

    # Instrument Type Classification
    if "Ordinance" in doc_text[:1000] or "অধ্যাদেশ" in doc_text[:1000]:
        instrument_type = "Ordinance"
    elif "Rules" in filepath.name or "বিধিমালা" in doc_text[:1000]:
        instrument_type = "Rules"
    elif amendments_found > 5 and ("Act" in doc_text[:1000] or "আইন" in doc_text[:1000]):
        instrument_type = "Consolidated Act"
    elif "Amendment" in doc_text[:1000] or "সংশোধন" in doc_text[:1000]:
        instrument_type = "Amending Act"
    else:
        instrument_type = "Original Act"

    # Verifiability Assessment
    extractability_status = "High" if total_sections_found > 0 and not is_bijoy else "Low"
    if doc_format == "Scanned PDF":
        extractability_status = "Zero (Requires OCR)"

    record = {
        "filename": filepath.name,
        "filepath": str(filepath.as_posix()),
        "file_size_bytes": file_size_bytes,
        "sha256": sha256,
        "format": doc_format,
        "primary_language": char_dist["primary_language"],
        "bangla_ratio": char_dist["bangla_ratio"],
        "latin_ratio": char_dist["latin_ratio"],
        "suspect_bijoy_encoding": is_bijoy,
        "bijoy_markers_count": bijoy_count,
        "detected_act_identifier": detected_act,
        "sections_detected_count": total_sections_found,
        "subsections_detected_count": subsections_found,
        "dates_detected": dates_en[:3] + dates_bn[:3],
        "has_date_metadata": has_effective_or_pub_date,
        "amendment_markers_count": amendments_found,
        "inferred_instrument_type": instrument_type,
        "extractability_rating": extractability_status,
        "extra_metadata": extra_meta
    }

    return record


def main():
    parser = argparse.ArgumentParser(description="Week 0 Task 0.2: Automated Legal Source Inspector for Legal Aid BD")
    parser.add_argument("--input-dir", default="data/raw/sample_audit_files", help="Directory containing sample legal files")
    parser.add_argument("--output", default="data/manifests/week0_source_audit_log.jsonl", help="JSONL output manifest path")
    parser.add_argument("--summary-json", default="data/manifests/week0_source_summary.json", help="Summary JSON output path")
    parser.add_argument("--verbose", action="store_true", help="Print verbose details for every file")

    args = parser.parse_args()

    input_path = Path(args.input_dir)
    output_path = Path(args.output)
    summary_path = Path(args.summary_json)

    # Ensure parent directories exist
    input_path.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("  Legal Aid BD — Week 0: Legal Source Inspection & Encoding Audit")
    print("=" * 75)
    print(f"[*] Scanning Directory: {input_path.resolve()}")

    files = [p for p in input_path.iterdir() if p.is_file() and not p.name.startswith(".")]

    if not files:
        print(f"[!] Notice: No audit files found in `{input_path}`.")
        print("    Please place 10-15 sample legal documents (HTML, PDF) from bdlaws.minlaw.gov.bd in that directory.")
        print("    Writing an empty initialized manifest.")
        with open(output_path, "w", encoding="utf-8") as f:
            pass
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump({"total_files": 0, "status": "awaiting_sample_files"}, f, indent=2)
        sys.exit(0)

    print(f"[*] Found {len(files)} candidate legal documents to audit.\n")

    records = []
    format_counts = {}
    lang_counts = {}
    bijoy_alert_count = 0
    scanned_pdf_count = 0
    with_dates_count = 0
    with_sections_count = 0

    with open(output_path, "w", encoding="utf-8") as out_f:
        for p in sorted(files):
            rec = inspect_single_document(p)
            records.append(rec)
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")

            # Accumulate statistics
            fmt = rec["format"]
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

            lang = rec["primary_language"]
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

            if rec["suspect_bijoy_encoding"]:
                bijoy_alert_count += 1
            if fmt == "Scanned PDF":
                scanned_pdf_count += 1
            if rec["has_date_metadata"]:
                with_dates_count += 1
            if rec["sections_detected_count"] > 0:
                with_sections_count += 1

            # Console output
            status_symbol = "[+]" if rec["extractability_rating"] == "High" else "[!]"
            print(f"{status_symbol} {p.name:<35} | {rec['format']:<12} | Lang: {rec['primary_language']:<5} | Secs: {rec['sections_detected_count']:<3} | Bijoy: {str(rec['suspect_bijoy_encoding']):<5}")
            if args.verbose:
                print(f"    SHA256: {rec['sha256']}")
                print(f"    Act ID: {rec['detected_act_identifier']}")
                print(f"    Dates:  {rec['dates_detected']}")
                print(f"    Type:   {rec['inferred_instrument_type']}")
                print("-" * 75)

    # Compile Summary
    summary = {
        "total_documents_audited": len(files),
        "format_distribution": format_counts,
        "language_distribution": lang_counts,
        "extractable_sections_count": with_sections_count,
        "extractable_sections_percentage": round((with_sections_count / len(files)) * 100, 2),
        "documents_with_date_metadata": with_dates_count,
        "date_metadata_percentage": round((with_dates_count / len(files)) * 100, 2),
        "scanned_pdfs_requiring_ocr": scanned_pdf_count,
        "suspect_bijoy_encodings_detected": bijoy_alert_count,
        "manifest_path": str(output_path.as_posix()),
    }

    with open(summary_path, "w", encoding="utf-8") as sum_f:
        json.dump(summary, sum_f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 75)
    print("  WEEK 0 TASK 0.2: SOURCE AUDIT SUMMARY REPORT")
    print("=" * 75)
    print(f"[*] Total Documents Audited:         {summary['total_documents_audited']}")
    print(f"[*] Format Breakdown:                {format_counts}")
    print(f"[*] Language Breakdown:              {lang_counts}")
    print(f"[*] Section Extractability:          {summary['extractable_sections_count']}/{summary['total_documents_audited']} ({summary['extractable_sections_percentage']}%)")
    print(f"[*] Date Metadata Present:           {summary['documents_with_date_metadata']}/{summary['total_documents_audited']} ({summary['date_metadata_percentage']}%)")
    print(f"[*] Scanned PDFs (OCR Required):     {scanned_pdf_count}")
    print(f"[*] Suspect Legacy Bijoy Encodings:  {bijoy_alert_count}")
    print(f"\n[+] Audit Manifest written to: {output_path}")
    print(f"[+] Summary JSON written to:     {summary_path}")


if __name__ == "__main__":
    main()
