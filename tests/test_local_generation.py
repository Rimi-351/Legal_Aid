"""
tests/test_local_generation.py
------------------------------
Focused unit tests for Day 4 Local Legal Answer Generation and Extractive Baseline.
Verifies:
1. Deterministic extractive baseline formatting and provenance preservation.
2. Extractive baseline abstention on empty evidence.
3. Provision ID citation extraction and regex accuracy.
4. Rubric scoring logic for evidence grounding, citations, and abstention.
5. Prompt template construction with multi-provision blocks.
6. Ollama client error handling and graceful fallbacks.
"""

import unittest
from src.generation.prompts import build_user_prompt, format_evidence_block
from src.generation.extractive import ExtractiveBaselineGenerator
from src.generation.rubric import GenerationRubricEvaluator
from src.generation.client import OllamaGenerationClient


class TestLocalGeneration(unittest.TestCase):

    def setUp(self):
        self.extractive_gen = ExtractiveBaselineGenerator()
        self.rubric = GenerationRubricEvaluator()
        self.sample_provisions = [
            {
                "provision_id": "CA1872_S11",
                "act_title": "The Contract Act, 1872",
                "section_number": "11",
                "section_heading": "Who are competent to contract",
                "text": "Every person is competent to contract who is of the age of majority...",
                "source_file": "data/raw/sample_audit_files/sample_contract_act_1872.html",
            },
            {
                "provision_id": "CA1872_S10",
                "act_title": "The Contract Act, 1872",
                "section_number": "10",
                "section_heading": "What agreements are contracts",
                "text": "All agreements are contracts if they are made by the free consent of parties...",
                "source_file": "data/raw/sample_audit_files/sample_contract_act_1872.html",
            },
        ]

    def test_extractive_generator_multi_provision(self):
        """Verify extractive generator returns verbatim blocks with provenance."""
        res = self.extractive_gen.generate(
            query="Who can contract?",
            provisions=self.sample_provisions,
            query_language="en",
        )
        self.assertFalse(res["is_abstention"])
        self.assertEqual(res["passages_count"], 2)
        self.assertEqual(res["cited_provision_ids"], ["CA1872_S11", "CA1872_S10"])
        self.assertIn("[Provision 1: CA1872_S11]", res["answer"])
        self.assertIn("The Contract Act, 1872", res["answer"])
        self.assertIn("[Provision 2: CA1872_S10]", res["answer"])

    def test_extractive_generator_empty_abstention(self):
        """Verify extractive generator abstains when evidence is empty."""
        res_en = self.extractive_gen.generate(
            query="What is the limitation period?",
            provisions=[],
            query_language="en",
        )
        self.assertTrue(res_en["is_abstention"])
        self.assertIn("do not contain sufficient evidence", res_en["answer"])

        res_bn = self.extractive_gen.generate(
            query="সাইবার অপরাধে কি সাজা?",
            provisions=[],
            query_language="bn",
        )
        self.assertTrue(res_bn["is_abstention"])
        self.assertIn("পর্যাপ্ত তথ্য বা প্রমাণ নেই", res_bn["answer"])

    def test_citation_extraction(self):
        """Verify extraction of valid schema provision IDs."""
        text = (
            "According to [CA1872_S11], a minor cannot contract. "
            "Furthermore, CRPA2009_S৩৭ imposes penalties."
        )
        cits = self.rubric.extract_citations(text)
        self.assertIn("CA1872_S11", cits)
        self.assertIn("CRPA2009_S৩৭", cits)
        self.assertEqual(len(cits), 2)

    def test_rubric_scoring_abstention(self):
        """Verify rubric awards full score for proper abstention on unanswerable query."""
        unanswerable_case = {
            "case_id": "CASE_TEST_UNANSWERABLE",
            "is_answerable": False,
            "target_provision_ids": [],
            "expected_concepts": ["insufficient evidence"],
            "prohibited_hallucinations": ["3 years"],
        }
        good_abstention_text = "The provided legal passages do not contain sufficient evidence to answer."
        eval_good = self.rubric.evaluate(
            case=unanswerable_case,
            answer_text=good_abstention_text,
            condition="generative",
            supplied_pids=[],
        )
        self.assertEqual(eval_good["scores"]["abstention_correctness"], 2)
        self.assertEqual(eval_good["scores"]["evidence_support"], 2)
        self.assertEqual(eval_good["scores"]["factual_fidelity"], 2)

        bad_hallucination_text = "The limitation period is 3 years under Section 19."
        eval_bad = self.rubric.evaluate(
            case=unanswerable_case,
            answer_text=bad_hallucination_text,
            condition="generative",
            supplied_pids=[],
        )
        self.assertEqual(eval_bad["scores"]["abstention_correctness"], 0)
        self.assertEqual(eval_bad["scores"]["factual_fidelity"], 0)

    def test_prompt_template_rendering(self):
        """Verify user prompt correctly formats multiple provisions and query."""
        prompt = build_user_prompt("Can a minor enter into a contract?", self.sample_provisions)
        self.assertIn("--- EVIDENCE START ---", prompt)
        self.assertIn("Passage 1 [ID: CA1872_S11]:", prompt)
        self.assertIn("Passage 2 [ID: CA1872_S10]:", prompt)
        self.assertIn("Can a minor enter into a contract?", prompt)

    def test_client_offline_fallback(self):
        """Verify client returns error dictionary on unreachable port rather than crashing."""
        offline_client = OllamaGenerationClient(base_url="http://127.0.0.1:59999", timeout_sec=1.0)
        res = offline_client.generate("Test prompt")
        self.assertIsNotNone(res["error"])
        self.assertEqual(res["answer"], "")

    def test_citation_checked_against_supplied_evidence_generative(self):
        """Verify citations are checked against retrieved evidence passages, not just corpus dictionary."""
        case = {
            "case_id": "CASE_TEST_CIT_GROUND",
            "category": "E_CITATION_GROUNDING",
            "query": "Notice period for termination?",
            "target_provision_ids": ["BLA2006_S২৬"],
            "is_answerable": True,
            "expected_concepts": ["120 days notice"],
            "prohibited_hallucinations": [],
        }

        # Case 1: Model cites provision present in supplied evidence -> Full score (2)
        ans_valid = "According to [BLA2006_S২৬], 120 days written notice is required."
        ev_valid = self.rubric.evaluate(
            case=case,
            answer_text=ans_valid,
            condition="generative",
            supplied_pids=["BLA2006_S২৬"],
        )
        self.assertEqual(ev_valid["scores"]["citation_validity"], 2)

        # Case 2: Model cites a valid corpus provision that was NOT in supplied evidence -> Penalized (1)
        ans_unretrieved = "According to [CA1872_S11], majority is required."
        ev_unretrieved = self.rubric.evaluate(
            case=case,
            answer_text=ans_unretrieved,
            condition="generative",
            supplied_pids=["BLA2006_S২৬"],
        )
        self.assertEqual(ev_unretrieved["scores"]["citation_validity"], 1)

        # Case 3: Model cites a completely non-existent / fabricated provision ID -> 0
        ans_fake = "According to [FAKE_ACT_S99], 30 days notice is required."
        ev_fake = self.rubric.evaluate(
            case=case,
            answer_text=ans_fake,
            condition="generative",
            supplied_pids=["BLA2006_S২৬"],
        )
        self.assertEqual(ev_fake["scores"]["citation_validity"], 0)

    def test_evidence_support_requires_retrieved_evidence(self):
        """Verify evidence support requires target provisions to be in supplied evidence."""
        case = {
            "case_id": "CASE_TEST_EVID_SUPP",
            "category": "C_TWO_PROVISION",
            "query": "Enforceable contract requirements?",
            "target_provision_ids": ["CA1872_S10", "CA1872_S11"],
            "is_answerable": True,
            "expected_concepts": [],
            "prohibited_hallucinations": [],
        }

        # If both are supplied and cited -> evidence_support = 2
        ans = "Under [CA1872_S10] and [CA1872_S11], free consent and majority are required."
        ev_full = self.rubric.evaluate(case, ans, "generative", ["CA1872_S10", "CA1872_S11"])
        self.assertEqual(ev_full["scores"]["evidence_support"], 2)

        # If CA1872_S11 was NOT in supplied evidence (retriever failed to fetch it) -> partial evidence support (1)
        ev_partial_evidence = self.rubric.evaluate(case, ans, "generative", ["CA1872_S10"])
        self.assertEqual(ev_partial_evidence["scores"]["evidence_support"], 1)

    def test_extractive_bengali_abstention_pipeline(self):
        """Verify extractive Bengali abstention message is recognized and scored 2.0 by rubric."""
        unans_case_bn = {
            "case_id": "CASE_TEST_UNANS_BN",
            "category": "D_INSUFFICIENT_EVID",
            "query": "সাইবার ক্রাইমে কি সাজা?",
            "query_language": "bn",
            "target_provision_ids": [],
            "is_answerable": False,
            "expected_concepts": ["পর্যাপ্ত তথ্য বা প্রমাণ নেই"],
            "prohibited_hallucinations": ["৫ বছর জেল"],
        }
        res_bn = self.extractive_gen.generate(
            query=unans_case_bn["query"],
            provisions=[],
            query_language="bn",
        )
        self.assertTrue(res_bn["is_abstention"])

        ev = self.rubric.evaluate(
            case=unans_case_bn,
            answer_text=res_bn["answer"],
            condition="extractive",
            supplied_pids=[],
        )
        self.assertTrue(ev["is_abstention"])
        self.assertEqual(ev["scores"]["abstention_correctness"], 2)
        self.assertEqual(ev["scores"]["evidence_support"], 2)
        self.assertEqual(ev["scores"]["factual_fidelity"], 2)
        self.assertEqual(ev["mean_rubric_score"], 2.0)

    def test_multi_provision_synthesis_scoring(self):
        """Verify partial vs full credit on two-provision synthesis."""
        case = {
            "case_id": "CASE_TEST_TWO_PROV",
            "category": "C_TWO_PROVISION",
            "target_provision_ids": ["PRCA1991_S১৩", "PRCA1991_S১৮"],
            "is_answerable": True,
            "expected_concepts": [],
            "prohibited_hallucinations": [],
        }
        supplied = ["PRCA1991_S১৩", "PRCA1991_S১৮"]

        # Only 1 of 2 cited -> evidence_support = 1
        ans_half = "[PRCA1991_S১৩] ভাড়া নিয়ন্ত্রক মানসম্মত ভাড়া নির্ধারণ করেন।"
        ev_half = self.rubric.evaluate(case, ans_half, "generative", supplied)
        self.assertEqual(ev_half["scores"]["evidence_support"], 1)

        # Both cited -> evidence_support = 2
        ans_both = "[PRCA1991_S১৩] ভাড়া নির্ধারণ এবং [PRCA1991_S১৮] ভাড়াটিয়া উচ্ছেদ।"
        ev_both = self.rubric.evaluate(case, ans_both, "generative", supplied)
        self.assertEqual(ev_both["scores"]["evidence_support"], 2)

    def test_hallucination_detection_on_unanswerable_failure(self):
        """Verify hallucination_detected is True when model asserts law on unanswerable query."""
        unans_case = {
            "case_id": "CASE_TEST_HALL",
            "category": "D_INSUFFICIENT_EVID",
            "target_provision_ids": [],
            "is_answerable": False,
            "expected_concepts": [],
            "prohibited_hallucinations": [],
        }
        hall_ans = "[CRPA2009_S১] এই আইন সাইবার নিরাপত্তার ব্যবস্থা করেছে।"
        ev = self.rubric.evaluate(unans_case, hall_ans, "generative", ["CRPA2009_S১"])
        self.assertEqual(ev["scores"]["factual_fidelity"], 0)
        self.assertTrue(ev["hallucination_detected"])


if __name__ == "__main__":
    unittest.main()
