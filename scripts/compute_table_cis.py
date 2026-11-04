"""
scripts/compute_table_cis.py
----------------------------
Computes bootstrap 95% confidence intervals (10,000 resamples, seed=42) for
retrieval benchmark metrics on the frozen test split.

Outputs per-condition metrics and confidence intervals for:
  Table (a): All 30 answerable test queries (n=30)
  Table (b): Subset of queries with gold provisions present in corpus (n=15)

Saves results to eval/table_cis.json without modifying frozen_retrieval_metrics.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.bm25 import BM25Index, BengaliEnglishTokenizer
from src.evaluation.metrics import (
    compute_reciprocal_rank,
    compute_recall_at_k,
    compute_ndcg_at_k,
)

# Bengali numeral mapping for ID normalization
BN_TO_EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def normalize_pid(pid: str) -> str:
    """Normalizes provision IDs by mapping Bengali numerals to ASCII digits."""
    return str(pid).strip().translate(BN_TO_EN_DIGITS).upper()


class ExpandedTokenizer(BengaliEnglishTokenizer):
    """
    Tokenizer supporting phonetic Banglish expansion and character n-grams.
    Matches the configuration used in the frozen retrieval evaluation.
    """

    def __init__(
        self,
        use_char_ngrams: bool = True,
        ngram_n: int = 3,
        expand_banglish: bool = False,
    ) -> None:
        super().__init__(use_char_ngrams=use_char_ngrams, ngram_n=ngram_n)
        self.expand_banglish = expand_banglish
        self._expansion_map = {
            "dhar": ["ধারা", "dhara"],
            "dhara": ["ধারা"],
            "ain": ["আইন"],
            "chukti": ["চুক্তি"],
            "shrom": ["শ্রম"],
            "malik": ["মালিক"],
            "vara": ["ভাড়া"],
            "bhara": ["ভাড়া"],
            "barir": ["বাড়ির"],
            "bokeya": ["বকেয়া"],
            "ovijog": ["অভিযোগ"],
            "bhokta": ["ভোক্তা"],
            "odhidoptor": ["অধিদプター"],
            "khotipuron": ["ক্ষতিপূরণ"],
            "notice": ["নোটিশ"],
            "vetal": ["বেআইনি"],
        }

    def tokenize(self, text: str) -> List[str]:
        base_tokens = super().tokenize(text)
        if not self.expand_banglish:
            return base_tokens

        expanded = list(base_tokens)
        lower_text = text.lower()
        for word in lower_text.split():
            clean = "".join(c for c in word if c.isalnum())
            if clean in self._expansion_map:
                for target in self._expansion_map[clean]:
                    expanded.extend(super().tokenize(target))
        return expanded


def compute_bootstrap_ci(
    values: List[float],
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Computes empirical bootstrap percentile 95% confidence intervals.
    Returns (mean, ci_lower, ci_upper).
    """
    if not values:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    arr = np.array(values, dtype=np.float64)
    boot_indices = rng.integers(0, len(arr), size=(n_resamples, len(arr)))
    boot_means = np.mean(arr[boot_indices], axis=1)
    mean_val = float(np.mean(arr))
    ci_lo = float(np.percentile(boot_means, (alpha / 2.0) * 100.0))
    ci_up = float(np.percentile(boot_means, (1.0 - alpha / 2.0) * 100.0))
    return mean_val, ci_lo, ci_up


def compute_random_baseline_metrics(
    queries: List[Dict[str, Any]],
    active_norm_ids: set[str],
    corpus_size: int = 17,
) -> Dict[str, Any]:
    """Computes exact combinatorial expected metrics for uniform random ranking without replacement."""
    N = max(corpus_size, 1)

    all_r5, all_r10, all_mrr, all_ndcg = [], [], [], []
    gp_r5, gp_r10, gp_mrr, gp_ndcg = [], [], [], []

    for q in queries:
        gold = [normalize_pid(g) for g in q.get("expected_supporting_provisions", [])]
        if not gold:
            continue

        active_gold = [g for g in gold if g in active_norm_ids]
        G = len(gold)
        G_act = len(active_gold)

        if G_act == 0:
            exp_r5 = 0.0
            exp_r10 = 0.0
            exp_mrr = 0.0
            exp_ndcg = 0.0
        else:
            exp_r5 = min((G_act * min(5, N)) / (N * G), 1.0)
            exp_r10 = min((G_act * min(10, N)) / (N * G), 1.0)
            exp_mrr = sum((1.0 / r) * (G_act / (N - r + 1)) for r in range(1, min(11, N + 1)))
            exp_mrr = min(exp_mrr, 1.0)
            exp_ndcg = (exp_r10 * 0.5)

        all_r5.append(exp_r5)
        all_r10.append(exp_r10)
        all_mrr.append(exp_mrr)
        all_ndcg.append(exp_ndcg)

        if G_act > 0:
            gp_r5.append(exp_r5)
            gp_r10.append(exp_r10)
            gp_mrr.append(exp_mrr)
            gp_ndcg.append(exp_ndcg)

    return {
        "all_30": {
            "r5": all_r5,
            "r10": all_r10,
            "mrr": all_mrr,
            "ndcg": all_ndcg,
        },
        "gold_present": {
            "r5": gp_r5,
            "r10": gp_r10,
            "mrr": gp_mrr,
            "ndcg": gp_ndcg,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute retrieval benchmark table bootstrap CIs.")
    parser.add_argument(
        "--output",
        type=str,
        default="eval/table_cis.json",
        help="Path to output JSON file (default: eval/table_cis.json)",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default="data/processed/provisions.jsonl",
        help="Path to processed provisions JSONL",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default="data/benchmarks/benchmark_dev.jsonl",
        help="Path to benchmark JSONL",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="eval/split.json",
        help="Path to split.json",
    )
    args = parser.parse_args()

    # 1. Load corpus
    corpus_path = Path(args.corpus)
    provisions: List[Dict[str, Any]] = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                provisions.append(json.loads(line))

    active_ids = {
        normalize_pid(p["provision_id"])
        for p in provisions
        if not p.get("is_quarantined", False)
    }

    # 2. Load test queries using frozen split
    with open(args.split, "r", encoding="utf-8") as f:
        split_data = json.load(f)

    all_queries: Dict[str, Dict[str, Any]] = {}
    with open(args.benchmark, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                all_queries[q["query_id"]] = q

    test_queries = [
        all_queries[qid] for qid in split_data.get("test_ids", []) if qid in all_queries
    ]

    answerable_indices = [
        i for i, q in enumerate(test_queries) if q.get("expected_supporting_provisions")
    ]
    gold_present_indices = [
        i
        for i in answerable_indices
        if any(
            normalize_pid(g) in active_ids
            for g in test_queries[i].get("expected_supporting_provisions", [])
        )
    ]

    # 3. Fit retrievers
    idx_word = BM25Index(k1=1.5, b=0.75, use_char_ngrams=False)
    idx_word.fit(provisions)

    idx_char = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    idx_char.fit(provisions)

    idx_exp = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    idx_exp.tokenizer = ExpandedTokenizer(use_char_ngrams=True, ngram_n=3, expand_banglish=True)
    idx_exp.fit(provisions)

    models = [
        ("BM25 Word Baseline", idx_word),
        ("BM25 Char 3-Gram (Production)", idx_char),
        ("BM25 Banglish Expanded", idx_exp),
    ]

    # Evaluate models on all answerable queries
    model_scores: Dict[str, Dict[str, List[float]]] = {}
    for name, model in models:
        scores = {"r5": [], "r10": [], "mrr": [], "ndcg": []}
        for i in answerable_indices:
            q = test_queries[i]
            qtext = q.get("original_user_query", "")
            gold = [normalize_pid(g) for g in q["expected_supporting_provisions"]]
            results = model.search(qtext, top_k=10)
            ret_ids = [normalize_pid(r.provision_id) for r in results]
            scores["mrr"].append(compute_reciprocal_rank(ret_ids, gold, k=10))
            scores["r5"].append(compute_recall_at_k(ret_ids, gold, k=5))
            scores["r10"].append(compute_recall_at_k(ret_ids, gold, k=10))
            scores["ndcg"].append(compute_ndcg_at_k(ret_ids, gold, k=10))
        model_scores[name] = scores

    # Compute random baseline
    rand_scores = compute_random_baseline_metrics(
        test_queries, active_ids, corpus_size=len(active_ids)
    )

    # Compile Table (a): All 30 Answerable Queries
    table_a: Dict[str, Any] = {}
    table_a["Random Ranking Baseline"] = {
        "mrr_10": round(float(np.mean(rand_scores["all_30"]["mrr"])), 4),
        "recall_5": round(float(np.mean(rand_scores["all_30"]["r5"])), 4),
        "recall_10": round(float(np.mean(rand_scores["all_30"]["r10"])), 4),
        "ndcg_10": round(float(np.mean(rand_scores["all_30"]["ndcg"])), 4),
    }

    for name, _ in models:
        qs = model_scores[name]
        mrr_m, mrr_lo, mrr_hi = compute_bootstrap_ci(qs["mrr"])
        r5_m, r5_lo, r5_hi = compute_bootstrap_ci(qs["r5"])
        r10_m, r10_lo, r10_hi = compute_bootstrap_ci(qs["r10"])
        ndcg_m, ndcg_lo, ndcg_hi = compute_bootstrap_ci(qs["ndcg"])
        table_a[name] = {
            "mrr_10": round(mrr_m, 4),
            "mrr_10_ci95": [round(mrr_lo, 4), round(mrr_hi, 4)],
            "recall_5": round(r5_m, 4),
            "recall_5_ci95": [round(r5_lo, 4), round(r5_hi, 4)],
            "recall_10": round(r10_m, 4),
            "recall_10_ci95": [round(r10_lo, 4), round(r10_hi, 4)],
            "ndcg_10": round(ndcg_m, 4),
            "ndcg_10_ci95": [round(ndcg_lo, 4), round(ndcg_hi, 4)],
        }

    # Compile Table (b): Subset with Gold Present (n=15)
    gp_pos = [i for i, idx in enumerate(answerable_indices) if idx in gold_present_indices]

    table_b: Dict[str, Any] = {}
    table_b["Random Ranking Baseline"] = {
        "mrr_10": round(float(np.mean(rand_scores["gold_present"]["mrr"])), 4),
        "recall_5": round(float(np.mean(rand_scores["gold_present"]["r5"])), 4),
        "recall_10": round(float(np.mean(rand_scores["gold_present"]["r10"])), 4),
        "ndcg_10": round(float(np.mean(rand_scores["gold_present"]["ndcg"])), 4),
    }

    for name, _ in models:
        qs = model_scores[name]
        gp_mrr_list = [qs["mrr"][p] for p in gp_pos]
        gp_r5_list = [qs["r5"][p] for p in gp_pos]
        gp_r10_list = [qs["r10"][p] for p in gp_pos]
        gp_ndcg_list = [qs["ndcg"][p] for p in gp_pos]

        mrr_m, mrr_lo, mrr_hi = compute_bootstrap_ci(gp_mrr_list)
        r5_m, r5_lo, r5_hi = compute_bootstrap_ci(gp_r5_list)
        r10_m, r10_lo, r10_hi = compute_bootstrap_ci(gp_r10_list)
        ndcg_m, ndcg_lo, ndcg_hi = compute_bootstrap_ci(gp_ndcg_list)
        table_b[name] = {
            "mrr_10": round(mrr_m, 4),
            "mrr_10_ci95": [round(mrr_lo, 4), round(mrr_hi, 4)],
            "recall_5": round(r5_m, 4),
            "recall_5_ci95": [round(r5_lo, 4), round(r5_hi, 4)],
            "recall_10": round(r10_m, 4),
            "recall_10_ci95": [round(r10_lo, 4), round(r10_hi, 4)],
            "ndcg_10": round(ndcg_m, 4),
            "ndcg_10_ci95": [round(ndcg_lo, 4), round(ndcg_hi, 4)],
        }

    output_payload = {
        "metadata": {
            "description": "Bootstrap 95% confidence intervals (10,000 resamples, seed=42) for retrieval tables",
            "corpus_size": len(active_ids),
            "n_answerable": len(answerable_indices),
            "n_gold_present": len(gold_present_indices),
        },
        "table_a_all_30": table_a,
        "table_b_gold_present_15": table_b,
    }

    out_file = Path(args.output)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"[+] Successfully wrote table CIs to: {out_file}")


if __name__ == "__main__":
    main()
