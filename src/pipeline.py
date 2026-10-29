"""
src/pipeline.py
---------------
Unified execution pipeline for Legal Aid BD retrieval-augmented generation.
Central entry point called by both CLI and UI. No logic in the UI.

Core functionalities:
1. Script-ratio language detection (Bangla, Latin, Banglish, Mixed) with override.
2. Query normalization preserving original user text.
3. Lexical BM25 retrieval over verified statutory corpus.
4. Temporal version auditing and as_of_date qualification.
5. RAG execution across modes (extractive, llm, llm_validated, llm_validated_noabstain).
6. Strict citation validation via citation_validator.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import time
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.config import (
    settings,
    check_retrieval_abstention,
    LEAKAGE_PATTERN,
)
from src.retrieval.bm25 import BM25Index
from src.retrieval.temporal import (
    get_corpus_verification_date,
    check_temporal_qualification,
)
from src.rag.extractive import (
    extractive_answer,
    INSUFFICIENT_EVIDENCE_NOTICE_EN,
    INSUFFICIENT_EVIDENCE_NOTICE_BN,
)
from src.rag.llm_answer import generate_answer
from src.rag.citation_validator import validate

logger = logging.getLogger(__name__)

# Common Banglish lexicon markers
BANGLISH_KEYWORDS = {
    "ki", "kivabe", "korbo", "hobe", "chuti", "shrom", "ain", "dharaye",
    "keno", "koto", "taka", "pabo", "chakri", "borkhasto", "malik", "shromik",
    "bhara", "bari", "basa", "dokan", "jomi", "kes", "mamla", "shathe",
    "theke", "poribar", "noy", "ache", "nei", "korte", "parbe", "er",
    "jonno", "kotodin", "kora", "shomoy", "shorkari", "nirdharito",
    "onujayi", "kormo", "dofa", "dhara", "notish", "chara", "beton"
}


@dataclass
class PipelineResult:
    """Dataclass capturing the complete lifecycle and outputs of a legal inquiry."""
    original_text: str
    detected_lang: str  # bn | en | banglish | mixed
    lang_overridden: bool
    normalized_query: str
    retrieved: List[Dict[str, Any]]  # ids, scores, text, version_status
    answer: str
    answer_lang: str
    abstained: bool
    fallback_used: bool
    validation: List[Dict[str, Any]]  # validation details per claim
    version_status: Dict[str, Any]  # provision_id -> status, corpus_verification_date
    latency_ms: float
    warning: Optional[str] = None
    claims: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "detected_lang": self.detected_lang,
            "lang_overridden": self.lang_overridden,
            "normalized_query": self.normalized_query,
            "retrieved": self.retrieved,
            "answer": self.answer,
            "answer_lang": self.answer_lang,
            "abstained": self.abstained,
            "fallback_used": self.fallback_used,
            "validation": self.validation,
            "version_status": self.version_status,
            "latency_ms": self.latency_ms,
            "warning": self.warning,
            "claims": self.claims,
        }


def detect_language(text: str) -> str:
    """
    Language detection via script-ratio heuristic and phonetic markers:
    - Bengali script characters (\u0980-\u09FF)
    - Latin ASCII characters ([a-zA-Z])
    Returns one of: 'bn' | 'en' | 'banglish' | 'mixed'.
    """
    if not text or not text.strip():
        return "en"

    bengali_chars = len(re.findall(r"[\u0980-\u09FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    total_script = bengali_chars + latin_chars

    if total_script == 0:
        return "en"

    # Pure Bengali script
    if bengali_chars > 0 and latin_chars == 0:
        return "bn"

    # Pure Latin script -> distinguish English vs Banglish
    if latin_chars > 0 and bengali_chars == 0:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        banglish_matches = sum(1 for w in words if w in BANGLISH_KEYWORDS)
        if banglish_matches >= 1:
            return "banglish"
        return "en"

    # Mixed script
    bn_ratio = bengali_chars / total_script
    latin_ratio = latin_chars / total_script
    if bn_ratio >= 0.15 and latin_ratio >= 0.15:
        return "mixed"

    if bn_ratio > latin_ratio:
        return "bn"
    else:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        if any(w in BANGLISH_KEYWORDS for w in words):
            return "banglish"
        return "en"


def normalize_query_text(text: str) -> str:
    """Performs Unicode NFC normalization and clean whitespace handling."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFC", text.strip())
    return re.sub(r"\s+", " ", norm)


# Singleton BM25 index and cached records
_retriever: Optional[BM25Index] = None
_corpus_records: List[Dict[str, Any]] = []


def get_pipeline_retriever(
    corpus_path: Optional[Path] = None,
) -> Tuple[BM25Index, List[Dict[str, Any]]]:
    """Loads and caches the singleton BM25 index over the verified corpus."""
    global _retriever, _corpus_records
    c_path = corpus_path or settings.corpus_path
    if not c_path.exists():
        raise FileNotFoundError(f"Corpus file not found: {c_path}")

    if _retriever is None or corpus_path is not None:
        records = []
        with open(c_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    if not p.get("is_quarantined", False):
                        records.append(p)

        index = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
        index.fit(records)
        if corpus_path is None:
            _retriever = index
            _corpus_records = records
        return index, records

    return _retriever, _corpus_records


def ask(
    query: str,
    lang_override: Optional[str] = None,
    as_of_date: Optional[str] = None,
    mode: Literal["extractive", "llm", "llm_validated", "llm_validated_noabstain"] = "llm_validated",
    threshold: Optional[float] = None,
) -> PipelineResult:
    """
    Central execution entry point for legal inquiries.
    Called identically by both the CLI and Streamlit UI.
    """
    t0 = time.perf_counter()

    if not query or not query.strip():
        return PipelineResult(
            original_text=query,
            detected_lang="en",
            lang_overridden=False,
            normalized_query="",
            retrieved=[],
            answer="Query text cannot be empty.",
            answer_lang="en",
            abstained=True,
            fallback_used=False,
            validation=[],
            version_status={},
            latency_ms=0.0,
        )

    # 1. Language Detection & Override Handling
    detected = detect_language(query)
    if lang_override and lang_override.lower() not in ("auto", "none", ""):
        effective_lang = lang_override.lower().strip()
        lang_overridden = (effective_lang != detected)
    else:
        effective_lang = detected
        lang_overridden = False

    # 2. Query Normalization (Never replaces original text; preserves original_text)
    normalized_query = normalize_query_text(query)

    # 3. Retrieval over Verified Corpus
    retriever, _ = get_pipeline_retriever()
    search_results = retriever.search(
        normalized_query, top_k=settings.retrieval_top_k, as_of_date=as_of_date
    )

    corpus_v_date, v_warning = get_corpus_verification_date()

    evidence: List[Dict[str, Any]] = [
        {
            "record_id": r.provision_id,
            "provision_id": r.provision_id,
            "act_title": r.act_title,
            "section_id": r.section_number,
            "section_number": r.section_number,
            "source_url": r.source_file,
            "source_file": r.source_file,
            "text": r.text,
            "language": r.language,
            "score": r.score,
            "version_status": getattr(r, "version_status", "uncertain"),
        }
        for r in search_results
    ]

    version_status_map = {
        e["provision_id"]: e["version_status"] for e in evidence
    }
    version_meta = {
        "statuses": version_status_map,
        "corpus_verification_date": corpus_v_date,
    }

    # 4. Temporal Version Qualification Check
    if as_of_date:
        is_unverified, qualified_text = check_temporal_qualification(as_of_date, evidence)
        if is_unverified:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return PipelineResult(
                original_text=query,
                detected_lang=detected,
                lang_overridden=lang_overridden,
                normalized_query=normalized_query,
                retrieved=evidence,
                answer=qualified_text or f"Legal status as of {as_of_date} cannot be established.",
                answer_lang=effective_lang,
                abstained=True,
                fallback_used=False,
                validation=[],
                version_status=version_meta,
                latency_ms=latency_ms,
                warning=v_warning,
                claims=[],
            )

    abstained = False
    fallback_used = False
    final_answer: str = ""
    claims_list: List[Dict[str, Any]] = []
    validation_list: List[Dict[str, Any]] = []

    # 5. Operational Modes
    if mode == "extractive":
        ext = extractive_answer(normalized_query, evidence, lang=effective_lang)
        abstained = ext.get("insufficient_evidence", False)
        final_answer = ext.get("summary", "")
        for c in ext.get("claims", []):
            claim_dict = {
                "text": c["text"],
                "citation": {
                    "record_id": ext.get("record_id"),
                    "act_title": ext.get("act_title"),
                    "section_id": ext.get("section_id"),
                    "source_url": ext.get("source_url"),
                    "quote": c.get("quote"),
                },
                "is_valid": True,
            }
            claims_list.append(claim_dict)
            validation_list.append({"match_type": "exact", "is_valid": True})

    elif mode == "llm":
        raw_llm = generate_answer(normalized_query, evidence, lang=effective_lang)
        fallback_used = raw_llm.get("fallback_used", False)
        if raw_llm.get("abstain") is True:
            abstained = True
            final_answer = raw_llm.get("reason", "Abstained")
        else:
            claims_text = []
            for c in raw_llm.get("claims", []):
                t = c.get("text", "")
                if not LEAKAGE_PATTERN.search(t):
                    claims_text.append(t)
                claims_list.append({
                    "text": t,
                    "citation": {"quote": c.get("quote")},
                    "is_valid": None,
                })
                validation_list.append({"unvalidated": True})
            final_answer = " ".join(claims_text)

    elif mode == "llm_validated":
        should_abstain, reason = check_retrieval_abstention(
            normalized_query, evidence, threshold=threshold or settings.abstain_threshold
        )
        if should_abstain:
            abstained = True
            notice = (
                INSUFFICIENT_EVIDENCE_NOTICE_BN
                if effective_lang.lower().startswith("bn") or "banglish" in effective_lang.lower()
                else INSUFFICIENT_EVIDENCE_NOTICE_EN
            )
            final_answer = notice
        else:
            llm_res = generate_answer(normalized_query, evidence, lang=effective_lang)
            fallback_used = llm_res.get("fallback_used", False)
            if llm_res.get("abstain") is True:
                abstained = True
                final_answer = llm_res.get("reason", "Evidence insufficient")
            else:
                val_res = validate(llm_res, evidence, query=normalized_query, lang=effective_lang)
                fallback_used = fallback_used or val_res.fallback_used
                final_answer = val_res.answer.get("answer", "")
                for vc in val_res.validated_claims:
                    claims_list.append({
                        "text": vc.text,
                        "citation": vc.citation,
                        "is_valid": vc.is_valid,
                        "rejection_reasons": vc.rejection_reasons,
                    })
                    validation_list.append({
                        "is_valid": vc.is_valid,
                        "match_type": vc.match_type,
                        "rejection_reasons": vc.rejection_reasons,
                        "flags": vc.flags,
                    })

    elif mode == "llm_validated_noabstain":
        llm_res = generate_answer(normalized_query, evidence, lang=effective_lang)
        fallback_used = llm_res.get("fallback_used", False)
        if llm_res.get("abstain") is True:
            abstained = True
            final_answer = llm_res.get("reason", "Evidence insufficient")
        else:
            val_res = validate(llm_res, evidence, query=normalized_query, lang=effective_lang)
            fallback_used = fallback_used or val_res.fallback_used
            final_answer = val_res.answer.get("answer", "")
            for vc in val_res.validated_claims:
                claims_list.append({
                    "text": vc.text,
                    "citation": vc.citation,
                    "is_valid": vc.is_valid,
                    "rejection_reasons": vc.rejection_reasons,
                })
                validation_list.append({
                    "is_valid": vc.is_valid,
                    "match_type": vc.match_type,
                    "rejection_reasons": vc.rejection_reasons,
                    "flags": vc.flags,
                })

    # 6. Strict Exit Gate: No response claims 'as of <date>' unless every cited provision is verified_*
    if as_of_date:
        cited_ids = {
            c["citation"].get("record_id")
            for c in claims_list if c.get("citation") and c["citation"].get("record_id")
        }
        cited_ev = [
            e for e in evidence
            if e.get("record_id") in cited_ids or e.get("provision_id") in cited_ids
        ]
        if cited_ev and not all(
            e.get("version_status") in ("verified_in_force", "verified_not_in_force")
            for e in cited_ev
        ):
            if "as of" in final_answer.lower():
                final_answer = f"Legal status as of {as_of_date} cannot be established."
                claims_list = []
                validation_list = []

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return PipelineResult(
        original_text=query,
        detected_lang=detected,
        lang_overridden=lang_overridden,
        normalized_query=normalized_query,
        retrieved=evidence,
        answer=final_answer,
        answer_lang=effective_lang,
        abstained=abstained,
        fallback_used=fallback_used,
        validation=validation_list,
        version_status=version_meta,
        latency_ms=latency_ms,
        warning=v_warning,
        claims=claims_list,
    )


def cli_main() -> None:
    """CLI runner interface."""
    import argparse
    parser = argparse.ArgumentParser(description="Legal Aid BD Pipeline CLI")
    parser.add_argument("query", type=str, help="Legal question to evaluate")
    parser.add_argument("--lang", type=str, default=None, help="Language override (bn|en|banglish|auto)")
    parser.add_argument("--as-of-date", type=str, default=None, help="Statutory version as-of date (YYYY-MM-DD)")
    parser.add_argument("--mode", type=str, default="llm_validated", choices=["extractive", "llm", "llm_validated", "llm_validated_noabstain"])
    args = parser.parse_args()

    result = ask(
        query=args.query,
        lang_override=args.lang,
        as_of_date=args.as_of_date,
        mode=args.mode,
    )

    print("\n" + "=" * 70)
    print("  Legal Aid BD Pipeline Result")
    print("=" * 70)
    print(f"Original Query   : {result.original_text}")
    print(f"Detected Lang    : {result.detected_lang} (Overridden: {result.lang_overridden})")
    print(f"Normalized Query : {result.normalized_query}")
    print(f"Operational Mode : {args.mode}")
    print(f"Abstained        : {result.abstained}")
    print(f"Fallback Used    : {result.fallback_used}")
    print(f"Latency          : {result.latency_ms} ms")
    print("-" * 70)
    print("Answer:")
    print(result.answer)
    print("-" * 70)
    print(f"Retrieved Records: {len(result.retrieved)}")
    for r in result.retrieved:
        print(f"  - [{r.get('score'):.2f}] {r.get('provision_id')} ({r.get('act_title')} S{r.get('section_number')}) - status: {r.get('version_status')}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    cli_main()
