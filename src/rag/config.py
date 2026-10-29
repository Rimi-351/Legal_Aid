"""
src/rag/config.py
------------------
Centralized configuration settings for Week 5 Legal RAG pipeline.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os
import re


# Deterministic scan regex: rejects mentions of section|Act|ধারা|আইন|https?:// followed by digits
# Word boundary \b prevents matching within Latin words like 'fact' or 'impact'
LEAKAGE_PATTERN = re.compile(
    r"(?:(?:\bsection|\bact|ধারা|আইন)\s*[\d০-৯]+|https?://\S*[\d০-৯]*)",
    re.IGNORECASE | re.UNICODE
)

FOREIGN_JURISDICTION_PATTERN = re.compile(
    r"\b(?:uk|united kingdom|india|california|united states|usa|west bengal)\b|\bu\.s\.(?:a\b|\b)?|(?i:ভারত|পশ্চিমবঙ্গ|যুক্তরাজ্য|ক্যালিফোর্নিয়া)",
    re.IGNORECASE | re.UNICODE
)

QUERY_SECTION_PATTERN = re.compile(
    r"(?:section|sec\.?|s\.)\s*([0-9]+)|(?:ধারা|দফা|অনুচ্ছেদ)\s*([০-৯0-9]+)|([০-৯0-9]+)\s*(?:ধারা|ধারায়|নং ধারা)",
    re.IGNORECASE | re.UNICODE
)

ACT_PATTERNS = {
    "contract": re.compile(r"\b(?:contract\s*act|the\s*contract\s*act)\b|চুক্তি\s*আইন", re.IGNORECASE | re.UNICODE),
    "labour": re.compile(r"\b(?:labour\s*act|labor\s*act|bla)\b|শ্রম\s*আইন", re.IGNORECASE | re.UNICODE),
    "consumer": re.compile(r"\b(?:consumer\s*rights|consumer\s*protection|crpa)\b|ভোক্তা[-\s]*অধিকার", re.IGNORECASE | re.UNICODE),
    "rent": re.compile(r"\b(?:premises\s*rent|rent\s*control|prca)\b|বাড়ি\s*ভাড়া|বাড়ি\s*ভাড়া", re.IGNORECASE | re.UNICODE),
}


def normalize_numerals(text: str) -> str:
    """Converts Bengali numerals (০-৯) to ASCII digits (0-9)."""
    if not text:
        return ""
    return str(text).translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))


def extract_query_section(query: str) -> Optional[str]:
    """Extracts statutory section number referenced in a user query if present."""
    m = QUERY_SECTION_PATTERN.search(query)
    if not m:
        return None
    raw = m.group(1) or m.group(2) or m.group(3)
    return normalize_numerals(raw) if raw else None


def identify_query_act(query: str) -> Optional[str]:
    """Identifies statutory Act referenced in a user query if present."""
    for act_key, pat in ACT_PATTERNS.items():
        if pat.search(query):
            return act_key
    return None


def record_matches_act(record: Dict[str, Any], act_key: str) -> bool:
    """Checks whether a retrieved statutory record belongs to the named Act."""
    act_title = (record.get("act_title") or "").lower()
    rid = (record.get("record_id") or record.get("provision_id") or "").lower()
    if act_key == "contract":
        return "contract" in act_title or "contract" in rid
    elif act_key == "labour":
        return "শ্রম" in act_title or "labour" in act_title or "bla" in rid
    elif act_key == "consumer":
        return "ভোক্তা" in act_title or "consumer" in act_title or "crpa" in rid
    elif act_key == "rent":
        return "ভাড়া" in act_title or "ভাড়া" in act_title or "rent" in act_title or "prca" in rid
    return False


def is_foreign_jurisdiction_query(query: str) -> bool:
    """Checks if the query explicitly targets a non-Bangladesh legal jurisdiction."""
    return bool(FOREIGN_JURISDICTION_PATTERN.search(query))


def check_retrieval_abstention(
    query: str,
    evidence: List[Dict[str, Any]],
    threshold: Optional[float] = None
) -> Tuple[bool, str]:
    """
    Centralized abstention verification:
    1. Checks if evidence is empty.
    2. Checks if query targets a foreign jurisdiction.
    3. Checks if query cites a specific statutory section.
       If an Act is named in the query, the section must belong to records of that Act.
       If no Act is named, the section must exist in the retrieved set.
    4. Checks if top retrieval score falls below the calibrated abstention threshold.
    Returns (should_abstain: bool, reason: str).
    """
    if not evidence:
        return True, "No retrieved legal records"

    if is_foreign_jurisdiction_query(query):
        return True, "Query references foreign jurisdiction not in Bangladesh legal corpus"

    named_sec = extract_query_section(query)
    if named_sec:
        query_act = identify_query_act(query)
        if query_act:
            matching_act_secs = [
                normalize_numerals(str(r.get("section_id") or r.get("section_number") or ""))
                for r in evidence
                if record_matches_act(r, query_act)
            ]
            if named_sec not in matching_act_secs:
                return True, f"Named section '{named_sec}' does not exist in named Act '{query_act}' among retrieved provisions"
        else:
            retrieved_secs = [
                normalize_numerals(str(r.get("section_id") or r.get("section_number") or ""))
                for r in evidence
            ]
            if named_sec not in retrieved_secs:
                return True, f"Named section '{named_sec}' is absent from retrieved statutory provisions"

    top_hit = evidence[0]
    top_score = float(top_hit.get("score", 0.0))
    th = threshold if threshold is not None else settings.abstain_threshold
    if top_score < th:
        return True, f"Top retrieval score ({top_score:.2f}) is below abstention threshold ({th:.2f})"

    return False, ""


@dataclass(frozen=True)
class RAGSettings:
    """Immutable runtime configuration for the legal RAG pipeline."""
    # LLM Settings (From Week 1 Model Feasibility)
    llm_model: str = os.getenv("RAG_LLM_MODEL", "qwen2.5:3b")
    llm_temperature: float = 0.0
    llm_top_p: float = 1.0
    llm_seed: int = 42
    llm_max_tokens: int = 1024
    llm_num_ctx: int = 4096
    llm_keep_alive: str = "30m"
    llm_timeout_sec: float = 300.0
    llm_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    # LLM Evidence Capping
    llm_max_evidence_records: int = 3
    llm_max_evidence_chars: int = 1200

    # Retrieval & Abstention (Tuned on dev split for maximum F1)
    abstain_threshold: float = float(os.getenv("RAG_ABSTAIN_THRESHOLD", "30.0"))
    corpus_path: Path = Path(os.getenv("RAG_CORPUS_PATH", "data/processed/provisions.jsonl"))
    retrieval_top_k: int = 5

    # Quote Citation Mode (Week 8 Quote-Copy Fix)
    # When True: LLM emits evidence_id + sentence_index (e.g., "E1:S2"); quote is extracted verbatim by construction.
    # When False: LLM copies verbatim quote text directly (legacy Week 5 mode).
    use_sentence_index_citations: bool = bool(int(os.getenv("USE_SENTENCE_INDEX_CITATIONS", "1")))

    # Document Upload & Security Settings (Week 7)
    max_upload_size_mb: float = float(os.getenv("MAX_UPLOAD_SIZE_MB", "25.0"))
    allowed_upload_extensions: Tuple[str, ...] = (".pdf", ".docx")
    ui_host: str = os.getenv("STREAMLIT_SERVER_ADDRESS", "127.0.0.1")


settings = RAGSettings()
