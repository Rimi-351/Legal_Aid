"""
src/evaluation/metrics.py
-------------------------
Standard information retrieval metrics: Recall@k, Precision@k, MRR, nDCG@k.
"""

import math
from typing import List, Set, Union


def compute_reciprocal_rank(retrieved_ids: List[str], gold_ids: Union[List[str], Set[str]]) -> float:
    """Computes Reciprocal Rank (1 / rank of first relevant item)."""
    gold_set = set(gold_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in gold_set:
            return 1.0 / rank
    return 0.0


def compute_recall_at_k(retrieved_ids: List[str], gold_ids: Union[List[str], Set[str]], k: int = 5) -> float:
    """Computes Recall@k (fraction of relevant items retrieved in top-k)."""
    if not gold_ids or k <= 0:
        return 0.0

    gold_set = set(gold_ids)
    top_k_ids = set(retrieved_ids[:k])
    matched = len(top_k_ids.intersection(gold_set))
    return matched / len(gold_set)


def compute_precision_at_k(retrieved_ids: List[str], gold_ids: Union[List[str], Set[str]], k: int = 5) -> float:
    """Computes Precision@k (fraction of retrieved top-k items that are relevant)."""
    if k <= 0:
        return 0.0

    gold_set = set(gold_ids)
    top_k_ids = retrieved_ids[:k]
    matched = sum(1 for doc_id in top_k_ids if doc_id in gold_set)
    return matched / k


def compute_ndcg_at_k(retrieved_ids: List[str], gold_ids: Union[List[str], Set[str]], k: int = 5) -> float:
    """Computes Normalized Discounted Cumulative Gain (nDCG@k) with binary relevance."""
    if not gold_ids or k <= 0:
        return 0.0

    gold_set = set(gold_ids)
    top_k = retrieved_ids[:k]

    # Compute DCG@k
    dcg = 0.0
    for i, doc_id in enumerate(top_k):
        if doc_id in gold_set:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because 1-based rank i=0 is rank 1 -> log2(2) = 1

    # Compute Ideal DCG@k (IDCG@k)
    ideal_hits = min(len(gold_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    if idcg == 0.0:
        return 0.0

    return dcg / idcg
