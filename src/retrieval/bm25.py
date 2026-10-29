"""
src/retrieval/bm25.py
---------------------
Okapi BM25 lexical retrieval engine with specialized Bengali-English tokenization.
Pure Python, zero-dependency, fully reproducible implementation.
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from collections import Counter
from typing import List, Dict, Any, Optional, Set

from src.retrieval.temporal import resolve_provision_version_status


@dataclass
class SearchResult:
    """Represents a ranked retrieval result with full provenance."""
    rank: int
    score: float
    provision_id: str
    act_title: str
    section_number: str
    section_heading: str
    text: str
    language: str
    source_file: str
    matched_tokens: List[str]
    version_status: str = "uncertain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "score": round(self.score, 4),
            "provision_id": self.provision_id,
            "act_title": self.act_title,
            "section_number": self.section_number,
            "section_heading": self.section_heading,
            "text": self.text,
            "language": self.language,
            "source_file": self.source_file,
            "matched_tokens": self.matched_tokens,
            "version_status": self.version_status,
        }


class BengaliEnglishTokenizer:
    """
    Tokenizer handling Bengali Unicode script, English ASCII words, and Bengali/Arabic numerals.
    Includes support for character n-grams to handle phonetic Banglish spelling variation.
    """

    def __init__(self, use_char_ngrams: bool = False, ngram_n: int = 3):
        self.use_char_ngrams = use_char_ngrams
        self.ngram_n = ngram_n
        # Regex matching Bengali words, English words, or numbers
        self.re_tokens = re.compile(r"[\u0980-\u09FF]+|[a-zA-Z]+|[0-9\u09E6-\u09EF]+")

    def tokenize(self, text: str) -> List[str]:
        """Tokenizes text into normalized words and optional character n-grams."""
        if not text:
            return []

        # 1. Unicode NFC Normalization
        normalized = unicodedata.normalize("NFC", text)

        # 2. Extract word tokens
        words = self.re_tokens.findall(normalized)
        tokens = [w.lower() if w.isascii() else w for w in words]

        # 3. Optional character n-grams for transliteration / spelling resilience
        if self.use_char_ngrams:
            ngrams = []
            for w in tokens:
                if len(w) >= self.ngram_n:
                    for i in range(len(w) - self.ngram_n + 1):
                        ngrams.append(w[i:i + self.ngram_n])
            tokens.extend(ngrams)

        return tokens


class BM25Index:
    """
    Okapi BM25 index with configurable k1 and b parameters.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, use_char_ngrams: bool = False):
        self.k1 = k1
        self.b = b
        self.tokenizer = BengaliEnglishTokenizer(use_char_ngrams=use_char_ngrams)
        self.corpus: List[Dict[str, Any]] = []
        self.doc_len: List[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_term_freqs: List[Counter] = []
        self.idf: Dict[str, float] = {}
        self.num_docs: int = 0

    def fit(self, provisions: List[Dict[str, Any]], filter_quarantined: bool = True):
        """Builds index over a list of provision dictionaries."""
        self.corpus = []
        raw_doc_tokens = []

        for p in provisions:
            if filter_quarantined and p.get("is_quarantined", False):
                continue
            self.corpus.append(p)

            # Combine title, heading, and text for indexing
            doc_text = f"{p.get('act_title', '')} {p.get('section_heading', '')} {p.get('text', '')}"
            tokens = self.tokenizer.tokenize(doc_text)
            raw_doc_tokens.append(tokens)

        self.num_docs = len(self.corpus)
        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            return

        self.doc_len = [len(toks) for toks in raw_doc_tokens]
        self.avg_doc_len = sum(self.doc_len) / self.num_docs
        self.doc_term_freqs = [Counter(toks) for toks in raw_doc_tokens]

        # Compute document frequencies
        df: Dict[str, int] = Counter()
        for term_counter in self.doc_term_freqs:
            for term in term_counter.keys():
                df[term] += 1

        # Compute Okapi BM25 IDF
        self.idf = {}
        for term, freq in df.items():
            # Standard Okapi IDF with +1 smoothing to avoid negative weights
            self.idf[term] = math.log(((self.num_docs - freq + 0.5) / (freq + 0.5)) + 1.0)

    def search(self, query: str, top_k: int = 5, as_of_date: Optional[str] = None) -> List[SearchResult]:
        """Searches index with a natural language query and returns top-k ranked results with version status."""
        if not query or self.num_docs == 0 or top_k <= 0:
            return []

        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []

        scores: List[float] = [0.0] * self.num_docs
        matched_tokens_per_doc: List[Set[str]] = [set() for _ in range(self.num_docs)]

        for q_term in query_tokens:
            if q_term not in self.idf:
                continue

            term_idf = self.idf[q_term]

            for doc_idx, term_freqs in enumerate(self.doc_term_freqs):
                if q_term in term_freqs:
                    freq = term_freqs[q_term]
                    dl = self.doc_len[doc_idx]
                    numerator = freq * (self.k1 + 1.0)
                    denominator = freq + self.k1 * (1.0 - self.b + self.b * (dl / self.avg_doc_len))
                    scores[doc_idx] += term_idf * (numerator / denominator)
                    matched_tokens_per_doc[doc_idx].add(q_term)

        # Rank documents with non-zero score; secondary tie breaker by provision_id
        scored_docs = [
            (idx, scores[idx], self.corpus[idx].get("provision_id", f"DOC_{idx}"))
            for idx in range(self.num_docs) if scores[idx] > 0.0
        ]
        scored_docs.sort(key=lambda x: (-x[1], x[2]))

        results: List[SearchResult] = []
        for rank, (idx, score, pid) in enumerate(scored_docs[:top_k], start=1):
            p = self.corpus[idx]
            v_status = resolve_provision_version_status(p, as_of_date=as_of_date) if as_of_date else "uncertain"
            results.append(SearchResult(
                rank=rank,
                score=score,
                provision_id=p.get("provision_id", pid),
                act_title=p.get("act_title", ""),
                section_number=p.get("section_number", ""),
                section_heading=p.get("section_heading", ""),
                text=p.get("text", ""),
                language=p.get("language", ""),
                source_file=p.get("source_file", ""),
                matched_tokens=sorted(list(matched_tokens_per_doc[idx])),
                version_status=v_status,
            ))

        return results

    def query(self, query_text: str, top_k: int = 5, as_of_date: Optional[str] = None) -> List[SearchResult]:
        """Alias for search."""
        return self.search(query_text, top_k=top_k, as_of_date=as_of_date)

    def index_corpus(self, provisions: List[Dict[str, Any]], filter_quarantined: bool = True):
        """Alias for fit."""
        return self.fit(provisions, filter_quarantined=filter_quarantined)


# Class alias for consistent nomenclature across components
BM25Retriever = BM25Index
