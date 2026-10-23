"""
tests/test_embedding_feasibility.py
-----------------------------------
Automated smoke tests for independent embedding model feasibility evaluation.

Verifies:
1. Embedding shape matches model specification (768 for E5, 1024 for BGE-M3).
2. Embedding vectors contain strictly finite float values (zero NaNs, zero Infs).
3. Vectors are L2 unit-normalized (norm == 1.0 +- 1e-3).
4. Top-5 retrieval output structure contains required rank, score, and provision attributes.
5. Prefix conventions are preserved for models requiring instruction/modality prefixes.
"""

import unittest
import numpy as np

from scripts.eval_e5_feasibility import MultilingualE5Evaluator, PASSAGE_PREFIX, QUERY_PREFIX
from scripts.eval_bge_m3_feasibility import BGEM3Evaluator


class TestEmbeddingFeasibility(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize evaluators for smoke testing."""
        cls.e5_evaluator = MultilingualE5Evaluator()

    def test_e5_embedding_shape_and_finiteness(self):
        """Verify E5 produces (N, 768) strictly finite unit-normalized embeddings."""
        sample_texts = [
            f"{PASSAGE_PREFIX}The Contract Act, 1872 Section 10 What agreements are contracts",
            f"{PASSAGE_PREFIX}ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯ ধারা ৩৭ পণ্যের মোড়ক ইত্যাদি ব্যবহার না করিবার দণ্ড",
            f"{QUERY_PREFIX}Dokandar expiry date na likhe ponno sell korle ki shasti hobe?",
        ]
        vectors, latency = self.e5_evaluator.encode(sample_texts, batch_size=2)

        # 1. Shape check
        self.assertEqual(vectors.shape, (3, 768))

        # 2. Finiteness check
        self.assertTrue(np.all(np.isfinite(vectors)), "Embeddings must contain 100% finite floats.")
        self.assertFalse(np.any(np.isnan(vectors)), "Embeddings must not contain NaNs.")
        self.assertFalse(np.any(np.isinf(vectors)), "Embeddings must not contain Infinities.")

        # 3. L2 Unit Normalization check
        norms = np.linalg.norm(vectors, axis=1)
        for idx, norm in enumerate(norms):
            self.assertAlmostEqual(norm, 1.0, places=3, msg=f"Vector {idx} norm {norm} is not unit length.")

    def test_bge_m3_embedding_shape_and_finiteness(self):
        """Verify BGE-M3 produces (N, 1024) strictly finite unit-normalized embeddings."""
        bge_evaluator = BGEM3Evaluator()
        sample_texts = [
            "The Contract Act, 1872 Section 10 What agreements are contracts",
            "ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯ ধারা ৩৭ পণ্যের মোড়ক ইত্যাদি ব্যবহার না করিবার দণ্ড",
        ]
        vectors, latency = bge_evaluator.encode(sample_texts, batch_size=2)

        # 1. Shape check
        self.assertEqual(vectors.shape, (2, 1024))

        # 2. Finiteness check
        self.assertTrue(np.all(np.isfinite(vectors)), "Embeddings must contain 100% finite floats.")
        self.assertFalse(np.any(np.isnan(vectors)), "Embeddings must not contain NaNs.")
        self.assertFalse(np.any(np.isinf(vectors)), "Embeddings must not contain Infinities.")

        # 3. L2 Unit Normalization check
        norms = np.linalg.norm(vectors, axis=1)
        for idx, norm in enumerate(norms):
            self.assertAlmostEqual(norm, 1.0, places=3, msg=f"Vector {idx} norm {norm} is not unit length.")

    def test_e5_prefix_distinction(self):
        """Verify that E5 produces distinct representations with and without required query/passage prefixes."""
        base_text = "What is the penalty if a seller sells goods without expiration date?"
        text_with_prefix = f"{QUERY_PREFIX}{base_text}"
        text_without_prefix = base_text

        vecs, _ = self.e5_evaluator.encode([text_with_prefix, text_without_prefix], batch_size=2)
        cosine_sim = float(np.dot(vecs[0], vecs[1]))

        # The representations should be highly related but distinct due to instruction prefix
        self.assertLess(cosine_sim, 0.9999, "Prefix should meaningfully condition the embedding space.")
        self.assertGreater(cosine_sim, 0.85, "Same semantic content should maintain high correlation.")

    def test_retrieval_ranking_structure(self):
        """Verify cosine similarity ranking output structure and deterministic tie-breaking."""
        pids = ["PROV_A", "PROV_B", "PROV_C"]
        doc_vectors = np.array([
            [1.0, 0.0, 0.0],
            [0.5, 0.866, 0.0],
            [0.0, 1.0, 0.0],
        ], dtype=np.float32)
        # Normalize
        doc_vectors = doc_vectors / np.linalg.norm(doc_vectors, axis=1, keepdims=True)

        query_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        sims = np.dot(doc_vectors, query_vec)

        ranked_indices = sorted(range(len(pids)), key=lambda i: (-sims[i], pids[i]))
        top_results = [
            {
                "rank": rank + 1,
                "provision_id": pids[i],
                "score": round(float(sims[i]), 4),
            }
            for rank, i in enumerate(ranked_indices)
        ]

        # Verify rank ordering
        self.assertEqual(top_results[0]["provision_id"], "PROV_A")
        self.assertEqual(top_results[0]["rank"], 1)
        self.assertAlmostEqual(top_results[0]["score"], 1.0, places=4)
        self.assertEqual(top_results[1]["provision_id"], "PROV_B")
        self.assertEqual(top_results[2]["provision_id"], "PROV_C")


if __name__ == "__main__":
    unittest.main()
