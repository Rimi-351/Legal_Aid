#!/usr/bin/env python3
"""
scripts/run_retrieval_experiment.py
-----------------------------------
End-to-end reproducible retrieval experiment runner.
Executes Lexical (BM25), Dense (Bi-Encoder), and Hybrid (RRF) retrieval,
evaluates scenario-grouped queries, and logs results to experiments.jsonl.

Usage:
    python scripts/run_retrieval_experiment.py [--config configs/week1_retrieval_config.yaml]
                                               [--method bm25|bm25_ngram|dense|hybrid|all]
                                               [--model-name intfloat/multilingual-e5-small]
                                               [--top-k 5]
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from src.retrieval.bm25 import BM25Index
from src.retrieval.dense import DenseRetriever
from src.retrieval.hybrid import HybridRetriever
from src.evaluation.metrics import (
    compute_reciprocal_rank,
    compute_recall_at_k,
    compute_precision_at_k,
    compute_ndcg_at_k
)
from src.evaluation.logger import ExperimentLogger, get_process_memory_mb


def load_provisions(provisions_path: Path, filter_quarantined: bool = True) -> List[Dict[str, Any]]:
    """Loads extracted provisions from JSONL."""
    if not provisions_path.exists():
        raise FileNotFoundError(f"Provisions file not found: {provisions_path}")

    provisions = []
    with open(provisions_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            p = json.loads(line)
            if filter_quarantined and p.get("is_quarantined", False):
                continue
            provisions.append(p)
    return provisions


def evaluate_query_set(retriever, queries: List[Dict[str, Any]], top_k: int = 5) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Evaluates a retriever instance over a list of queries with ground truth."""
    query_eval_records = []
    reciprocal_ranks = []
    recalls = []
    precisions = []
    ndcgs = []

    # Per-language metric tracking
    lang_mrrs: Dict[str, List[float]] = {}

    for q in queries:
        qid = q["query_id"]
        qtext = q["text"]
        qlang = q.get("language", "undetermined")
        expected = q.get("expected_provisions", [])

        t0 = time.perf_counter()
        results = retriever.search(qtext, top_k=top_k)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        retrieved_pids = [r.provision_id for r in results]

        rr = compute_reciprocal_rank(retrieved_pids, expected, k=top_k)
        recall = compute_recall_at_k(retrieved_pids, expected, k=top_k)
        precision = compute_precision_at_k(retrieved_pids, expected, k=top_k)
        ndcg = compute_ndcg_at_k(retrieved_pids, expected, k=top_k)

        reciprocal_ranks.append(rr)
        recalls.append(recall)
        precisions.append(precision)
        ndcgs.append(ndcg)

        lang_mrrs.setdefault(qlang, []).append(rr)

        query_eval_records.append({
            "query_id": qid,
            "scenario_id": q.get("scenario_id", ""),
            "language": qlang,
            "query_text": qtext,
            "latency_ms": latency_ms,
            "expected_provisions": expected,
            "retrieved_provisions": [r.to_dict() for r in results],
            "metrics": {
                "reciprocal_rank": round(rr, 4),
                "recall_at_k": round(recall, 4),
                "precision_at_k": round(precision, 4),
                "ndcg_at_k": round(ndcg, 4)
            }
        })

    num_q = max(len(queries), 1)
    overall_metrics = {
        "mean_reciprocal_rank": round(sum(reciprocal_ranks) / num_q, 4),
        "mean_recall_at_k": round(sum(recalls) / num_q, 4),
        "mean_precision_at_k": round(sum(precisions) / num_q, 4),
        "mean_ndcg_at_k": round(sum(ndcgs) / num_q, 4)
    }

    # Add per-language MRR
    for lang, mrrs in lang_mrrs.items():
        overall_metrics[f"mrr_{lang}"] = round(sum(mrrs) / len(mrrs), 4)

    return query_eval_records, overall_metrics


def run_single_method(method: str, cfg: Dict[str, Any], provisions: List[Dict[str, Any]],
                      queries: List[Dict[str, Any]], top_k: int, logger: ExperimentLogger,
                      dense_retriever_instance: Optional[DenseRetriever] = None) -> Dict[str, Any]:
    """Runs a single retrieval experiment condition and logs results."""
    print(f"\n=======================================================")
    print(f"  RUNNING RETRIEVAL EXPERIMENT: [{method.upper()}]")
    print(f"=======================================================")

    t_start = time.perf_counter()
    model_name = "none"
    retriever = None

    if method == "bm25":
        bm25_cfg = cfg.get("models", {}).get("bm25", {})
        k1 = bm25_cfg.get("k1", 1.5)
        b = bm25_cfg.get("b", 0.75)
        print(f"[*] Initializing BM25 (k1={k1}, b={b}, use_char_ngrams=False)...")
        bm25 = BM25Index(k1=k1, b=b, use_char_ngrams=False)
        bm25.fit(provisions)
        retriever = bm25
        model_name = "bm25_word_tokens"

    elif method == "bm25_ngram":
        bm25_cfg = cfg.get("models", {}).get("bm25_ngram", {})
        k1 = bm25_cfg.get("k1", 1.5)
        b = bm25_cfg.get("b", 0.75)
        n = bm25_cfg.get("ngram_n", 3)
        print(f"[*] Initializing BM25 Character N-grams (k1={k1}, b={b}, n={n})...")
        bm25_ngram = BM25Index(k1=k1, b=b, use_char_ngrams=True)
        bm25_ngram.fit(provisions)
        retriever = bm25_ngram
        model_name = f"bm25_char_{n}gram"

    elif method == "dense":
        dense_cfg = cfg.get("models", {}).get("dense", {})
        m_name = dense_cfg.get("model_name", "intfloat/multilingual-e5-small")
        if dense_retriever_instance:
            dense = dense_retriever_instance
        else:
            print(f"[*] Initializing Dense Retriever (Model: '{m_name}')...")
            dense = DenseRetriever(
                model_name=m_name,
                cache_dir=dense_cfg.get("cache_dir", "experiments/cache"),
                batch_size=dense_cfg.get("batch_size", 4),
                max_length=dense_cfg.get("max_length", 512),
                device="cpu"
            )
            dense.fit(provisions)
        retriever = dense
        model_name = dense.model_name

    elif method == "hybrid":
        # Build both BM25 and Dense
        bm25_cfg = cfg.get("models", {}).get("bm25", {})
        bm25 = BM25Index(k1=bm25_cfg.get("k1", 1.5), b=bm25_cfg.get("b", 0.75))
        bm25.fit(provisions)

        dense_cfg = cfg.get("models", {}).get("dense", {})
        if dense_retriever_instance:
            dense = dense_retriever_instance
        else:
            dense = DenseRetriever(
                model_name=dense_cfg.get("model_name", "intfloat/multilingual-e5-small"),
                cache_dir=dense_cfg.get("cache_dir", "experiments/cache")
            )
            dense.fit(provisions)

        hyb_cfg = cfg.get("models", {}).get("hybrid", {})
        retriever = HybridRetriever(
            bm25_index=bm25,
            dense_retriever=dense,
            k_rrf=hyb_cfg.get("k_rrf", 60),
            weight_bm25=hyb_cfg.get("weight_bm25", 1.0),
            weight_dense=hyb_cfg.get("weight_dense", 1.0)
        )
        model_name = f"hybrid_rrf_bm25_{dense.model_name}"

    else:
        raise ValueError(f"Unknown retrieval method: {method}")

    # Evaluate query set
    query_eval_records, overall_metrics = evaluate_query_set(retriever, queries, top_k=top_k)
    duration = time.perf_counter() - t_start

    # Log run
    exp_id = logger.log_run(
        experiment_name=f"week1_{method}",
        retrieval_method=method,
        model_name=model_name,
        corpus_manifest=cfg.get("corpus", {}).get("manifest_path", "data/manifests/processed_manifest.jsonl"),
        num_provisions=len(provisions),
        query_records=query_eval_records,
        config_params={"method": method, "top_k": top_k},
        overall_metrics=overall_metrics,
        total_duration_sec=duration
    )

    print(f"\n[+] Experiment Completed: {exp_id}")
    print(f"    - Execution Duration:   {duration:.2f} s")
    print(f"    - Overall MRR@{top_k}:         {overall_metrics['mean_reciprocal_rank']:.4f}")
    print(f"    - Overall Recall@{top_k}:      {overall_metrics['mean_recall_at_k']:.4f}")
    print(f"    - Overall nDCG@{top_k}:        {overall_metrics['mean_ndcg_at_k']:.4f}")
    if "mrr_bn" in overall_metrics:
        print(f"    - Bangla MRR:           {overall_metrics['mrr_bn']:.4f}")
    if "mrr_en" in overall_metrics:
        print(f"    - English MRR:          {overall_metrics['mrr_en']:.4f}")
    if "mrr_banglish" in overall_metrics:
        print(f"    - Banglish MRR:         {overall_metrics['mrr_banglish']:.4f}")

    return {
        "method": method,
        "experiment_id": exp_id,
        "metrics": overall_metrics,
        "duration_sec": round(duration, 2),
        "retriever": retriever
    }


def main():
    parser = argparse.ArgumentParser(description="Legal Aid BD: Retrieval Experiment Runner")
    parser.add_argument("--config", default="configs/week1_retrieval_config.yaml", help="Path to config YAML")
    parser.add_argument("--method", default="all",
                        choices=["bm25", "bm25_ngram", "bm25_char_ngram", "dense", "hybrid", "all"],
                        help="Retrieval method to evaluate")
    parser.add_argument("--model-name", default=None, help="Override dense model identifier")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to retrieve per query")

    args = parser.parse_args()

    # Normalize method alias
    if args.method == "bm25_char_ngram":
        args.method = "bm25_ngram"

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"[X] Error: Configuration file not found at {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if args.model_name:
        cfg.setdefault("models", {}).setdefault("dense", {})["model_name"] = args.model_name

    provisions_file = Path(cfg.get("corpus", {}).get("provisions_path", "data/processed/provisions.jsonl"))
    provisions = load_provisions(provisions_file, filter_quarantined=True)
    queries = cfg.get("evaluation_queries", [])

    print("=" * 70)
    print("  Legal Aid BD — Week 1 Retrieval Evaluation Suite")
    print("=" * 70)
    print(f"[*] Evaluatable Corpus Size: {len(provisions)} Provisions")
    print(f"[*] Benchmark Queries:        {len(queries)} Multilingual Queries")
    print(f"[*] Top-K Cutoff:            {args.top_k}")
    print(f"[*] Current Process RSS:     {get_process_memory_mb()} MB\n")

    logger = ExperimentLogger()
    methods_to_run = ["bm25", "bm25_ngram"] if args.method == "all" else [args.method]

    results = []
    dense_inst = None

    # If method is all, we run bm25, bm25_ngram, and if dense is requested or all, we run dense + hybrid
    if args.method == "all":
        methods_to_run = ["bm25", "bm25_ngram", "dense", "hybrid"]

    for m in methods_to_run:
        try:
            res = run_single_method(
                method=m,
                cfg=cfg,
                provisions=provisions,
                queries=queries,
                top_k=args.top_k,
                logger=logger,
                dense_retriever_instance=dense_inst
            )
            if m == "dense":
                dense_inst = res.get("retriever")
            results.append(res)
        except Exception as e:
            print(f"[!] Error executing method '{m}': {e}")
            logger.log_run(
                experiment_name=f"week1_{m}_failed",
                retrieval_method=m,
                model_name="error",
                corpus_manifest=str(provisions_file),
                num_provisions=len(provisions),
                query_records=[],
                config_params={"method": m},
                warnings=[f"Execution failed: {type(e).__name__}: {e}"]
            )

    # Print Comparative Matrix
    if len(results) > 1:
        print("\n" + "=" * 70)
        print("  COMPARATIVE RETRIEVAL EVALUATION MATRIX")
        print("=" * 70)
        print(f"{'Method':<16} | {'MRR@5':<8} | {'Recall@5':<10} | {'nDCG@5':<8} | {'Banglish MRR':<14} | {'Duration'}")
        print("-" * 70)
        for r in results:
            m = r["metrics"]
            b_mrr = m.get("mrr_banglish", "N/A")
            b_str = f"{b_mrr:.4f}" if isinstance(b_mrr, float) else str(b_mrr)
            print(f"{r['method']:<16} | {m['mean_reciprocal_rank']:<8.4f} | {m['mean_recall_at_k']:<10.4f} | {m['mean_ndcg_at_k']:<8.4f} | {b_str:<14} | {r['duration_sec']} s")
        print("=" * 70)


if __name__ == "__main__":
    main()
