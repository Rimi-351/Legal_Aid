"""
src/rag/citation_validator.py
------------------------------
Deterministic citation validation and claim verification engine.
Enforces:
1. Every evidence_id in claims must map to a retrieved DB record.
2. Act title, section ID, and source URL are populated strictly from DB records.
3. Quotes must be exact or normalized substrings of the cited statutory text (minimum 20 chars).
4. Any invalid claim triggers immediate safe extractive fallback.
5. Final answer text is rendered ONLY from validated claims (model free-text answer_sections dropped).
6. Deterministic scan over model free text rejects statutory citation or URL leakage patterns.
"""
import re
import unicodedata
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from .config import LEAKAGE_PATTERN
from .extractive import extractive_answer

logger = logging.getLogger(__name__)


def normalize_for_quote_match(text: str) -> str:
    """
    Normalizes text for substring quote verification:
    - Unicode NFC normalization
    - Bengali numerals to ASCII digits
    - Bengali punctuation (dari/double-dari) to standard dot
    - Whitespace collapse
    - Lowercase
    """
    if not text:
        return ""
    # 1. Unicode NFC
    t = unicodedata.normalize("NFC", text)
    # 2. Bengali numerals to ASCII: ০-৯ -> 0-9
    t = t.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))
    # 3. Punctuation normalization
    t = t.replace("।", ".").replace("॥", ".")
    # 4. Whitespace collapse
    t = re.sub(r"\s+", " ", t).strip()
    return t.lower()


@dataclass
class ClaimValidationResult:
    text: str
    is_valid: bool
    match_type: str  # 'exact' | 'normalized' | 'fail'
    citation: Optional[Dict[str, Any]]
    rejection_reasons: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.citation:
            d["record_id"] = self.citation.get("record_id")
            d["act_title"] = self.citation.get("act_title")
            d["section_id"] = self.citation.get("section_id")
            d["source_url"] = self.citation.get("source_url")
            d["quote"] = self.citation.get("quote")
        return d


@dataclass
class ValidationResult:
    is_valid: bool
    fallback_used: bool
    answer: Any
    validated_claims: List[ClaimValidationResult]
    rejection_log: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate(
    answer: Dict[str, Any],
    evidence_records: List[Dict[str, Any]],
    query: str = "",
    lang: str = "en"
) -> ValidationResult:
    """
    Deterministically validates LLM-generated answer and claims against retrieved DB records.
    Enforces all Week 5 hardening rules:
    - Validate ALL evidence_ids per claim.
    - Minimum quote length >= 20 normalized characters.
    - If ANY claim is dropped, fall back to extractive.
    - On fallback, return claims[] from extractive answer only.
    - Final answer rendered strictly from validated claims; model answer_sections dropped.
    """
    # If the answer already represents an abstention
    if answer.get("abstain") is True:
        return ValidationResult(
            is_valid=True,
            fallback_used=False,
            answer={"answer": answer.get("reason", "Abstained"), "claims": []},
            validated_claims=[],
            rejection_log=[]
        )

    # Deterministic scan over model free text (answer_sections)
    raw_sections = answer.get("answer_sections", {})
    if isinstance(raw_sections, dict):
        for sec_name, items in raw_sections.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str) and LEAKAGE_PATTERN.search(item):
                        logger.warning(
                            f"Dropping model free text matching legal leakage pattern in section '{sec_name}': {item}"
                        )

    # Build lookup map from evidence ID (E1, E2, ...) and record_id to DB record
    evidence_map: Dict[str, Dict[str, Any]] = {}
    for idx, rec in enumerate(evidence_records, 1):
        evidence_map[f"E{idx}"] = rec
        evidence_map[f"[E{idx}]"] = rec
        rid = rec.get("record_id") or rec.get("provision_id")
        if rid:
            evidence_map[rid] = rec

    raw_claims = answer.get("claims", [])
    candidate_claims: List[ClaimValidationResult] = []
    rejection_log: List[Dict[str, Any]] = []

    for c_idx, claim in enumerate(raw_claims):
        claim_text = claim.get("text", "").strip()
        e_ids = claim.get("evidence_ids", [])
        quote = claim.get("quote", "").strip()

        rejection_reasons: List[str] = []
        flags: List[str] = []

        # Check: Scan claim text for forbidden leakage patterns
        if LEAKAGE_PATTERN.search(claim_text):
            rejection_reasons.append("Claim text matches forbidden statutory citation or URL leakage pattern")
            logger.warning(f"Rejected claim text due to leakage pattern: {claim_text}")

        # Check a: Validate ALL evidence_ids per claim, not just [0]
        matched_rec = None
        if not e_ids:
            rejection_reasons.append("Claim does not cite any evidence_id")
        else:
            for eid in e_ids:
                s_eid = str(eid).strip()
                if s_eid not in evidence_map:
                    rejection_reasons.append(f"Invalid evidence_id '{s_eid}': not in retrieved set")
                elif matched_rec is None:
                    matched_rec = evidence_map[s_eid]

        # Check b: Check if model attempted to emit Act/Section/URL and flag mismatch
        if matched_rec:
            db_act = matched_rec.get("act_title", "")
            db_sec = str(matched_rec.get("section_id") or matched_rec.get("section_number", ""))
            db_url = matched_rec.get("source_url") or matched_rec.get("source_file", "")
            db_rid = matched_rec.get("record_id") or matched_rec.get("provision_id", "")

            model_sec = claim.get("section_id") or claim.get("section_number")
            if model_sec is not None and str(model_sec).strip() != db_sec:
                flags.append(f"model_emitted_wrong_section: model={model_sec}, db={db_sec}")
                logger.warning(f"Model-emitted wrong section flagged: model={model_sec}, db={db_sec}")

            model_url = claim.get("source_url")
            if model_url is not None and str(model_url).strip() != db_url:
                flags.append(f"model_emitted_url_ignored: {model_url}")

            citation_payload = {
                "record_id": db_rid,
                "act_title": db_act,
                "section_id": db_sec,
                "source_url": db_url,
                "quote": quote
            }
        else:
            citation_payload = None

        # Check c: Quote substring and length verification
        match_type = "fail"
        if matched_rec and quote:
            norm_quote = normalize_for_quote_match(quote)
            # Minimum quote length: >= 20 chars after normalization
            if len(norm_quote) < 20:
                match_type = "fail"
                rejection_reasons.append(
                    f"Quote too short ({len(norm_quote)} chars after normalization, minimum is 20)"
                )
            else:
                rec_text = matched_rec.get("text", "")
                if quote in rec_text:
                    match_type = "exact"
                else:
                    norm_rec = normalize_for_quote_match(rec_text)
                    if norm_quote in norm_rec:
                        match_type = "normalized"
                    else:
                        match_type = "fail"
                        rejection_reasons.append(
                            "Quote is not an exact or normalized substring of cited passage"
                        )
        elif matched_rec and not quote:
            rejection_reasons.append("Claim missing required quote")

        is_claim_valid = (len(rejection_reasons) == 0) and (match_type in ("exact", "normalized"))

        if not is_claim_valid:
            rejection_info = {
                "claim_index": c_idx,
                "claim_text": claim_text,
                "reasons": rejection_reasons,
                "match_type": match_type
            }
            rejection_log.append(rejection_info)
            logger.warning(f"Rejected claim {c_idx}: {rejection_reasons}")

        candidate_claims.append(ClaimValidationResult(
            text=claim_text,
            is_valid=is_claim_valid,
            match_type=match_type,
            citation=citation_payload,
            rejection_reasons=rejection_reasons,
            flags=flags
        ))

    # Fallback rule: if ANY claim is dropped or zero claims returned, fall back to extractive
    any_claim_dropped = (len(candidate_claims) == 0) or any(not c.is_valid for c in candidate_claims)

    if any_claim_dropped:
        fallback = extractive_answer(query, evidence_records, lang=lang)
        extractive_claims: List[ClaimValidationResult] = []
        for c in fallback.get("claims", []):
            extractive_claims.append(
                ClaimValidationResult(
                    text=c["text"],
                    is_valid=True,
                    match_type="exact",
                    citation={
                        "record_id": fallback.get("record_id"),
                        "act_title": fallback.get("act_title"),
                        "section_id": fallback.get("section_id"),
                        "source_url": fallback.get("source_url"),
                        "quote": c.get("quote"),
                    },
                    rejection_reasons=[],
                    flags=["fallback_extractive"]
                )
            )
        # On fallback, return claims[] from extractive answer only, never the rejected claims
        return ValidationResult(
            is_valid=False,
            fallback_used=True,
            answer={
                "answer": fallback.get("summary", ""),
                "claims": [c.to_dict() for c in extractive_claims]
            },
            validated_claims=extractive_claims,
            rejection_log=rejection_log
        )

    # All claims valid: render final answer text ONLY from validated claims
    final_answer_text = " ".join(c.text for c in candidate_claims)
    cleaned_answer = {
        "answer": final_answer_text,
        "claims": [c.to_dict() for c in candidate_claims]
    }

    return ValidationResult(
        is_valid=True,
        fallback_used=False,
        answer=cleaned_answer,
        validated_claims=candidate_claims,
        rejection_log=rejection_log
    )
