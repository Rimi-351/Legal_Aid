"""
src/rag/api.py
---------------
FastAPI service exposing POST /api/v1/legal/ask endpoint.
Supports modes: extractive, llm, llm_validated, llm_validated_noabstain.
Enforces:
- Final answer text rendered ONLY from validated claims.
- Drops model free-text answer_sections from responses.
- Shared retrieval abstention logic.
- Model abstention bookkeeping in llm_validated_noabstain.
"""
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal, Tuple
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import (
    settings,
    check_retrieval_abstention,
    LEAKAGE_PATTERN,
)
from .extractive import (
    extractive_answer,
    INSUFFICIENT_EVIDENCE_NOTICE_EN,
    INSUFFICIENT_EVIDENCE_NOTICE_BN,
)
from .llm_answer import generate_answer
from .citation_validator import validate
from src.retrieval.bm25 import BM25Index
from src.evaluation.logger import get_process_memory_mb

logger = logging.getLogger(__name__)

app = FastAPI(title="Legal Aid BD RAG API", version="1.0.0")

# Singleton Retriever
_retriever: Optional[BM25Index] = None
_corpus_cache: List[Dict[str, Any]] = []


def get_retriever() -> Tuple[BM25Index, List[Dict[str, Any]]]:
    """Initializes and caches the BM25 lexical retriever over the verified corpus."""
    global _retriever, _corpus_cache
    if _retriever is None:
        if not settings.corpus_path.exists():
            raise FileNotFoundError(f"Corpus file not found: {settings.corpus_path}")

        records = []
        with open(settings.corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    if not p.get("is_quarantined", False):
                        records.append(p)

        index = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
        index.fit(records)
        _retriever = index
        _corpus_cache = records

    return _retriever, _corpus_cache


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------

class CitationModel(BaseModel):
    record_id: Optional[str] = None
    act_title: Optional[str] = None
    section_id: Optional[str] = None
    source_url: Optional[str] = None
    quote: Optional[str] = None


class ClaimModel(BaseModel):
    text: str
    citation: Optional[CitationModel] = None
    validation: Dict[str, Any] = Field(default_factory=dict)


class AskRequest(BaseModel):
    query: str
    lang: str = "en"
    mode: Literal["extractive", "llm", "llm_validated", "llm_validated_noabstain"] = "llm_validated"


class AskResponse(BaseModel):
    answer: str
    claims: List[ClaimModel]
    abstained: bool
    fallback_used: bool
    latency_ms: float
    peak_rss_mb: float


# -----------------------------------------------------------------------------
# Endpoint Implementation
# -----------------------------------------------------------------------------

@app.post("/api/v1/legal/ask", response_model=AskResponse)
def ask_legal(request: AskRequest) -> AskResponse:
    """Executes the legal RAG pipeline in the requested operational mode."""
    t0 = time.perf_counter()

    retriever, _ = get_retriever()
    search_results = retriever.search(request.query, top_k=settings.retrieval_top_k)

    # Format evidence records
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
        }
        for r in search_results
    ]

    abstained = False
    fallback_used = False
    final_answer: str = ""
    final_claims: List[ClaimModel] = []

    # Mode 1: Pure Extractive
    if request.mode == "extractive":
        ext = extractive_answer(request.query, evidence, lang=request.lang)
        abstained = ext.get("insufficient_evidence", False)
        final_answer = ext.get("summary", "")
        for c in ext.get("claims", []):
            final_claims.append(
                ClaimModel(
                    text=c["text"],
                    citation=CitationModel(
                        record_id=ext.get("record_id"),
                        act_title=ext.get("act_title"),
                        section_id=ext.get("section_id"),
                        source_url=ext.get("source_url"),
                        quote=c.get("quote"),
                    ),
                    validation={"match_type": "exact", "is_valid": True},
                )
            )

    # Mode 2: Raw Local LLM (Unvalidated)
    elif request.mode == "llm":
        raw_llm = generate_answer(request.query, evidence, lang=request.lang)
        fallback_used = raw_llm.get("fallback_used", False)
        if raw_llm.get("abstain") is True:
            abstained = True
            final_answer = raw_llm.get("reason", "Abstained")
        else:
            # Render answer ONLY from claims, drop answer_sections
            claims_text = []
            for c in raw_llm.get("claims", []):
                t = c.get("text", "")
                if not LEAKAGE_PATTERN.search(t):
                    claims_text.append(t)
                final_claims.append(
                    ClaimModel(
                        text=c.get("text", ""),
                        citation=CitationModel(quote=c.get("quote")),
                        validation={"unvalidated": True},
                    )
                )
            final_answer = " ".join(claims_text)

    # Mode 3: LLM Validated (With Abstention Threshold & Checks)
    elif request.mode == "llm_validated":
        should_abstain, reason = check_retrieval_abstention(
            request.query, evidence, threshold=settings.abstain_threshold
        )
        if should_abstain:
            abstained = True
            notice = (
                INSUFFICIENT_EVIDENCE_NOTICE_BN
                if request.lang.lower().startswith("bn") or "banglish" in request.lang.lower()
                else INSUFFICIENT_EVIDENCE_NOTICE_EN
            )
            final_answer = notice
            final_claims = []
        else:
            llm_res = generate_answer(request.query, evidence, lang=request.lang)
            fallback_used = llm_res.get("fallback_used", False)
            if llm_res.get("abstain") is True:
                abstained = True
                final_answer = llm_res.get("reason", "Evidence insufficient")
                final_claims = []
            else:
                val_res = validate(llm_res, evidence, query=request.query, lang=request.lang)
                fallback_used = fallback_used or val_res.fallback_used
                # Final answer rendered strictly from validated claims
                final_answer = val_res.answer.get("answer", "")
                for vc in val_res.validated_claims:
                    cit = None
                    if vc.citation:
                        cit = CitationModel(
                            record_id=vc.citation.get("record_id"),
                            act_title=vc.citation.get("act_title"),
                            section_id=vc.citation.get("section_id"),
                            source_url=vc.citation.get("source_url"),
                            quote=vc.citation.get("quote"),
                        )
                    final_claims.append(
                        ClaimModel(
                            text=vc.text,
                            citation=cit,
                            validation={
                                "is_valid": vc.is_valid,
                                "match_type": vc.match_type,
                                "rejection_reasons": vc.rejection_reasons,
                                "flags": vc.flags,
                            },
                        )
                    )

    # Mode 4: LLM Validated (No Abstention Threshold)
    elif request.mode == "llm_validated_noabstain":
        llm_res = generate_answer(request.query, evidence, lang=request.lang)
        fallback_used = llm_res.get("fallback_used", False)
        # Set is_abstained from model {"abstain": true} output
        if llm_res.get("abstain") is True:
            abstained = True
            final_answer = llm_res.get("reason", "Evidence insufficient")
            final_claims = []
        else:
            val_res = validate(llm_res, evidence, query=request.query, lang=request.lang)
            fallback_used = fallback_used or val_res.fallback_used
            # Final answer rendered strictly from validated claims
            final_answer = val_res.answer.get("answer", "")
            for vc in val_res.validated_claims:
                cit = None
                if vc.citation:
                    cit = CitationModel(
                        record_id=vc.citation.get("record_id"),
                        act_title=vc.citation.get("act_title"),
                        section_id=vc.citation.get("section_id"),
                        source_url=vc.citation.get("source_url"),
                        quote=vc.citation.get("quote"),
                    )
                final_claims.append(
                    ClaimModel(
                        text=vc.text,
                        citation=cit,
                        validation={
                            "is_valid": vc.is_valid,
                            "match_type": vc.match_type,
                            "rejection_reasons": vc.rejection_reasons,
                            "flags": vc.flags,
                        },
                    )
                )

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    peak_rss = get_process_memory_mb()

    return AskResponse(
        answer=final_answer,
        claims=final_claims,
        abstained=abstained,
        fallback_used=fallback_used,
        latency_ms=latency_ms,
        peak_rss_mb=peak_rss,
    )
