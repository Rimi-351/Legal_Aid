"""
src/retrieval/temporal.py
-------------------------
Temporal reasoning and statutory versioning status for Bangladesh legal provisions.

Computes version_status per provision:
- verified_in_force: Provision verified active and in force as of given date.
- verified_not_in_force: Provision verified not yet enacted/commenced or repealed/replaced as of given date.
- uncertain: Metadata unverified, dates unknown, or conflicting records.

Hard Rule:
verified_* status is granted ONLY when effective_date and repeal/replace info
come from an official, review_status=verified record. Everything else is 'uncertain'.
"""
import re
import json
import datetime
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Union, List

logger = logging.getLogger(__name__)

BENGALI_DIGITS_TRANS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

BENGALI_MONTHS = {
    "জানুয়ারি": 1,
    "ফেব্রুয়ারি": 2,
    "মার্চ": 3,
    "এপ্রিল": 4,
    "মে": 5,
    "জুন": 6,
    "জুলাই": 7,
    "আগস্ট": 8,
    "সেপ্টেম্বর": 9,
    "অক্টোবর": 10,
    "নভেম্বর": 11,
    "ডিসেম্বর": 12,
}

ENGLISH_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def parse_date_string(date_input: Optional[Union[str, datetime.date, datetime.datetime]]) -> Optional[datetime.date]:
    """
    Parses date from ISO string (YYYY-MM-DD), English textual date,
    or Bengali calendar date string. Returns datetime.date or None.
    """
    if date_input is None:
        return None
    if isinstance(date_input, datetime.datetime):
        return date_input.date()
    if isinstance(date_input, datetime.date):
        return date_input

    raw = str(date_input).strip()
    if not raw:
        return None

    # Normalize Bengali numerals to ASCII digits
    normalized = raw.translate(BENGALI_DIGITS_TRANS)

    # 1. ISO format: YYYY-MM-DD or YYYY/MM/DD
    iso_match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", normalized)
    if iso_match:
        try:
            return datetime.date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # 2. Year only: YYYY
    year_only_match = re.fullmatch(r"(\d{4})", normalized)
    if year_only_match:
        try:
            return datetime.date(int(year_only_match.group(1)), 1, 1)
        except ValueError:
            pass

    # 3. Bengali text date, e.g., '৬ এপ্রিল, ২০০৯' or '২২ জুলাই ২০১৩'
    for bn_name, m_num in BENGALI_MONTHS.items():
        if bn_name in raw:
            # Extract day and year from normalized text
            nums = re.findall(r"\d+", normalized)
            if len(nums) >= 2:
                day = int(nums[0])
                year = int(nums[-1])
                try:
                    return datetime.date(year, m_num, day)
                except ValueError:
                    pass

    # 4. English textual date, e.g., '25th April, 1872' or '17 February 1882'
    clean_en = re.sub(r"(st|nd|rd|th),?", "", normalized, flags=re.IGNORECASE)
    for en_name, m_num in ENGLISH_MONTHS.items():
        pattern = rf"\b{en_name}\b"
        if re.search(pattern, clean_en, re.IGNORECASE):
            nums = re.findall(r"\d+", clean_en)
            if len(nums) >= 2:
                day = int(nums[0])
                year = int(nums[-1])
                try:
                    return datetime.date(year, m_num, day)
                except ValueError:
                    pass

    return None


def resolve_provision_version_status(
    provision_meta: Dict[str, Any],
    as_of_date: Optional[Union[str, datetime.date]] = None,
) -> str:
    """
    Computes statutory version_status given as_of_date:
    Returns one of: 'verified_in_force' | 'verified_not_in_force' | 'uncertain'.

    Enforces strict rules:
    - If as_of_date is not given: 'uncertain'.
    - verified_* ONLY when evidence_type='official' AND review_status='verified'.
    - If effective_date is unknown: 'uncertain'.
    - If conflicting metadata exists: 'uncertain'.
    """
    if as_of_date is None:
        return "uncertain"

    parsed_as_of = parse_date_string(as_of_date)
    if parsed_as_of is None:
        return "uncertain"

    # Conflicting metadata or quarantine -> immediately uncertain
    if provision_meta.get("conflict_note") or provision_meta.get("is_quarantined"):
        return "uncertain"

    # Rule: verified_* only when official and verified
    evidence_type = (provision_meta.get("evidence_type") or "unknown").lower()
    review_status = (provision_meta.get("review_status") or "pending").lower()

    if evidence_type != "official" or review_status != "verified":
        return "uncertain"

    # Effective date must be explicitly present and parseable
    effective_raw = provision_meta.get("effective_date") or provision_meta.get("commencement_date")
    parsed_effective = parse_date_string(effective_raw)

    enactment_raw = provision_meta.get("enactment_date") or provision_meta.get("publication_date")
    parsed_enactment = parse_date_string(enactment_raw)

    if parsed_effective is None and parsed_enactment is None:
        return "uncertain"

    # Use effective date if available, otherwise enactment date
    in_force_start = parsed_effective or parsed_enactment

    # Check 1: as_of before enactment/commencement
    if in_force_start and parsed_as_of < in_force_start:
        return "verified_not_in_force"

    # Check 2: repealed or replaced
    relation = (provision_meta.get("relation") or "none").lower()
    if relation in ("repeal", "replace"):
        repeal_raw = provision_meta.get("repeal_date") or provision_meta.get("amendment_effective_date") or in_force_start
        parsed_repeal = parse_date_string(repeal_raw)
        if parsed_repeal:
            if parsed_as_of >= parsed_repeal:
                return "verified_not_in_force"
        else:
            return "uncertain"

    # Otherwise verified in force
    return "verified_in_force"


def get_corpus_verification_date(manifest_path: Optional[Path] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieves corpus_verification_date from manifest.
    Returns (date_str or None, warning_message or None).
    """
    m_path = manifest_path or Path("data/manifests/processed_manifest.jsonl")
    if not m_path.exists():
        msg = f"Warning: manifest file not found at {m_path}; corpus_verification_date is null"
        logger.warning(msg)
        return None, msg

    try:
        with open(m_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    v_date = item.get("corpus_verification_date")
                    if v_date:
                        return str(v_date).strip(), None
    except Exception as e:
        msg = f"Warning: error reading manifest: {e}; corpus_verification_date is null"
        logger.warning(msg)
        return None, msg

    msg = "Warning: corpus_verification_date is absent from manifest; defaulting to null"
    logger.warning(msg)
    return None, msg


def check_temporal_qualification(
    as_of_date: Optional[str],
    cited_provisions: List[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """
    If as_of_date is provided and no cited provision is verified (all are 'uncertain'),
    returns (True, qualified_response_text).
    """
    if not as_of_date:
        return False, None

    has_verified = any(
        p.get("version_status") in ("verified_in_force", "verified_not_in_force")
        for p in cited_provisions
    )

    if not has_verified:
        qualified_text = f"Legal status as of {as_of_date} cannot be established."
        return True, qualified_text

    return False, None
