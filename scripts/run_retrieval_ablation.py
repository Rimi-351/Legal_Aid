#!/usr/bin/env python3
"""
scripts/run_retrieval_ablation.py
----------------------------------
Week 4 Retrieval Ablation and Banglish Contribution Evaluation Runner.
Evaluates retrieval conditions E1 to E6 on data/benchmarks/benchmark_dev.jsonl.
Reports Recall@5, Recall@10, MRR@10, nDCG@10, breakdowns by modality & domain,
latency, process memory, and failure analysis.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import json
import time
import math
import argparse
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.bm25 import BM25Index, SearchResult, BengaliEnglishTokenizer
from src.evaluation.metrics import (
    compute_reciprocal_rank,
    compute_recall_at_k,
    compute_precision_at_k,
    compute_ndcg_at_k
)
from src.evaluation.logger import get_process_memory_mb


# =============================================================================
# Banglish Phonetic Query Expansion Dictionary
# =============================================================================
BANGLISH_LEGAL_EXPANSION = {
    "chukti": ["চুক্তি", "contract", "agreement"],
    "shromik": ["শ্রমিক", "worker", "labour"],
    "dokandar": ["দোকানদার", "বিক্রেতা", "shopkeeper"],
    "dokan": ["দোকান", "shop"],
    "bhara": ["ভাড়া", "rent", "tenancy"],
    "vara": ["ভাড়া", "rent", "tenancy"],
    "bariwala": ["বাড়িওয়ালা", "landlord"],
    "jomi": ["জমি", "land", "property"],
    "sthabor": ["স্থাবর", "immovable"],
    "shasti": ["শাস্তি", "দণ্ড", "penalty", "punishment"],
    "meyad": ["মেয়াদ", "মেয়াদোত্তীর্ণ", "expiry"],
    "vejal": ["ভেজাল", "adulteration"],
    "bhejal": ["ভেজাল", "adulteration"],
    "borghasto": ["বরখাস্ত", "dismissal", "termination"],
    "chador": ["চাকরি", "employment"],
    "ovijog": ["অভিযোগ", "complaint"],
    "bedokhol": ["বেদখল", "eviction", "dispossession"],
    "deed": ["দলিল", "instrument", "registered"],
    "notice": ["নোটিশ", "notice"]
}


class ExpandedTokenizer(BengaliEnglishTokenizer):
    """Extends tokenizer with optional Banglish phonetic dictionary expansion."""

    def __init__(self, use_char_ngrams: bool = False, ngram_n: int = 3, expand_banglish: bool = False):
        super().__init__(use_char_ngrams=use_char_ngrams, ngram_n=ngram_n)
        self.expand_banglish = expand_banglish

    def tokenize(self, text: str, is_query: bool = False) -> List[str]:
        tokens = super().tokenize(text)
        if is_query and self.expand_banglish:
            expanded = list(tokens)
            for t in tokens:
                if t in BANGLISH_LEGAL_EXPANSION:
                    expanded.extend(BANGLISH_LEGAL_EXPANSION[t])
            return expanded
        return tokens


def load_provisions(provisions_path: Path) -> List[Dict[str, Any]]:
    """Loads active unquarantined statutory provisions."""
    provisions = []
    with open(provisions_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            p = json.loads(line)
            if not p.get("is_quarantined", False):
                provisions.append(p)
    return provisions


def load_dev_benchmark(benchmark_path: Path, filter_covered_only: bool = True, corpus_pids: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """Loads benchmark queries from dev set."""
    queries = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            q = json.loads(line)
            expected = q.get("expected_supporting_provisions", [])
            # If filtering for evaluatable covered queries
            if filter_covered_only and corpus_pids:
                if not expected or not all(pid in corpus_pids for pid in expected):
                    continue
            queries.append(q)
    return queries


def evaluate_retriever_on_benchmark(retriever: Any, queries: List[Dict[str, Any]], condition_name: str) -> Dict[str, Any]:
    """Runs rigorous multi-metric evaluation across all queries."""
    recalls_5 = []
    recalls_10 = []
    mrrs_10 = []
    ndcgs_10 = []
    latencies_ms = []

    modality_metrics: Dict[str, Dict[str, List[float]]] = {}
    domain_metrics: Dict[str, Dict[str, List[float]]] = {}
    failure_cases: List[Dict[str, Any]] = []

    for q in queries:
        qid = q["query_id"]
        qtext = q["original_user_query"]
        modality = q.get("language_and_script", "unknown")
        domain = q.get("legal_domain", "unknown")
        gold = set(q.get("expected_supporting_provisions", []))

        t0 = time.perf_counter()
        results = retriever.search(qtext, top_k=10)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)

        retrieved_pids = [r.provision_id for r in results]

        r5 = compute_recall_at_k(retrieved_pids, gold, k=5)
        r10 = compute_recall_at_k(retrieved_pids, gold, k=10)
        mrr10 = compute_reciprocal_rank(retrieved_pids, gold, k=10)
        ndcg10 = compute_ndcg_at_k(retrieved_pids, gold, k=10)

        recalls_5.append(r5)
        recalls_10.append(r10)
        mrrs_10.append(mrr10)
        ndcgs_10.append(ndcg10)

        # Track failure case (MRR@10 == 0)
        if mrr10 == 0.0 and len(gold) > 0:
            failure_cases.append({
                "query_id": qid,
                "modality": modality,
                "domain": domain,
                "query_text": qtext,
                "expected": list(gold),
                "top_retrieved": retrieved_pids[:3]
            })

        # By modality
        m_dict = modality_metrics.setdefault(modality, {"mrr": [], "r5": [], "r10": [], "ndcg": []})
        m_dict["mrr"].append(mrr10)
        m_dict["r5"].append(r5)
        m_dict["r10"].append(r10)
        m_dict["ndcg"].append(ndcg10)

        # By domain
        d_dict = domain_metrics.setdefault(domain, {"mrr": [], "r5": [], "r10": [], "ndcg": []})
        d_dict["mrr"].append(mrr10)
        d_dict["r5"].append(r5)
        d_dict["r10"].append(r10)
        d_dict["ndcg"].append(ndcg10)

    n = max(len(queries), 1)
    summary = {
        "condition": condition_name,
        "num_queries": len(queries),
        "overall": {
            "recall_at_5": round(sum(recalls_5) / n, 4),
            "recall_at_10": round(sum(recalls_10) / n, 4),
            "mrr_at_10": round(sum(mrrs_10) / n, 4),
            "ndcg_at_10": round(sum(ndcgs_10) / n, 4),
            "avg_latency_ms": round(sum(latencies_ms) / n, 2),
            "peak_rss_mb": get_process_memory_mb()
        },
        "by_modality": {
            m: {
                "count": len(vals["mrr"]),
                "recall_at_5": round(sum(vals["r5"]) / len(vals["r5"]), 4),
                "recall_at_10": round(sum(vals["r10"]) / len(vals["r10"]), 4),
                "mrr_at_10": round(sum(vals["mrr"]) / len(vals["mrr"]), 4),
                "ndcg_at_10": round(sum(vals["ndcg"]) / len(vals["ndcg"]), 4)
            }
            for m, vals in modality_metrics.items()
        },
        "by_domain": {
            d: {
                "count": len(vals["mrr"]),
                "recall_at_5": round(sum(vals["r5"]) / len(vals["r5"]), 4),
                "recall_at_10": round(sum(vals["r10"]) / len(vals["r10"]), 4),
                "mrr_at_10": round(sum(vals["mrr"]) / len(vals["mrr"]), 4),
                "ndcg_at_10": round(sum(vals["ndcg"]) / len(vals["ndcg"]), 4)
            }
            for d, vals in domain_metrics.items()
        },
        "failure_count": len(failure_cases),
        "sample_failures": failure_cases[:5]
    }
    return summary


def run_all_conditions():
    provisions_path = Path("data/processed/provisions.jsonl")
    benchmark_path = Path("data/benchmarks/benchmark_dev.jsonl")

    provisions = load_provisions(provisions_path)
    corpus_pids = {p["provision_id"] for p in provisions}
    queries = load_dev_benchmark(benchmark_path, filter_covered_only=True, corpus_pids=corpus_pids)

    print("=" * 75)
    print("  Legal Aid BD — Week 4 Retrieval Ablation & Banglish Contribution Study")
    print("=" * 75)
    print(f"[*] Evaluated Provisions in Active Corpus: {len(provisions)}")
    print(f"[*] Evaluated Benchmark Dev Queries:      {len(queries)} (Ground Truth Verified)")
    print(f"[*] Process Initial RSS:                  {get_process_memory_mb()} MB\n")

    results = []

    # -------------------------------------------------------------------------
    # E1: BM25 Word Tokens (Standard Baseline)
    # -------------------------------------------------------------------------
    print("[*] Running Condition E1: BM25 Word Tokens...")
    bm25_word = BM25Index(k1=1.5, b=0.75, use_char_ngrams=False)
    bm25_word.fit(provisions)
    res_e1 = evaluate_retriever_on_benchmark(bm25_word, queries, "E1: BM25 Word Tokens")
    results.append(res_e1)

    # -------------------------------------------------------------------------
    # E1-N: BM25 Character 3-Grams (Phonetic Resilience Baseline)
    # -------------------------------------------------------------------------
    print("[*] Running Condition E1-N: BM25 Character 3-Grams...")
    bm25_ngram = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    bm25_ngram.fit(provisions)
    res_e1n = evaluate_retriever_on_benchmark(bm25_ngram, queries, "E1-N: BM25 Char 3-Grams")
    results.append(res_e1n)

    # -------------------------------------------------------------------------
    # E1-QE: BM25 Word Tokens + Banglish Query Expansion
    # -------------------------------------------------------------------------
    print("[*] Running Condition E1-QE: BM25 + Banglish Query Expansion...")
    bm25_qe = BM25Index(k1=1.5, b=0.75, use_char_ngrams=False)
    bm25_qe.tokenizer = ExpandedTokenizer(use_char_ngrams=False, expand_banglish=True)
    bm25_qe.fit(provisions)
    res_e1qe = evaluate_retriever_on_benchmark(bm25_qe, queries, "E1-QE: BM25 + Query Expansion")
    results.append(res_e1qe)

    # -------------------------------------------------------------------------
    # E1-N-QE: BM25 Char 3-Grams + Query Expansion
    # -------------------------------------------------------------------------
    print("[*] Running Condition E1-N-QE: BM25 Char 3-Grams + Query Expansion...")
    bm25_n_qe = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    bm25_n_qe.tokenizer = ExpandedTokenizer(use_char_ngrams=True, ngram_n=3, expand_banglish=True)
    bm25_n_qe.fit(provisions)
    res_e1nqe = evaluate_retriever_on_benchmark(bm25_n_qe, queries, "E1-N-QE: BM25 Char 3-Grams + QE")
    results.append(res_e1nqe)

    # Print Comparative Matrix
    print("\n" + "=" * 90)
    print(f"{'Condition':<32} | {'Recall@5':<9} | {'Recall@10':<9} | {'MRR@10':<8} | {'nDCG@10':<8} | {'Latency':<8} | {'Failures'}")
    print("-" * 90)
    for r in results:
        o = r["overall"]
        print(f"{r['condition']:<32} | {o['recall_at_5']:<9.4f} | {o['recall_at_10']:<9.4f} | {o['mrr_at_10']:<8.4f} | {o['ndcg_at_10']:<8.4f} | {o['avg_latency_ms']:<5.2f} ms | {r['failure_count']:<3}/{r['num_queries']}")
    print("=" * 90)

    # Modality Breakdown Table for E1 vs E1-N vs E1-N-QE
    print("\n" + "=" * 90)
    print("  MODALITY BREAKDOWN (MRR@10 across Language Scripts)")
    print("=" * 90)
    print(f"{'Condition':<32} | {'bn_unicode':<12} | {'banglish':<12} | {'en':<12} | {'code_mixed'}")
    print("-" * 90)
    for r in results:
        bm = r["by_modality"]
        bn_mrr = bm.get("bn_unicode", {}).get("mrr_at_10", 0.0)
        bl_mrr = bm.get("banglish", {}).get("mrr_at_10", 0.0)
        en_mrr = bm.get("en", {}).get("mrr_at_10", 0.0)
        cm_mrr = bm.get("code_mixed", {}).get("mrr_at_10", 0.0)
        print(f"{r['condition']:<32} | {bn_mrr:<12.4f} | {bl_mrr:<12.4f} | {en_mrr:<12.4f} | {cm_mrr:.4f}")
    print("=" * 90)

    # Save JSON summary
    out_path = Path("experiments/week4_retrieval_ablation_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Ablation results saved to: {out_path}")


if __name__ == "__main__":
    run_all_conditions()

