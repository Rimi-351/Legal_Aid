"""
tests/test_hybrid.py
--------------------
Unit test suite for Reciprocal Rank Fusion (RRF) in src/retrieval/hybrid.py.
Verifies rank fusion mechanics, tie-breaking determinism, and candidate pool
edge conditions using lightweight mock retrievers.
"""
from typing import List, Optional
import pytest

from src.retrieval.bm25 import SearchResult
from src.retrieval.hybrid import HybridRetriever


def make_result(pid: str, rank: int, score: float = 1.0) -> SearchResult:
    """Helper to instantiate mock SearchResult with minimal valid fields."""
    return SearchResult(
        rank=rank,
        score=score,
        provision_id=pid,
        act_title="Sample Act 2020",
        section_number="1",
        section_heading="Test Section",
        text=f"Statutory text content for {pid}.",
        language="en",
        source_file="sample.html",
        matched_tokens={"sample"},
    )


class FakeRetriever:
    """Mock retriever returning predetermined SearchResult lists."""
    def __init__(self, results: List[SearchResult]):
        self.results = results
        self.last_top_k: Optional[int] = None

    def search(self, query: str, top_k: int = 5, **kwargs) -> List[SearchResult]:
        self.last_top_k = top_k
        return self.results[:top_k]


def test_doc_ranked_first_by_both():
    """
    Risk: When a document is ranked top by both lexical and dense retrievers,
    its reciprocal rank score must sum both channels and rank strictly first.
    """
    bm25_mock = FakeRetriever([
        make_result("DOC_A", rank=1),
        make_result("DOC_B", rank=2),
    ])
    dense_mock = FakeRetriever([
        make_result("DOC_A", rank=1),
        make_result("DOC_C", rank=2),
    ])

    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock, k_rrf=60)
    results = hybrid.search(query="test query", top_k=5)

    assert len(results) == 3
    # DOC_A must be rank 1
    assert results[0].provision_id == "DOC_A"
    assert results[0].rank == 1
    # Expected fused score: 1.0/(60+1) + 1.0/(60+1) = 2/61
    expected_score = (1.0 / 61.0) + (1.0 / 61.0)
    assert pytest.approx(results[0].score, rel=1e-5) == expected_score


def test_doc_found_by_only_one_retriever():
    """
    Risk: Documents present in only one channel must not be dropped, but should
    rank lower than documents reinforced across both channels.
    """
    # DOC_BOTH is rank 3 in both (score = 1/63 + 1/63 = 2/63 ~= 0.0317)
    # DOC_BM25_ONLY is rank 1 in BM25 only (score = 1/61 ~= 0.0164)
    # DOC_DENSE_ONLY is rank 2 in Dense only (score = 1/62 ~= 0.0161)
    bm25_mock = FakeRetriever([
        make_result("DOC_BM25_ONLY", rank=1),
        make_result("DOC_BOTH", rank=3),
    ])
    dense_mock = FakeRetriever([
        make_result("DOC_DENSE_ONLY", rank=2),
        make_result("DOC_BOTH", rank=3),
    ])

    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock, k_rrf=60)
    results = hybrid.search(query="contract dispute", top_k=5)

    pids = [r.provision_id for r in results]
    assert pids == ["DOC_BOTH", "DOC_BM25_ONLY", "DOC_DENSE_ONLY"]

    # Check scores
    score_both = results[0].score
    score_bm25_only = results[1].score
    score_dense_only = results[2].score

    assert pytest.approx(score_both, rel=1e-5) == (2.0 / 63.0)
    assert pytest.approx(score_bm25_only, rel=1e-5) == (1.0 / 61.0)
    assert pytest.approx(score_dense_only, rel=1e-5) == (1.0 / 62.0)


def test_tied_scores_deterministic_lexicographical_order():
    """
    Risk: Tied RRF scores could cause non-deterministic ranking flip-flops
    between test runs or API calls if ordering does not enforce stable secondary sort.
    """
    # DOC_Z is rank 1 in BM25 (score = 1/61)
    # DOC_A is rank 1 in Dense (score = 1/61)
    # Both have identical fused scores: 1/61
    bm25_mock = FakeRetriever([make_result("DOC_Z", rank=1)])
    dense_mock = FakeRetriever([make_result("DOC_A", rank=1)])

    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock, k_rrf=60)
    results = hybrid.search(query="eviction notice", top_k=5)

    assert len(results) == 2
    assert results[0].score == results[1].score
    # Lexicographical tie-breaking enforces DOC_A precedes DOC_Z
    assert results[0].provision_id == "DOC_A"
    assert results[1].provision_id == "DOC_Z"


@pytest.mark.parametrize("invalid_top_k", [0, -1, -10])
def test_top_k_zero_or_negative_returns_empty(invalid_top_k: int):
    """
    Risk: top_k <= 0 must safely return an empty candidate list without raising
    IndexError or slice errors.
    """
    bm25_mock = FakeRetriever([make_result("DOC_1", rank=1)])
    dense_mock = FakeRetriever([make_result("DOC_1", rank=1)])
    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock)

    results = hybrid.search("test", top_k=invalid_top_k)
    assert results == []


def test_empty_query_returns_empty():
    """
    Risk: Empty query string must short-circuit retrieval and return an empty list.
    """
    bm25_mock = FakeRetriever([make_result("DOC_1", rank=1)])
    dense_mock = FakeRetriever([make_result("DOC_1", rank=1)])
    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock)

    assert hybrid.search("", top_k=5) == []


def test_top_k_larger_than_candidate_pool():
    """
    Risk: Requesting top_k greater than the number of available candidates must
    return all available items without padding with None or crashing.
    """
    bm25_mock = FakeRetriever([make_result("DOC_1", rank=1)])
    dense_mock = FakeRetriever([make_result("DOC_2", rank=1)])
    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock)

    results = hybrid.search("test", top_k=100)
    assert len(results) == 2
    assert [r.rank for r in results] == [1, 2]


def test_candidate_pool_size_limits_retrieval_depth():
    """
    Risk: candidate_pool_size parameter controls retrieval depth passed to underlying
    retrievers, preventing unnecessary candidate scoring and latency.
    """
    bm25_mock = FakeRetriever([make_result(f"DOC_{i}", rank=i) for i in range(1, 11)])
    dense_mock = FakeRetriever([make_result(f"DOC_{i}", rank=i) for i in range(1, 11)])
    hybrid = HybridRetriever(bm25_index=bm25_mock, dense_retriever=dense_mock)

    results = hybrid.search("test", top_k=5, candidate_pool_size=3)
    assert bm25_mock.last_top_k == 3
    assert dense_mock.last_top_k == 3
    assert len(results) == 3

