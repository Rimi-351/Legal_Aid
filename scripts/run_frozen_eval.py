"""
scripts/run_frozen_eval.py
--------------------------
Week 8 Retrieval Evaluation on Frozen Test Split with Paired Bootstrap CIs
and Holm-Bonferroni Multiple Testing Correction.

Features & Gates:
1. Manifest verification: Refuses to run if corpus or split SHA256 hashes differ.
2. Dual-set evaluation:
   (a) All 30 answerable test queries (n=30)
   (b) Queries with gold present in the active corpus (n=15)
3. Columns include Recall Ceiling and Queries with Gold Present count.
4. Theoretical Random Ranking Baseline row included in all metric tables.
5. Gold-ID normalization (Bengali numerals <-> ASCII digits) for faithful evaluation.
6. Three paired comparisons with 10,000 seeded bootstrap resamples:
   - Char_Ngram vs Word_Baseline
   - Banglish_Expanded vs Word_Baseline
   - Banglish_Expanded vs Char_Ngram (isolates expansion contribution)
7. Holm-Bonferroni step-down correction:
   - Reports raw and adjusted CIs and p-values.
   - Enforces strict rule: Superiority claim permitted ONLY if adjusted CI excludes 0.
8. Subgroup results (language, domain) with bootstrap CIs and exact n:
   - en (n=15), bn_unicode (n=11), banglish (n=4)
   - land_tenancy (n=11), employment_labour (n=8), consumer_protection (n=6), contractual_obligations (n=5)
9. Corpus size annotation beside every latency and RAM measurement: (N=17 provisions).
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import time
import math
import hashlib
import argparse
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.bm25 import BM25Index, BengaliEnglishTokenizer
from src.evaluation.metrics import (
    compute_reciprocal_rank,
    compute_recall_at_k,
    compute_ndcg_at_k,
)
from src.evaluation.logger import get_process_memory_mb
from src.rag.config import settings

BENGALI_TO_ASCII_TRANS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
ASCII_TO_BENGALI_TRANS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def normalize_pid(pid: str) -> str:
    """Normalizes Bengali Unicode numerals to ASCII digits, strips whitespace, and uppercases."""
    if not pid:
        return ""
    return pid.strip().translate(BENGALI_TO_ASCII_TRANS).upper()


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
    "borkhasto": ["বরখাস্ত", "dismissal", "termination"],
    "chakri": ["চাকরি", "employment"],
    "ovijog": ["অভিযোগ", "complaint"],
    "bedokhol": ["বেদখল", "eviction", "dispossession"],
    "notice": ["নোটিশ", "notice"]
}


class ExpandedTokenizer(BengaliEnglishTokenizer):
    def __init__(self, use_char_ngrams: bool = False, ngram_n: int = 3, expand_banglish: bool = False):
        super().__init__(use_char_ngrams=use_char_ngrams, ngram_n=ngram_n)
        self.expand_banglish = expand_banglish

    def tokenize(self, text: str) -> List[str]:
        tokens = super().tokenize(text)
        if self.expand_banglish:
            expanded = list(tokens)
            for t in tokens:
                if t in BANGLISH_LEGAL_EXPANSION:
                    expanded.extend(BANGLISH_LEGAL_EXPANSION[t])
            return expanded
        return tokens


def check_git_status() -> Tuple[bool, List[str]]:
    """Checks git working tree status and returns (is_dirty, uncommitted_paths)."""
    import subprocess
    try:
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip()]
        paths = [l[2:].strip() for l in lines]
        return len(paths) > 0, paths
    except Exception as e:
        return False, [str(e)]


def verify_freeze_manifest(
    manifest_path: Path = Path("eval/freeze_manifest.json"),
    allow_dirty: bool = False
) -> None:
    """Refuses execution if corpus/split hashes differ or if working tree is dirty without --allow-dirty."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Freeze manifest not found: {manifest_path}")

    # Check git dirty gate
    is_dirty, uncommitted = check_git_status()
    if is_dirty and not allow_dirty:
        raise RuntimeError(
            f"REFUSING EVALUATION: Git working tree is dirty ({len(uncommitted)} uncommitted files)!\n"
            f"Refusing to evaluate against uncommitted/unverified code.\n"
            f"Commit changes or pass --allow-dirty to override and record this state."
        )
    elif is_dirty and allow_dirty:
        print(f"[!] WARNING: Evaluation proceeding with dirty working tree (--allow-dirty set, {len(uncommitted)} uncommitted paths).")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    hashes = manifest.get("hashes", {})
    corpus_p = Path(hashes.get("corpus_path", "data/processed/provisions.jsonl"))
    split_p = Path(hashes.get("split_path", "eval/split.json"))

    if not corpus_p.exists():
        raise FileNotFoundError(f"Corpus file not found: {corpus_p}")
    if not split_p.exists():
        raise FileNotFoundError(f"Split file not found: {split_p}")

    actual_corpus_hash = hashlib.sha256(corpus_p.read_bytes()).hexdigest()
    actual_split_hash = hashlib.sha256(split_p.read_bytes()).hexdigest()

    expected_corpus_hash = hashes.get("corpus_sha256")
    expected_split_hash = hashes.get("split_sha256")

    if actual_corpus_hash != expected_corpus_hash:
        raise RuntimeError(
            f"REFUSING EVALUATION: Corpus hash mismatch!\n"
            f"Expected: {expected_corpus_hash}\nActual:   {actual_corpus_hash}"
        )
    if actual_split_hash != expected_split_hash:
        raise RuntimeError(
            f"REFUSING EVALUATION: Split hash mismatch!\n"
            f"Expected: {expected_split_hash}\nActual:   {actual_split_hash}"
        )

    print("[+] Freeze manifest integrity verified. Hash checks PASSED.")


def load_corpus(path: Path = Path("data/processed/provisions.jsonl")) -> List[Dict[str, Any]]:
    provisions = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                if not p.get("is_quarantined", False):
                    provisions.append(p)
    return provisions


def load_test_queries(
    benchmark_path: Path = Path("data/benchmarks/benchmark_dev.jsonl"),
    split_path: Path = Path("eval/split.json")
) -> List[Dict[str, Any]]:
    with open(split_path, "r", encoding="utf-8") as f:
        split_data = json.load(f)

    all_queries = {}
    with open(benchmark_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                all_queries[q["query_id"]] = q

    test_queries = [all_queries[qid] for qid in split_data.get("test_ids", []) if qid in all_queries]
    return test_queries


def run_paired_bootstrap(
    baseline_scores: List[float],
    candidate_scores: List[float],
    n_resamples: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Computes paired bootstrap difference, 95% Confidence Interval, and empirical two-sided p-value.
    Returns dict containing mean_delta, ci_lower, ci_upper, raw_p_value, and boot_means.
    """
    assert len(baseline_scores) == len(candidate_scores), "Score lists must be paired."
    diffs = np.array(candidate_scores) - np.array(baseline_scores)
    n = len(diffs)
    mean_delta = float(np.mean(diffs))

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_resamples)

    for i in range(n_resamples):
        sample_indices = rng.integers(0, n, size=n)
        boot_means[i] = np.mean(diffs[sample_indices])

    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    # Empirical two-sided p-value via percentile inversion
    p_pos = np.mean(boot_means <= 0.0)
    p_neg = np.mean(boot_means >= 0.0)
    raw_p = float(min(1.0, 2.0 * min(p_pos, p_neg)))
    if raw_p == 0.0:
        raw_p = 1.0 / n_resamples

    is_significant = (ci_lower > 0.0) or (ci_upper < 0.0)

    return {
        "mean_delta": round(mean_delta, 4),
        "raw_ci": [round(ci_lower, 4), round(ci_upper, 4)],
        "raw_p_value": round(raw_p, 4),
        "significant": is_significant,
        "boot_means": boot_means,
    }


def compute_bootstrap_ci(
    values: List[float],
    n_resamples: int = 10000,
    seed: int = 42,
    alpha: float = 0.05
) -> Tuple[float, float, float]:
    """Computes sample mean and (1 - alpha) bootstrap CI for a list of metric values."""
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    mean_val = float(np.mean(values))
    if n == 1 or np.all(np.array(values) == values[0]):
        return mean_val, mean_val, mean_val

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_resamples)
    for i in range(n_resamples):
        sample_indices = rng.integers(0, n, size=n)
        boot_means[i] = np.mean([values[idx] for idx in sample_indices])

    ci_lo = float(np.percentile(boot_means, (alpha / 2.0) * 100.0))
    ci_up = float(np.percentile(boot_means, (1.0 - alpha / 2.0) * 100.0))
    return mean_val, ci_lo, ci_up


def holm_bonferroni_correction(
    tests: List[Dict[str, Any]],
    alpha: float = 0.05
) -> List[Dict[str, Any]]:
    """
    Applies Holm-Bonferroni step-down correction across multiple comparison tests.
    Sorts tests ascending by raw_p_value, evaluates step-down thresholds alpha / (m - k + 1),
    computes monotonic adjusted p-values, and calculates Holm-adjusted confidence intervals.
    """
    m = len(tests)
    if m == 0:
        return []

    sorted_indices = sorted(range(m), key=lambda i: tests[i]["raw_p_value"])

    cum_max_p = 0.0
    adjusted_results = [None] * m

    for rank, idx in enumerate(sorted_indices):
        k = rank + 1  # 1-indexed
        multiplier = m - k + 1
        step_alpha = alpha / multiplier

        t = tests[idx]
        raw_p = t["raw_p_value"]
        adj_p = min(1.0, max(cum_max_p, raw_p * multiplier))
        cum_max_p = adj_p

        # Compute Holm-adjusted CI using step_alpha
        boot_means = t.get("boot_means")
        if boot_means is not None and len(boot_means) > 0:
            pct_lo = (step_alpha / 2.0) * 100.0
            pct_up = (1.0 - step_alpha / 2.0) * 100.0
            adj_ci = [
                float(np.percentile(boot_means, pct_lo)),
                float(np.percentile(boot_means, pct_up)),
            ]
        else:
            adj_ci = t.get("raw_ci", [0.0, 0.0])

        is_sig_after_holm = (adj_p < alpha) and (adj_ci[0] > 0.0 or adj_ci[1] < 0.0)

        res_entry = dict(t)
        res_entry.update({
            "rank": k,
            "multiplier": multiplier,
            "step_alpha": round(step_alpha, 6),
            "adj_p_value": round(adj_p, 4),
            "adj_ci": [round(adj_ci[0], 4), round(adj_ci[1], 4)],
            "significant_after_holm": is_sig_after_holm,
        })
        adjusted_results[idx] = res_entry

    return adjusted_results


def compute_random_baseline_metrics(
    queries: List[Dict[str, Any]],
    active_corpus_normalized_ids: Set[str],
    corpus_size: int = 17,
) -> Dict[str, Any]:
    """
    Computes exact closed-form analytical expected scores for a random ranking baseline
    over an active corpus of size N=17.
    """
    harmonic_10 = sum(1.0 / r for r in range(1, 11))
    dcg_sum_10 = sum(1.0 / math.log2(r + 1) for r in range(1, 11))
    total_pairs = (corpus_size * (corpus_size - 1)) / 2.0

    r5_list, r10_list, mrr10_list, ndcg10_list = [], [], [], []
    per_language: Dict[str, Dict[str, List[float]]] = {}
    per_domain: Dict[str, Dict[str, List[float]]] = {}

    for q in queries:
        gold = [normalize_pid(g) for g in q.get("expected_supporting_provisions", [])]
        gold_count = len(gold)
        lang = q.get("language_and_script", "unknown")
        domain = q.get("legal_domain", "unknown")

        if gold_count == 0:
            r5_list.append(0.0)
            r10_list.append(0.0)
            mrr10_list.append(0.0)
            ndcg10_list.append(0.0)
            continue

        present_count = len([g for g in gold if g in active_corpus_normalized_ids])
        if present_count == 0:
            r5, r10, mrr, ndcg = 0.0, 0.0, 0.0, 0.0
        else:
            r5 = (5.0 / corpus_size) * (present_count / gold_count)
            r10 = (10.0 / corpus_size) * (present_count / gold_count)
            if present_count == 1:
                mrr = (1.0 / corpus_size) * harmonic_10
                idcg = sum(1.0 / math.log2(i + 2) for i in range(min(gold_count, 10)))
                ndcg = ((1.0 / corpus_size) * dcg_sum_10) / idcg if idcg > 0 else 0.0
            elif present_count == 2:
                mrr = sum((1.0 / r) * ((corpus_size - r) / total_pairs) for r in range(1, 11))
                idcg = sum(1.0 / math.log2(i + 2) for i in range(min(gold_count, 10)))
                ndcg = ((2.0 / corpus_size) * dcg_sum_10) / idcg if idcg > 0 else 0.0
            else:
                mrr = (present_count / corpus_size) * harmonic_10
                idcg = sum(1.0 / math.log2(i + 2) for i in range(min(gold_count, 10)))
                ndcg = ((present_count / corpus_size) * dcg_sum_10) / idcg if idcg > 0 else 0.0

        r5_list.append(r5)
        r10_list.append(r10)
        mrr10_list.append(mrr)
        ndcg10_list.append(ndcg)

        l_dict = per_language.setdefault(lang, {"r5": [], "r10": [], "mrr": [], "ndcg": []})
        l_dict["r5"].append(r5)
        l_dict["r10"].append(r10)
        l_dict["mrr"].append(mrr)
        l_dict["ndcg"].append(ndcg)

        d_dict = per_domain.setdefault(domain, {"r5": [], "r10": [], "mrr": [], "ndcg": []})
        d_dict["r5"].append(r5)
        d_dict["r10"].append(r10)
        d_dict["mrr"].append(mrr)
        d_dict["ndcg"].append(ndcg)

    answerable_indices = [i for i, q in enumerate(queries) if q.get("expected_supporting_provisions")]
    ans_r5 = [r5_list[i] for i in answerable_indices]
    ans_r10 = [r10_list[i] for i in answerable_indices]
    ans_mrr = [mrr10_list[i] for i in answerable_indices]
    ans_ndcg = [ndcg10_list[i] for i in answerable_indices]
    n_ans = max(len(answerable_indices), 1)

    gold_present_indices = [
        i for i in answerable_indices
        if any(normalize_pid(g) in active_corpus_normalized_ids for g in queries[i].get("expected_supporting_provisions", []))
    ]
    gp_r5 = [r5_list[i] for i in gold_present_indices]
    gp_r10 = [r10_list[i] for i in gold_present_indices]
    gp_mrr = [mrr10_list[i] for i in gold_present_indices]
    gp_ndcg = [ndcg10_list[i] for i in gold_present_indices]
    n_gp = max(len(gold_present_indices), 1)

    return {
        "name": "Random_Ranking_Baseline",
        "total_queries": len(queries),
        "answerable_queries": len(answerable_indices),
        "gold_present_queries": len(gold_present_indices),
        "overall_all_30": {
            "recall_at_5": round(sum(ans_r5) / n_ans, 4),
            "recall_at_10": round(sum(ans_r10) / n_ans, 4),
            "mrr_at_10": round(sum(ans_mrr) / n_ans, 4),
            "ndcg_at_10": round(sum(ans_ndcg) / n_ans, 4),
            "avg_latency_ms": 0.0,
            "peak_rss_mb": 0.0,
        },
        "overall_gold_present": {
            "recall_at_5": round(sum(gp_r5) / n_gp, 4),
            "recall_at_10": round(sum(gp_r10) / n_gp, 4),
            "mrr_at_10": round(sum(gp_mrr) / n_gp, 4),
            "ndcg_at_10": round(sum(gp_ndcg) / n_gp, 4),
            "avg_latency_ms": 0.0,
            "peak_rss_mb": 0.0,
        },
        "query_scores": {
            "r5": ans_r5,
            "r10": ans_r10,
            "mrr": ans_mrr,
            "ndcg": ans_ndcg,
        },
        "per_language": {
            l: {
                "count": len(vals["mrr"]),
                "recall_at_5": compute_bootstrap_ci(vals["r5"]),
                "recall_at_10": compute_bootstrap_ci(vals["r10"]),
                "mrr_at_10": compute_bootstrap_ci(vals["mrr"]),
                "ndcg_at_10": compute_bootstrap_ci(vals["ndcg"]),
            }
            for l, vals in per_language.items()
        },
        "per_domain": {
            d: {
                "count": len(vals["mrr"]),
                "recall_at_5": compute_bootstrap_ci(vals["r5"]),
                "recall_at_10": compute_bootstrap_ci(vals["r10"]),
                "mrr_at_10": compute_bootstrap_ci(vals["mrr"]),
                "ndcg_at_10": compute_bootstrap_ci(vals["ndcg"]),
            }
            for d, vals in per_domain.items()
        },
    }


def evaluate_condition(
    name: str,
    retriever: Any,
    queries: List[Dict[str, Any]],
    active_corpus_normalized_ids: Set[str],
) -> Dict[str, Any]:
    """Evaluates a retriever condition across queries with gold normalization and dual-set tracking."""
    r5_list = []
    r10_list = []
    mrr10_list = []
    ndcg10_list = []
    latencies = []

    per_language: Dict[str, Dict[str, List[float]]] = {}
    per_domain: Dict[str, Dict[str, List[float]]] = {}

    for q in queries:
        raw_gold = q.get("expected_supporting_provisions", [])
        norm_gold = set(normalize_pid(g) for g in raw_gold)
        qtext = q.get("original_user_query", "")
        lang = q.get("language_and_script", "unknown")
        domain = q.get("legal_domain", "unknown")

        t0 = time.perf_counter()
        results = retriever.search(qtext, top_k=10)
        lat = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat)

        norm_retrieved = [normalize_pid(r.provision_id) for r in results]

        if norm_gold:
            r5 = compute_recall_at_k(norm_retrieved, norm_gold, k=5)
            r10 = compute_recall_at_k(norm_retrieved, norm_gold, k=10)
            mrr = compute_reciprocal_rank(norm_retrieved, norm_gold, k=10)
            ndcg = compute_ndcg_at_k(norm_retrieved, norm_gold, k=10)
        else:
            r5 = 0.0
            r10 = 0.0
            mrr = 0.0
            ndcg = 0.0

        r5_list.append(r5)
        r10_list.append(r10)
        mrr10_list.append(mrr)
        ndcg10_list.append(ndcg)

        if norm_gold:
            l_dict = per_language.setdefault(lang, {"r5": [], "r10": [], "mrr": [], "ndcg": []})
            l_dict["r5"].append(r5)
            l_dict["r10"].append(r10)
            l_dict["mrr"].append(mrr)
            l_dict["ndcg"].append(ndcg)

            d_dict = per_domain.setdefault(domain, {"r5": [], "r10": [], "mrr": [], "ndcg": []})
            d_dict["r5"].append(r5)
            d_dict["r10"].append(r10)
            d_dict["mrr"].append(mrr)
            d_dict["ndcg"].append(ndcg)

    answerable_indices = [i for i, q in enumerate(queries) if q.get("expected_supporting_provisions")]
    ans_r5 = [r5_list[i] for i in answerable_indices]
    ans_r10 = [r10_list[i] for i in answerable_indices]
    ans_mrr = [mrr10_list[i] for i in answerable_indices]
    ans_ndcg = [ndcg10_list[i] for i in answerable_indices]
    n_ans = max(len(answerable_indices), 1)

    gold_present_indices = [
        i for i in answerable_indices
        if any(normalize_pid(g) in active_corpus_normalized_ids for g in queries[i].get("expected_supporting_provisions", []))
    ]
    gp_r5 = [r5_list[i] for i in gold_present_indices]
    gp_r10 = [r10_list[i] for i in gold_present_indices]
    gp_mrr = [mrr10_list[i] for i in gold_present_indices]
    gp_ndcg = [ndcg10_list[i] for i in gold_present_indices]
    n_gp = max(len(gold_present_indices), 1)

    return {
        "name": name,
        "total_queries": len(queries),
        "answerable_queries": len(answerable_indices),
        "gold_present_queries": len(gold_present_indices),
        "overall_all_30": {
            "recall_at_5": round(sum(ans_r5) / n_ans, 4),
            "recall_at_10": round(sum(ans_r10) / n_ans, 4),
            "mrr_at_10": round(sum(ans_mrr) / n_ans, 4),
            "ndcg_at_10": round(sum(ans_ndcg) / n_ans, 4),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "peak_rss_mb": get_process_memory_mb(),
        },
        "overall_gold_present": {
            "recall_at_5": round(sum(gp_r5) / n_gp, 4),
            "recall_at_10": round(sum(gp_r10) / n_gp, 4),
            "mrr_at_10": round(sum(gp_mrr) / n_gp, 4),
            "ndcg_at_10": round(sum(gp_ndcg) / n_gp, 4),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "peak_rss_mb": get_process_memory_mb(),
        },
        "query_scores": {
            "r5": ans_r5,
            "r10": ans_r10,
            "mrr": ans_mrr,
            "ndcg": ans_ndcg,
        },
        "per_language": {
            l: {
                "count": len(vals["mrr"]),
                "recall_at_5": compute_bootstrap_ci(vals["r5"]),
                "recall_at_10": compute_bootstrap_ci(vals["r10"]),
                "mrr_at_10": compute_bootstrap_ci(vals["mrr"]),
                "ndcg_at_10": compute_bootstrap_ci(vals["ndcg"]),
            }
            for l, vals in per_language.items()
        },
        "per_domain": {
            d: {
                "count": len(vals["mrr"]),
                "recall_at_5": compute_bootstrap_ci(vals["r5"]),
                "recall_at_10": compute_bootstrap_ci(vals["r10"]),
                "mrr_at_10": compute_bootstrap_ci(vals["mrr"]),
                "ndcg_at_10": compute_bootstrap_ci(vals["ndcg"]),
            }
            for d, vals in per_domain.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Week 8 Frozen Test Retrieval Evaluation.")
    parser.add_argument("--manifest", type=Path, default=Path("eval/freeze_manifest.json"))
    parser.add_argument("--allow-dirty", action="store_true", help="Allow running evaluation on a dirty working tree and record flag.")
    args = parser.parse_args()

    # Step 1: Verify Manifest Integrity and Dirty Gate
    verify_freeze_manifest(args.manifest, allow_dirty=args.allow_dirty)

    # Step 2: Load Corpus and Test Split
    provisions = load_corpus()
    corpus_size = len(provisions)  # 17
    active_corpus_norm_ids = {normalize_pid(p["provision_id"]) for p in provisions}

    test_queries = load_test_queries()
    answerable_queries = [q for q in test_queries if q.get("expected_supporting_provisions")]
    n_ans = len(answerable_queries)  # 30

    gold_present_queries = [
        q for q in answerable_queries
        if any(normalize_pid(g) in active_corpus_norm_ids for g in q.get("expected_supporting_provisions", []))
    ]
    n_gp = len(gold_present_queries)  # 15

    # Calculate recall ceilings
    max_recalls_all = [
        min(len([g for g in q["expected_supporting_provisions"] if normalize_pid(g) in active_corpus_norm_ids]), 10) / len(q["expected_supporting_provisions"])
        for q in answerable_queries
    ]
    ceiling_all = sum(max_recalls_all) / n_ans if n_ans > 0 else 0.0

    max_recalls_gp = [
        min(len([g for g in q["expected_supporting_provisions"] if normalize_pid(g) in active_corpus_norm_ids]), 10) / len(q["expected_supporting_provisions"])
        for q in gold_present_queries
    ]
    ceiling_gp = sum(max_recalls_gp) / n_gp if n_gp > 0 else 0.0

    print(f"[*] Loaded {corpus_size} active corpus provisions.")
    print(f"[*] Loaded {len(test_queries)} frozen test split queries ({n_ans} answerable).")
    print(f"[*] Queries with at least one gold provision in corpus: {n_gp}/{n_ans} ({n_gp/n_ans*100:.1f}%).")
    print(f"[*] Recall Ceiling (max achievable R@10): All={ceiling_all*100:.2f}%, Gold-Present={ceiling_gp*100:.2f}%.")

    # Baseline 0: Random Ranking Baseline
    res_rand = compute_random_baseline_metrics(test_queries, active_corpus_norm_ids, corpus_size=corpus_size)

    # Condition 1: Baseline Standard Word BM25
    idx_word_bm25 = BM25Index(k1=1.5, b=0.75, use_char_ngrams=False)
    idx_word_bm25.fit(provisions)

    # Condition 2: Production Char-n-gram BM25
    idx_char_bm25 = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    idx_char_bm25.fit(provisions)

    # Condition 3: Banglish-Expanded Lexical BM25
    idx_expanded_bm25 = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    idx_expanded_bm25.tokenizer = ExpandedTokenizer(use_char_ngrams=True, ngram_n=3, expand_banglish=True)
    idx_expanded_bm25.fit(provisions)

    # Run evaluations
    res_word = evaluate_condition("BM25_Word_Baseline", idx_word_bm25, test_queries, active_corpus_norm_ids)
    res_char = evaluate_condition("BM25_Char_Ngram (Production)", idx_char_bm25, test_queries, active_corpus_norm_ids)
    res_exp = evaluate_condition("BM25_Banglish_Expanded", idx_expanded_bm25, test_queries, active_corpus_norm_ids)

    all_res = [res_rand, res_word, res_char, res_exp]

    # =========================================================================
    # TABLE (A): All 30 Answerable Queries
    # =========================================================================
    print("\n" + "=" * 115)
    print("  Table (a): Retrieval Performance on All 30 Answerable Test Queries (n=30)")
    print("=" * 115)
    print(f"{'Condition':<28} | {'Recall@5':<9} | {'Recall@10':<10} | {'MRR@10':<7} | {'nDCG@10':<8} | {'Ceiling':<8} | {'Gold Present':<13} | {'Latency (N=17)':<15} | {'Peak RSS (N=17)'}")
    print("-" * 115)
    for r in all_res:
        ov = r["overall_all_30"]
        lat_str = f"{ov['avg_latency_ms']:.2f} ms" if ov['avg_latency_ms'] > 0 else "0.00 ms"
        rss_str = f"{ov['peak_rss_mb']:.1f} MB" if ov['peak_rss_mb'] > 0 else "0.0 MB"
        ceil_str = f"{ceiling_all*100:.1f}%"
        gp_str = f"{n_gp}/{n_ans} ({n_gp/n_ans*100:.0f}%)"
        print(f"{r['name']:<28} | {ov['recall_at_5']:<9.4f} | {ov['recall_at_10']:<10.4f} | {ov['mrr_at_10']:<7.4f} | {ov['ndcg_at_10']:<8.4f} | {ceil_str:<8} | {gp_str:<13} | {lat_str:<15} | {rss_str}")
    print("=" * 115)

    # =========================================================================
    # TABLE (B): Subset with Gold Present in Corpus (n=15)
    # =========================================================================
    print("\n" + "=" * 115)
    print(f"  Table (b): Retrieval Performance on Queries with Gold Present in Corpus (n={n_gp})")
    print("=" * 115)
    print(f"{'Condition':<28} | {'Recall@5':<9} | {'Recall@10':<10} | {'MRR@10':<7} | {'nDCG@10':<8} | {'Ceiling':<8} | {'Gold Present':<13} | {'Latency (N=17)':<15} | {'Peak RSS (N=17)'}")
    print("-" * 115)
    for r in all_res:
        ov = r["overall_gold_present"]
        lat_str = f"{ov['avg_latency_ms']:.2f} ms" if ov['avg_latency_ms'] > 0 else "0.00 ms"
        rss_str = f"{ov['peak_rss_mb']:.1f} MB" if ov['peak_rss_mb'] > 0 else "0.0 MB"
        ceil_str = f"{ceiling_gp*100:.1f}%"
        gp_str = f"{n_gp}/{n_gp} (100%)"
        print(f"{r['name']:<28} | {ov['recall_at_5']:<9.4f} | {ov['recall_at_10']:<10.4f} | {ov['mrr_at_10']:<7.4f} | {ov['ndcg_at_10']:<8.4f} | {ceil_str:<8} | {gp_str:<13} | {lat_str:<15} | {rss_str}")
    print("=" * 115)

    # =========================================================================
    # Paired Bootstrap Comparisons & Holm-Bonferroni Correction
    # =========================================================================
    print("\n" + "=" * 115)
    print("  Paired Bootstrap Statistical Comparisons & Holm-Bonferroni Correction (10,000 resamples, seeded)")
    print("  Three comparisons: (1) Char vs Word, (2) Banglish_Expanded vs Word, (3) Banglish_Expanded vs Char")
    print("=" * 115)

    comparison_pairs = [
        ("Char_Ngram vs Word_Baseline", res_char, res_word),
        ("Banglish_Expanded vs Word_Baseline", res_exp, res_word),
        ("Banglish_Expanded vs Char_Ngram", res_exp, res_char),  # Isolates Banglish expansion
    ]

    # Collect raw bootstrap tests across comparisons
    raw_tests_by_metric: Dict[str, List[Dict[str, Any]]] = {
        "mrr": [],
        "ndcg": [],
        "r5": [],
        "r10": [],
    }

    for comp_name, cand, base in comparison_pairs:
        for metric_name in ["mrr", "ndcg", "r5", "r10"]:
            b_vals = base["query_scores"][metric_name]
            c_vals = cand["query_scores"][metric_name]
            boot_res = run_paired_bootstrap(b_vals, c_vals, n_resamples=10000, seed=42)

            raw_tests_by_metric[metric_name].append({
                "comparison": comp_name,
                "candidate": cand["name"],
                "baseline": base["name"],
                "metric": metric_name,
                **boot_res,
            })

    # Apply Holm correction across the 3 comparisons per metric
    holm_results_by_metric: Dict[str, List[Dict[str, Any]]] = {}
    for metric_name, tests in raw_tests_by_metric.items():
        holm_results_by_metric[metric_name] = holm_bonferroni_correction(tests, alpha=0.05)

    for metric_name in ["mrr", "ndcg", "r5", "r10"]:
        print(f"\n[*] Metric: {metric_name.upper()}@10 (m=3 comparisons, Holm step-down correction):")
        print(f"  {'Comparison':<36} | {'Delta':<8} | {'Raw 95% CI':<19} | {'Raw p':<7} | {'Holm CI':<19} | {'Adj p':<7} | {'Claim Status'}")
        print("  " + "-" * 113)

        for res in holm_results_by_metric[metric_name]:
            c_name = res["comparison"]
            delta = res["mean_delta"]
            raw_ci = f"[{res['raw_ci'][0]:+.4f}, {res['raw_ci'][1]:+.4f}]"
            raw_p = f"{res['raw_p_value']:.4f}"
            adj_ci = f"[{res['adj_ci'][0]:+.4f}, {res['adj_ci'][1]:+.4f}]"
            adj_p = f"{res['adj_p_value']:.4f}"

            if res["significant_after_holm"] and res["adj_ci"][0] > 0.0:
                claim = "SUPERIORITY SUPPORTED (p_adj < 0.05, CI > 0)"
            else:
                claim = "NO SUPERIORITY CLAIM (Holm CI includes 0)"

            print(f"  {c_name:<36} | {delta:<+8.4f} | {raw_ci:<19} | {raw_p:<7} | {adj_ci:<19} | {adj_p:<7} | {claim}")

    # =========================================================================
    # Subgroup Performance by Language Modality (with explicit n and CIs)
    # =========================================================================
    print("\n" + "=" * 115)
    print("  Subgroup Performance by Language Modality (Sample sizes: en n=15, bn_unicode n=11, banglish n=4)")
    print("=" * 115)
    for r in all_res:
        print(f"\nCondition: {r['name']}")
        print(f"  {'Language':<18} | {'Count':<6} | {'Recall@5 (95% CI)':<26} | {'Recall@10 (95% CI)':<26} | {'MRR@10 (95% CI)'}")
        print("  " + "-" * 95)
        for l, m in r["per_language"].items():
            r5_str = f"{m['recall_at_5'][0]:.4f} [{m['recall_at_5'][1]:.4f}, {m['recall_at_5'][2]:.4f}]"
            r10_str = f"{m['recall_at_10'][0]:.4f} [{m['recall_at_10'][1]:.4f}, {m['recall_at_10'][2]:.4f}]"
            mrr_str = f"{m['mrr_at_10'][0]:.4f} [{m['mrr_at_10'][1]:.4f}, {m['mrr_at_10'][2]:.4f}]"
            label = f"{l} (n={m['count']})"
            print(f"  {label:<18} | {m['count']:<6} | {r5_str:<26} | {r10_str:<26} | {mrr_str}")

    print("\n  [!] CRITICAL NOTE ON BANGLISH SUBGROUP:")
    print("      Banglish subgroup has n=4 queries. With small sample size n=4, bootstrap confidence")
    print("      intervals are wide (e.g. [0.0000, 0.7500]). No generalized superiority claim across")
    print("      Banglish query performance is statistically valid or supported from n=4 queries.")

    # =========================================================================
    # Subgroup Performance by Legal Domain (with explicit n and CIs)
    # =========================================================================
    print("\n" + "=" * 115)
    print("  Subgroup Performance by Legal Domain (land n=11, labour n=8, consumer n=6, contract n=5)")
    print("=" * 115)
    for r in all_res:
        print(f"\nCondition: {r['name']}")
        print(f"  {'Domain':<30} | {'Count':<6} | {'Recall@5 (95% CI)':<26} | {'Recall@10 (95% CI)':<26} | {'MRR@10 (95% CI)'}")
        print("  " + "-" * 105)
        for d, m in r["per_domain"].items():
            r5_str = f"{m['recall_at_5'][0]:.4f} [{m['recall_at_5'][1]:.4f}, {m['recall_at_5'][2]:.4f}]"
            r10_str = f"{m['recall_at_10'][0]:.4f} [{m['recall_at_10'][1]:.4f}, {m['recall_at_10'][2]:.4f}]"
            mrr_str = f"{m['mrr_at_10'][0]:.4f} [{m['mrr_at_10'][1]:.4f}, {m['mrr_at_10'][2]:.4f}]"
            label = f"{d} (n={m['count']})"
            print(f"  {label:<30} | {m['count']:<6} | {r5_str:<26} | {r10_str:<26} | {mrr_str}")

    # Step 8: Save structured metrics summary
    out_path = Path("eval/frozen_retrieval_metrics.json")
    is_dirty, uncommitted = check_git_status()
    save_data = {
        "metadata": {
            "git_dirty": is_dirty,
            "allow_dirty": args.allow_dirty,
            "uncommitted_paths": uncommitted if is_dirty else [],
            "corpus_size": corpus_size,
            "corpus_size_annotation": f"(N={corpus_size} provisions)",
            "total_answerable_test_queries": n_ans,
            "queries_with_gold_in_corpus": n_gp,
            "fraction_gold_present": round(n_gp / n_ans, 4),
            "recall_ceiling_all_30": round(ceiling_all, 4),
            "recall_ceiling_gold_present": round(ceiling_gp, 4),
        },
        "conditions": [
            {
                "name": r["name"],
                "overall_all_30": r["overall_all_30"],
                "overall_gold_present": r["overall_gold_present"],
                "per_language": {
                    l: {
                        "count": m["count"],
                        "recall_at_5_mean": m["recall_at_5"][0],
                        "recall_at_5_ci95": [m["recall_at_5"][1], m["recall_at_5"][2]],
                        "recall_at_10_mean": m["recall_at_10"][0],
                        "recall_at_10_ci95": [m["recall_at_10"][1], m["recall_at_10"][2]],
                        "mrr_at_10_mean": m["mrr_at_10"][0],
                        "mrr_at_10_ci95": [m["mrr_at_10"][1], m["mrr_at_10"][2]],
                        "ndcg_at_10_mean": m["ndcg_at_10"][0],
                        "ndcg_at_10_ci95": [m["ndcg_at_10"][1], m["ndcg_at_10"][2]],
                    }
                    for l, m in r["per_language"].items()
                },
                "per_domain": {
                    d: {
                        "count": m["count"],
                        "recall_at_5_mean": m["recall_at_5"][0],
                        "recall_at_5_ci95": [m["recall_at_5"][1], m["recall_at_5"][2]],
                        "recall_at_10_mean": m["recall_at_10"][0],
                        "recall_at_10_ci95": [m["recall_at_10"][1], m["recall_at_10"][2]],
                        "mrr_at_10_mean": m["mrr_at_10"][0],
                        "mrr_at_10_ci95": [m["mrr_at_10"][1], m["mrr_at_10"][2]],
                        "ndcg_at_10_mean": m["ndcg_at_10"][0],
                        "ndcg_at_10_ci95": [m["ndcg_at_10"][1], m["ndcg_at_10"][2]],
                    }
                    for d, m in r["per_domain"].items()
                },
            }
            for r in all_res
        ],
        "holm_bonferroni_comparisons": {
            m: [
                {
                    "comparison": res["comparison"],
                    "candidate": res["candidate"],
                    "baseline": res["baseline"],
                    "rank": res["rank"],
                    "multiplier": res["multiplier"],
                    "mean_delta": res["mean_delta"],
                    "raw_ci": res["raw_ci"],
                    "raw_p_value": res["raw_p_value"],
                    "step_alpha": res["step_alpha"],
                    "adj_ci": res["adj_ci"],
                    "adj_p_value": res["adj_p_value"],
                    "significant_after_holm": res["significant_after_holm"],
                }
                for res in holm_results_by_metric[m]
            ]
            for m in ["mrr", "ndcg", "r5", "r10"]
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2)
    print(f"\n[+] Saved updated evaluation metrics to: {out_path}\n")


if __name__ == "__main__":
    main()
