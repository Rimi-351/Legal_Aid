"""
src/retrieval - Lexical, Dense, and Hybrid Retrieval Pipelines
"""
from typing import Any

from .bm25 import SearchResult, BM25Index, BengaliEnglishTokenizer

__all__ = [
    "SearchResult",
    "BM25Index",
    "BengaliEnglishTokenizer",
    "DenseRetriever",
    "HybridRetriever",
]


def __getattr__(name: str) -> Any:
    """Lazy import for dense and hybrid modules to avoid loading torch/transformers for lexical search."""
    if name == "DenseRetriever":
        from .dense import DenseRetriever
        return DenseRetriever
    elif name == "HybridRetriever":
        from .hybrid import HybridRetriever
        return HybridRetriever
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(__all__)
