"""
src/retrieval/hybrid.py
-----------------------
Hybrid reciprocal rank fusion (RRF) combining lexical BM25 and semantic dense retrieval.
"""

from typing import List, Dict, Any, Optional
from .bm25 import SearchResult, BM25Index
from .dense import DenseRetriever


class HybridRetriever:
    """
    Fuses ranked candidate lists from BM25 and Dense bi-encoder using Reciprocal Rank Fusion.
    """

    def __init__(self, bm25_index: BM25Index, dense_retriever: DenseRetriever,
                 k_rrf: int = 60, weight_bm25: float = 1.0, weight_dense: float = 1.0):
        self.bm25_index = bm25_index
        self.dense_retriever = dense_retriever
        self.k_rrf = k_rrf
        self.weight_bm25 = weight_bm25
        self.weight_dense = weight_dense

    def search(self, query: str, top_k: int = 5, candidate_pool_size: int = 20) -> List[SearchResult]:
        """Fuses top candidates from both retrieval models."""
        if not query or top_k <= 0:
            return []

        bm25_results = self.bm25_index.search(query, top_k=candidate_pool_size)
        dense_results = self.dense_retriever.search(query, top_k=candidate_pool_size)

        rrf_scores: Dict[str, float] = {}
        provision_map: Dict[str, SearchResult] = {}

        # 1. Score BM25 candidates
        for res in bm25_results:
            pid = res.provision_id
            provision_map[pid] = res
            rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (self.weight_bm25 / (self.k_rrf + res.rank))

        # 2. Score Dense candidates
        for res in dense_results:
            pid = res.provision_id
            if pid not in provision_map:
                provision_map[pid] = res
            rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (self.weight_dense / (self.k_rrf + res.rank))

        # 3. Sort by fused score descending, then provision_id ascending for deterministic tie-breaking
        sorted_pids = sorted(rrf_scores.keys(), key=lambda pid: (-rrf_scores[pid], pid))

        fused_results: List[SearchResult] = []
        for rank, pid in enumerate(sorted_pids[:top_k], start=1):
            base_res = provision_map[pid]
            fused_score = rrf_scores[pid]

            fused_results.append(SearchResult(
                rank=rank,
                score=fused_score,
                provision_id=base_res.provision_id,
                act_title=base_res.act_title,
                section_number=base_res.section_number,
                section_heading=base_res.section_heading,
                text=base_res.text,
                language=base_res.language,
                source_file=base_res.source_file,
                matched_tokens=base_res.matched_tokens
            ))

        return fused_results
