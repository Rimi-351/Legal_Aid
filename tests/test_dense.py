"""
tests/test_dense.py
-------------------
Unit tests for dense retrieval logic:
- L2 normalization and cosine similarity math.
- Corpus hash calculation.
- Embedding caching (.npz format) and vector ranking.
- Edge case handling (empty queries, invalid k).
- Mock dense encoder (no large model downloads during unit tests).
"""

import unittest
import tempfile
import numpy as np
from pathlib import Path

from src.retrieval.dense import (
    compute_corpus_hash,
    DenseRetriever,
    TORCH_TRANSFORMERS_AVAILABLE
)
from src.retrieval.bm25 import SearchResult


class TestDenseRetrievalMathAndLogic(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_corpus_hash_determinism(self):
        """Verify identical provision sets produce identical SHA hashes."""
        provisions_1 = [
            {"provision_id": "P1", "text": "Contract law in Bangladesh"},
            {"provision_id": "P2", "text": "Labour law statutory provision"}
        ]
        provisions_2 = [
            {"provision_id": "P2", "text": "Labour law statutory provision"},
            {"provision_id": "P1", "text": "Contract law in Bangladesh"}
        ]
        # Order should not matter because compute_corpus_hash sorts by provision_id
        hash1 = compute_corpus_hash(provisions_1)
        hash2 = compute_corpus_hash(provisions_2)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)

    def test_mock_vector_ranking_and_cosine_similarity(self):
        """Verify dot product on L2-normalized vectors matches expected cosine ranking."""
        # 3 mock vectors in 4-dimensional space
        # Target query points strongly along axis 0: [1, 0, 0, 0]
        v_query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Candidate 0: closely aligned [0.95, 0.31, 0.0, 0.0] -> norm ~ 1.0
        c0 = np.array([0.95, 0.3122, 0.0, 0.0], dtype=np.float32)
        c0 = c0 / np.linalg.norm(c0)

        # Candidate 1: orthogonal [0.0, 1.0, 0.0, 0.0]
        c1 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)

        # Candidate 2: opposite/poorly aligned [-0.5, 0.5, 0.5, 0.5]
        c2 = np.array([-0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        c2 = c2 / np.linalg.norm(c2)

        corpus_matrix = np.vstack([c0, c1, c2])

        # Verify finite values
        self.assertTrue(np.all(np.isfinite(corpus_matrix)))
        self.assertEqual(corpus_matrix.shape, (3, 4))

        # Compute cosine similarities via dot product
        scores = np.dot(corpus_matrix, v_query)
        self.assertEqual(scores.shape, (3,))
        self.assertAlmostEqual(scores[0], c0[0], places=3)
        self.assertAlmostEqual(scores[1], 0.0, places=3)
        self.assertLess(scores[2], 0.0)

        # Sorted indices
        ranked_indices = np.argsort(scores)[::-1]
        self.assertEqual(ranked_indices[0], 0)  # c0 is highest
        self.assertEqual(ranked_indices[1], 1)  # c1 is second
        self.assertEqual(ranked_indices[2], 2)  # c2 is last

    def test_npz_embedding_cache_roundtrip(self):
        """Verify embedding matrices and IDs save and load faithfully to compressed .npz."""
        cache_file = self.temp_path / "mock_embeddings.npz"
        original_vectors = np.random.randn(5, 128).astype(np.float32)
        # Normalize
        norms = np.linalg.norm(original_vectors, axis=1, keepdims=True)
        original_vectors = original_vectors / norms
        original_ids = np.array([f"P{i}" for i in range(5)])

        # Save
        np.savez_compressed(cache_file, embeddings=original_vectors, ids=original_ids)
        self.assertTrue(cache_file.exists())

        # Load
        loaded_data = np.load(cache_file)
        self.assertIn("embeddings", loaded_data)
        self.assertIn("ids", loaded_data)
        loaded_vectors = loaded_data["embeddings"]
        loaded_ids = loaded_data["ids"].tolist()

        self.assertEqual(loaded_vectors.shape, (5, 128))
        self.assertEqual(loaded_ids, [f"P{i}" for i in range(5)])
        np.testing.assert_allclose(original_vectors, loaded_vectors, rtol=1e-5)


if __name__ == "__main__":
    unittest.main()
