"""
src/retrieval/dense.py
----------------------
Dense bi-encoder retrieval engine using PyTorch CPU and Hugging Face Transformers.
Features mean-pooling, L2 vector normalization, cosine ranking, and caching.
"""

import os
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

try:
    import torch
    import psutil
    from transformers import AutoTokenizer, AutoModel
    TORCH_TRANSFORMERS_AVAILABLE = True
except ImportError:
    TORCH_TRANSFORMERS_AVAILABLE = False

from .bm25 import SearchResult


def compute_corpus_hash(provisions: List[Dict[str, Any]]) -> str:
    """Computes stable SHA-256 hash of provision IDs and texts."""
    h = hashlib.sha256()
    for p in sorted(provisions, key=lambda x: x.get("provision_id", "")):
        h.update(p.get("provision_id", "").encode("utf-8"))
        h.update(p.get("text", "")[:100].encode("utf-8"))
    return h.hexdigest()[:16]


def get_process_rss_mb() -> float:
    """Returns current process RSS memory in MB."""
    try:
        proc = psutil.Process(os.getpid())
        return round(proc.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


class DenseRetriever:
    """
    Multilingual dense retriever running on CPU with vector caching.
    """

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small",
                 cache_dir: str = "experiments/cache",
                 batch_size: int = 4,
                 max_length: int = 512,
                 device: str = "cpu"):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self.max_length = max_length
        self.device = device

        self.tokenizer = None
        self.model = None
        self.is_loaded = False
        self.model_load_time_sec = 0.0

        self.corpus: List[Dict[str, Any]] = []
        self.doc_embeddings: Optional[np.ndarray] = None
        self.corpus_hash: str = ""

        # Determine if E5 prefixing is required
        self.is_e5_model = "e5" in model_name.lower()

    def load_model(self):
        """Loads tokenizer and model onto CPU."""
        if self.is_loaded:
            return

        if not TORCH_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "PyTorch or Transformers is not installed.\n"
                "Ensure torch and transformers are available in the Python environment."
            )

        print(f"[*] Loading Dense Embedding Model: '{self.model_name}' on {self.device.upper()}...")
        start_mem = get_process_rss_mb()
        t0 = time.perf_counter()

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.eval()
        self.model.to(self.device)

        self.model_load_time_sec = round(time.perf_counter() - t0, 3)
        self.is_loaded = True
        post_mem = get_process_rss_mb()
        print(f"[+] Loaded '{self.model_name}' in {self.model_load_time_sec:.2f} s (Process RSS: {post_mem} MB, Delta: +{round(post_mem - start_mem, 2)} MB)")

    def _mean_pooling(self, model_output, attention_mask) -> torch.Tensor:
        """Applies mean pooling over token embeddings, respecting the attention mask."""
        token_embeddings = model_output[0]  # First element of model_output contains hidden states
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask

    def encode(self, texts: List[str], is_query: bool = False) -> np.ndarray:
        """Encodes a list of text strings into L2-normalized float32 vectors."""
        self.load_model()

        if not texts:
            return np.empty((0, 768), dtype=np.float32)

        # Apply model prefix if E5
        if self.is_e5_model:
            prefix = "query: " if is_query else "passage: "
            prefixed_texts = [f"{prefix}{t}" for t in texts]
        else:
            prefixed_texts = texts

        all_embeddings = []

        for i in range(0, len(prefixed_texts), self.batch_size):
            batch_texts = prefixed_texts[i:i + self.batch_size]
            encoded = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**encoded)
                embeddings = self._mean_pooling(outputs, encoded["attention_mask"])
                # L2 normalize vectors
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                all_embeddings.append(embeddings.cpu().numpy())

        return np.vstack(all_embeddings).astype(np.float32)

    def fit(self, provisions: List[Dict[str, Any]], filter_quarantined: bool = True, force_recompute: bool = False):
        """Indexes provisions and generates or loads cached embeddings."""
        self.corpus = []
        for p in provisions:
            if filter_quarantined and p.get("is_quarantined", False):
                continue
            self.corpus.append(p)

        if not self.corpus:
            self.doc_embeddings = np.empty((0, 768), dtype=np.float32)
            return

        self.corpus_hash = compute_corpus_hash(self.corpus)
        sanitized_model_id = self.model_name.replace("/", "_").replace(":", "_")
        cache_path = self.cache_dir / f"embeddings_{sanitized_model_id}_{self.corpus_hash}.npz"

        if not force_recompute and cache_path.exists():
            print(f"[*] Loading cached document embeddings from: {cache_path}")
            data = np.load(cache_path)
            self.doc_embeddings = data["embeddings"]
            print(f"[+] Loaded {len(self.doc_embeddings)} cached embeddings (Dim: {self.doc_embeddings.shape[1]})")
        else:
            print(f"[*] Generating embeddings for {len(self.corpus)} provisions using '{self.model_name}'...")
            t0 = time.perf_counter()
            doc_texts = [
                f"{p.get('act_title', '')} {p.get('section_heading', '')} {p.get('text', '')}"
                for p in self.corpus
            ]
            self.doc_embeddings = self.encode(doc_texts, is_query=False)
            elapsed = time.perf_counter() - t0
            print(f"[+] Encoded {len(self.corpus)} provisions in {elapsed:.2f} s ({round(elapsed / len(self.corpus) * 1000, 2)} ms/passage)")

            # Save to cache
            np.savez_compressed(cache_path, embeddings=self.doc_embeddings)
            print(f"[+] Cached embeddings saved to: {cache_path}")

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Runs cosine similarity search against indexed document embeddings."""
        if not query or self.doc_embeddings is None or len(self.corpus) == 0 or top_k <= 0:
            return []

        query_vec = self.encode([query], is_query=True)[0]  # shape: (dim,)

        # Cosine similarity is simply dot product because vectors are L2-normalized
        similarities = np.dot(self.doc_embeddings, query_vec)

        # Rank documents
        ranked_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[SearchResult] = []
        for rank, idx in enumerate(ranked_indices, start=1):
            score = float(similarities[idx])
            p = self.corpus[idx]
            results.append(SearchResult(
                rank=rank,
                score=score,
                provision_id=p.get("provision_id", f"DOC_{idx}"),
                act_title=p.get("act_title", ""),
                section_number=p.get("section_number", ""),
                section_heading=p.get("section_heading", ""),
                text=p.get("text", ""),
                language=p.get("language", ""),
                source_file=p.get("source_file", ""),
                matched_tokens=[]
            ))

        return results
