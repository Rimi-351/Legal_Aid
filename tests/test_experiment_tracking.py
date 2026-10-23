"""
tests/test_experiment_tracking.py
---------------------------------
Unit tests for information retrieval metrics, experiment logging schema integrity,
and scenario-grouped split anti-leakage checks.
"""

import unittest
import tempfile
import json
from pathlib import Path

from src.evaluation.metrics import (
    compute_reciprocal_rank,
    compute_recall_at_k,
    compute_precision_at_k,
    compute_ndcg_at_k
)
from src.evaluation.logger import ExperimentLogger


class TestRetrievalMetrics(unittest.TestCase):

    def test_reciprocal_rank(self):
        gold = {"doc_target"}
        self.assertEqual(compute_reciprocal_rank(["doc_target", "doc_b", "doc_c"], gold), 1.0)
        self.assertEqual(compute_reciprocal_rank(["doc_a", "doc_target", "doc_c"], gold), 0.5)
        self.assertEqual(compute_reciprocal_rank(["doc_a", "doc_b", "doc_c", "doc_d", "doc_target"], gold), 0.2)
        self.assertEqual(compute_reciprocal_rank(["doc_a", "doc_b", "doc_c"], gold), 0.0)

    def test_recall_at_k(self):
        gold = {"doc_1", "doc_2"}
        # Both retrieved in top 3
        self.assertEqual(compute_recall_at_k(["doc_1", "doc_2", "doc_3"], gold, k=3), 1.0)
        # Only one retrieved in top 2
        self.assertEqual(compute_recall_at_k(["doc_1", "doc_3"], gold, k=2), 0.5)
        # None retrieved
        self.assertEqual(compute_recall_at_k(["doc_a", "doc_b"], gold, k=2), 0.0)

    def test_precision_at_k(self):
        gold = {"doc_1", "doc_2"}
        # Top 4 has 2 relevant items: precision = 2/4 = 0.5
        self.assertEqual(compute_precision_at_k(["doc_1", "doc_a", "doc_2", "doc_b"], gold, k=4), 0.5)
        # Top 2 has 2 relevant items: precision = 2/2 = 1.0
        self.assertEqual(compute_precision_at_k(["doc_1", "doc_2"], gold, k=2), 1.0)

    def test_ndcg_at_k(self):
        gold = {"doc_1"}
        # Hit at rank 1: DCG = 1.0 / log2(2) = 1.0, IDCG = 1.0 -> nDCG = 1.0
        self.assertAlmostEqual(compute_ndcg_at_k(["doc_1", "doc_2"], gold, k=2), 1.0)
        # Hit at rank 2: DCG = 1.0 / log2(3) = 0.6309, IDCG = 1.0 -> nDCG = 0.6309
        self.assertAlmostEqual(compute_ndcg_at_k(["doc_2", "doc_1"], gold, k=2), 0.630929, places=4)
        # No hit -> 0.0
        self.assertEqual(compute_ndcg_at_k(["doc_a", "doc_b"], gold, k=2), 0.0)

    def test_reciprocal_rank_with_k_cutoff(self):
        """Regression test: verify hit at rank > k returns 0.0 when k is specified."""
        gold = {"target"}
        retrieved = ["a", "b", "c", "d", "e", "target"]  # target at rank 6
        # When cutoff is k=5, rank 6 is outside cutoff -> 0.0
        self.assertEqual(compute_reciprocal_rank(retrieved, gold, k=5), 0.0)
        # When cutoff is k=10, rank 6 is within cutoff -> 1/6
        self.assertAlmostEqual(compute_reciprocal_rank(retrieved, gold, k=10), 1.0 / 6.0)

    def test_duplicate_retrieved_ids_protection(self):
        """Regression test: duplicate IDs in retrieved list do not inflate precision or gain."""
        gold = {"target"}
        # Duplicate target in top 4
        retrieved = ["target", "target", "other_1", "other_2"]
        # Without deduplication, precision would be 2/4 = 0.5. With protection, exactly 1/4 = 0.25
        self.assertEqual(compute_precision_at_k(retrieved, gold, k=4), 0.25)
        # nDCG should only reward the first occurrence
        self.assertAlmostEqual(compute_ndcg_at_k(retrieved, gold, k=4), 1.0)

    def test_empty_gold_and_edge_cases(self):
        """Verify empty gold sets or invalid cutoffs return 0.0 safely."""
        self.assertEqual(compute_reciprocal_rank(["a", "b"], set()), 0.0)
        self.assertEqual(compute_recall_at_k(["a", "b"], set(), k=5), 0.0)
        self.assertEqual(compute_precision_at_k(["a", "b"], set(), k=5), 0.0)
        self.assertEqual(compute_ndcg_at_k(["a", "b"], set(), k=5), 0.0)
        self.assertEqual(compute_precision_at_k(["a"], {"a"}, k=0), 0.0)
        self.assertEqual(compute_precision_at_k(["a"], {"a"}, k=-1), 0.0)


class TestExperimentLoggerAndSplitIntegrity(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.logger = ExperimentLogger(log_dir=str(self.temp_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_run_schema(self):
        """Verify experiment records are stored with complete metadata."""
        exp_id = self.logger.log_run(
            experiment_name="TEST_RUN_001",
            retrieval_method="bm25_word",
            model_name=None,
            corpus_manifest="data/manifests/processed_manifest.jsonl",
            num_provisions=17,
            query_records=[{"query_id": "Q1", "retrieved": ["CA1872_S10"], "mrr": 1.0}],
            config_params={"k": 5, "tokenizer": "word"},
            overall_metrics={"mrr_at_5": 0.4444, "recall_at_5": 0.4583},
            total_duration_sec=0.15,
            warnings=["Test warning"]
        )

        self.assertTrue(exp_id.startswith("EXP_"))

        # Verify JSONL file exists and is readable
        jsonl_file = self.temp_path / "experiments.jsonl"
        self.assertTrue(jsonl_file.exists())
        with open(jsonl_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual(len(lines), 1)
        record = lines[0]
        self.assertEqual(record["experiment_id"], exp_id)
        self.assertIn("timestamp_utc", record)
        self.assertIn("git_commit", record)
        self.assertEqual(record["retrieval_method"], "bm25_word")
        self.assertEqual(record["overall_metrics"]["mrr_at_5"], 0.4444)

        # Verify summary Markdown was generated
        md_file = self.temp_path / "experiment_summary.md"
        self.assertTrue(md_file.exists())
        summary_text = md_file.read_text(encoding="utf-8")
        self.assertIn(exp_id, summary_text)
        self.assertIn("bm25_word", summary_text)

    def test_scenario_grouped_split_anti_leakage(self):
        """Verify that training/development queries and test queries never share scenario IDs."""
        # Simulated dataset split
        dev_queries = [
            {"query_id": "Q_BN_01", "scenario_id": "SCENARIO_01_CONTRACT_BREACH"},
            {"query_id": "Q_EN_01", "scenario_id": "SCENARIO_02_CONSUMER_FRAUD"},
        ]
        test_queries = [
            {"query_id": "Q_BL_01", "scenario_id": "SCENARIO_03_LABOUR_TERMINATION"},
            {"query_id": "Q_BN_02", "scenario_id": "SCENARIO_04_RENT_EVICTION"},
        ]

        dev_scenarios = {q["scenario_id"] for q in dev_queries}
        test_scenarios = {q["scenario_id"] for q in test_queries}

        # Strict disjoint set check
        overlap = dev_scenarios.intersection(test_scenarios)
        self.assertEqual(len(overlap), 0, f"Scenario leakage detected! Overlapping scenarios: {overlap}")


if __name__ == "__main__":
    unittest.main()
