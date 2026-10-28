"""
src/rag/extractive.py
----------------------
Deterministic extractive answer generator.
Assembles answers strictly from retrieved statutory sentences with complete provenance.
"""
import re
from typing import List, Dict, Any, Optional

from .config import settings, check_retrieval_abstention


INSUFFICIENT_EVIDENCE_NOTICE_EN = (
    "Insufficient evidence in retrieved legal sources to answer this question."
)
INSUFFICIENT_EVIDENCE_NOTICE_BN = (
    "সরবরাহকৃত আইনগত ধারাগুলোতে এই প্রশ্নের উত্তর দেওয়ার মতো পর্যাপ্ত প্রমাণ নেই।"
)


def _split_into_sentences(text: str) -> List[str]:
    """Splits text into sentences using Bengali dari and Latin punctuation boundaries."""
    if not text:
        return []
    # Split on newline, Bengali dari (।), double dari (॥), or English period/semicolon
    raw_sentences = re.split(r"[\r\n]+|[।॥\.]\s*", text)
    return [s.strip() for s in raw_sentences if s.strip()]


def extractive_answer(
    query: str,
    evidence: List[Dict[str, Any]],
    lang: str = "en",
    score_threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Assembles a summary strictly from retrieved statutory sentences.
    Returns supporting_passage, act_title, section_id, source_url, record_id,
    and flags insufficient_evidence when retrieval indicates abstention.
    """
    notice = (
        INSUFFICIENT_EVIDENCE_NOTICE_BN
        if lang.lower().startswith("bn") or "banglish" in lang.lower()
        else INSUFFICIENT_EVIDENCE_NOTICE_EN
    )

    should_abstain, _ = check_retrieval_abstention(query, evidence, threshold=score_threshold)
    if should_abstain:
        return {
            "summary": notice,
            "supporting_passage": "",
            "act_title": None,
            "section_id": None,
            "source_url": None,
            "record_id": None,
            "insufficient_evidence": True,
            "claims": []
        }

    top_hit = evidence[0]

    # Extract exact metadata from DB record
    record_id = top_hit.get("record_id") or top_hit.get("provision_id", "")
    act_title = top_hit.get("act_title", "")
    section_id = str(top_hit.get("section_id") or top_hit.get("section_number", ""))
    source_url = top_hit.get("source_url") or top_hit.get("source_file", "")
    full_text = top_hit.get("text", "").strip()

    # Assemble summary from first 1-2 verbatim statutory sentences
    sentences = _split_into_sentences(full_text)
    if sentences:
        summary = " ".join(sentences[:2])
    else:
        summary = full_text

    quote = sentences[0] if sentences else full_text

    return {
        "summary": summary,
        "supporting_passage": full_text,
        "act_title": act_title,
        "section_id": section_id,
        "source_url": source_url,
        "record_id": record_id,
        "insufficient_evidence": False,
        "claims": [
            {
                "text": summary,
                "evidence_ids": ["E1"],
                "quote": quote,
                "record_id": record_id,
                "act_title": act_title,
                "section_id": section_id,
                "source_url": source_url,
                "citation": {
                    "record_id": record_id,
                    "act_title": act_title,
                    "section_id": section_id,
                    "source_url": source_url,
                    "quote": quote,
                },
            }
        ],
    }
