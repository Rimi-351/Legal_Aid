"""
tests/test_rag.py
------------------
Pytest suite verifying Week 5 Legal RAG pipeline constraints:
1. Fabricated record_id rejected, triggers safe extractive fallback with zero rejected claims
2. Model-emitted wrong section number ignored and flagged; citation taken strictly from DB
3. Paraphrased quotes and quotes < 20 chars fail; whitespace/Unicode variant passes
4. Source URL never taken from model output
5. Invalid JSON falls back to extractive answer
6. Abstain path returns notice with zero citations
7. Leakage scan: model output containing "Section 450 of the Labour Act" in source_says does not appear in response
8. Multi-evidence_id validation: any invalid ID invalidates claim
9. Shared abstention logic:
   - Nonexistent section in query -> abstain
   - Foreign jurisdiction in query -> abstain
   - Section exists in different Act -> abstain
   - Section exists in named Act -> no abstain
   - 'fact 3' text not rejected by leakage pattern
   - Query containing bare 'us' not falsely abstained
10. Exit gate: 100% of citations match DB records and zero leakage patterns exist in model free-text answers
11. Outputs schema: eval/outputs.jsonl contains 4 conditions with exact 4 x n rows and required fields
"""
import unittest
import json
from pathlib import Path
from typing import Dict, Any, List

from src.rag.config import (
    settings,
    check_retrieval_abstention,
    extract_query_section,
    is_foreign_jurisdiction_query,
    identify_query_act,
    record_matches_act,
    LEAKAGE_PATTERN,
)
from src.rag.extractive import extractive_answer
from src.rag.llm_answer import generate_answer
from src.rag.citation_validator import validate, normalize_for_quote_match
from src.retrieval.bm25 import BM25Index


class TestLegalRAGPipeline(unittest.TestCase):

    def setUp(self):
        self.sample_db_record = {
            "record_id": "CRPA2009_S৩৭",
            "provision_id": "CRPA2009_S৩৭",
            "act_title": "ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯",
            "section_id": "৩৭",
            "section_number": "৩৭",
            "source_url": "tests/fixtures/sample_consumer_rights_2009.html",
            "source_file": "tests/fixtures/sample_consumer_rights_2009.html",
            "text": "কোন ব্যক্তি কোন পণ্যের মোড়কে পণ্য বা সেবার খুচরা বিক্রয় মূল্য, ওজন বা মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।",
            "language": "bn",
            "score": 35.0
        }
        self.evidence = [self.sample_db_record]

    def test_fabricated_record_id_rejected(self):
        """Fabricated record_id or unknown evidence_id is rejected, triggers fallback, returns extractive claims only."""
        answer = {
            "answer_sections": {"source_says": ["Penalty is 1 year."]},
            "claims": [
                {
                    "text": "Penalty is up to 1 year.",
                    "evidence_ids": ["REC_FABRICATED_999"],  # Not in retrieved set
                    "quote": "মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।"
                }
            ]
        }
        val = validate(answer, self.evidence)
        self.assertTrue(val.fallback_used)
        self.assertFalse(val.is_valid)
        self.assertEqual(len(val.rejection_log), 1)
        self.assertIn("Invalid evidence_id", val.rejection_log[0]["reasons"][0])
        # On fallback, claims[] contains only extractive answer claims, never rejected claims
        self.assertEqual(len(val.validated_claims), 1)
        self.assertTrue(val.validated_claims[0].is_valid)
        self.assertIn("fallback_extractive", val.validated_claims[0].flags)
        self.assertEqual(val.validated_claims[0].citation["record_id"], "CRPA2009_S৩৭")

    def test_model_emitted_wrong_section_number_ignored_or_flagged(self):
        """Model-emitted wrong section number is ignored/flagged; section is taken strictly from DB."""
        answer = {
            "answer_sections": {"source_says": ["Penalty is 1 year."]},
            "claims": [
                {
                    "text": "Penalty is up to 1 year.",
                    "evidence_ids": ["E1"],
                    "section_id": "999",  # Hallucinated section
                    "quote": "মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।"
                }
            ]
        }
        val = validate(answer, self.evidence)
        self.assertTrue(val.validated_claims[0].is_valid)
        self.assertEqual(val.validated_claims[0].citation["section_id"], "৩৭")
        self.assertNotEqual(val.validated_claims[0].citation["section_id"], "999")
        self.assertTrue(any("model_emitted_wrong_section" in f for f in val.validated_claims[0].flags))

    def test_paraphrased_quote_and_short_quote_fail_and_whitespace_variant_passes(self):
        """Paraphrased quotes and quotes < 20 chars fail; whitespace/Unicode normalized variants pass."""
        # 1. Exact quote passes
        exact_quote = "মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।"
        ans_exact = {
            "answer_sections": {"source_says": ["..."]},
            "claims": [{"text": "Claim 1", "evidence_ids": ["E1"], "quote": exact_quote}]
        }
        val_exact = validate(ans_exact, self.evidence)
        self.assertTrue(val_exact.validated_claims[0].is_valid)
        self.assertEqual(val_exact.validated_claims[0].match_type, "exact")

        # 2. Normalized whitespace/Unicode variant passes
        variant_quote = "মেয়াদ   উত্তীর্ণের  তারিখ   উল্লেখ না করিলে\nতিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে  দণ্ডনীয় হইবেন।"
        ans_variant = {
            "answer_sections": {"source_says": ["..."]},
            "claims": [{"text": "Claim 2", "evidence_ids": ["E1"], "quote": variant_quote}]
        }
        val_variant = validate(ans_variant, self.evidence)
        self.assertTrue(val_variant.validated_claims[0].is_valid)
        self.assertEqual(val_variant.validated_claims[0].match_type, "normalized")

        # 3. Paraphrased quote fails
        paraphrase = "দোকানদার যদি পণ্যে মেয়াদ না লেখে তবে তাকে ১ বছরের জেল দেওয়া হইবে।"
        ans_para = {
            "answer_sections": {"source_says": ["..."]},
            "claims": [{"text": "Claim 3", "evidence_ids": ["E1"], "quote": paraphrase}]
        }
        val_para = validate(ans_para, self.evidence)
        self.assertTrue(val_para.fallback_used)
        self.assertEqual(val_para.rejection_log[0]["match_type"], "fail")

        # 4. Short quote (< 20 chars) fails
        short_quote = "এক বৎসর কারাদণ্ডে"
        self.assertLess(len(normalize_for_quote_match(short_quote)), 20)
        ans_short = {
            "answer_sections": {"source_says": ["..."]},
            "claims": [{"text": "Claim 4", "evidence_ids": ["E1"], "quote": short_quote}]
        }
        val_short = validate(ans_short, self.evidence)
        self.assertTrue(val_short.fallback_used)
        self.assertIn("Quote too short", val_short.rejection_log[0]["reasons"][0])

    def test_url_never_taken_from_model_output(self):
        """Source URL is populated strictly from DB record and never taken from model output."""
        bogus_url = "https://fabricated-legal-portal.org/fake-law.html"
        answer = {
            "answer_sections": {"source_says": ["..."]},
            "claims": [
                {
                    "text": "Valid statement",
                    "evidence_ids": ["E1"],
                    "source_url": bogus_url,  # Bogus URL from model
                    "quote": "মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।"
                }
            ]
        }
        val = validate(answer, self.evidence)
        self.assertTrue(val.validated_claims[0].is_valid)
        self.assertEqual(val.validated_claims[0].citation["source_url"], "tests/fixtures/sample_consumer_rights_2009.html")
        self.assertNotEqual(val.validated_claims[0].citation["source_url"], bogus_url)
        self.assertTrue(any("model_emitted_url_ignored" in f for f in val.validated_claims[0].flags))

    def test_invalid_json_fallback_to_extractive(self):
        """Malformed JSON from model triggers retry and falls back to deterministic extractive answer."""
        def malformed_llm_mock(prompt: str) -> str:
            return "This is not valid JSON at all! {broken syntax:"

        res = generate_answer("What is the penalty?", self.evidence, lang="en", llm_caller=malformed_llm_mock)
        self.assertTrue(res.get("fallback_used"))
        self.assertTrue(res.get("parse_failure"))
        self.assertIn("summary", res)
        self.assertEqual(res.get("record_id"), "CRPA2009_S৩৭")

    def test_abstain_path_returns_notice_with_no_citations(self):
        """Low retrieval score triggers abstention notice with zero cited claims."""
        weak_evidence = [dict(self.sample_db_record, score=1.2)]  # Below threshold 5.0
        res = extractive_answer("Unknown off-topic question?", weak_evidence, lang="en", score_threshold=5.0)
        self.assertTrue(res["insufficient_evidence"])
        self.assertEqual(len(res["claims"]), 0)
        self.assertIn("Insufficient evidence", res["summary"])

    def test_leakage_in_source_says_dropped_from_response(self):
        """Model output containing 'Section 450 of the Labour Act' in source_says must not appear in response."""
        answer = {
            "answer_sections": {
                "source_says": ["Section 450 of the Labour Act prescribes penalties for illegal lockouts."],
                "relation_to_facts": ["Directly applies to employer actions."],
                "missing_facts": [],
                "uncertain": []
            },
            "claims": [
                {
                    "text": "The statutory penalty includes fines and imprisonment.",
                    "evidence_ids": ["E1"],
                    "quote": "মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।"
                }
            ]
        }
        val = validate(answer, self.evidence)
        self.assertIn("The statutory penalty includes fines and imprisonment.", val.answer["answer"])
        self.assertNotIn("Section 450 of the Labour Act", val.answer["answer"])
        self.assertNotIn("answer_sections", val.answer)
        self.assertIsNone(LEAKAGE_PATTERN.search(val.answer["answer"]))

    def test_validate_all_evidence_ids_per_claim(self):
        """Validate ALL evidence_ids per claim, not just [0]. Any invalid ID invalidates the claim."""
        answer = {
            "answer_sections": {"source_says": ["..."]},
            "claims": [
                {
                    "text": "Joint statutory claim.",
                    "evidence_ids": ["E1", "INVALID_E99"],
                    "quote": "মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।"
                }
            ]
        }
        val = validate(answer, self.evidence)
        self.assertTrue(val.fallback_used)
        self.assertEqual(len(val.rejection_log), 1)
        self.assertIn("Invalid evidence_id 'INVALID_E99'", val.rejection_log[0]["reasons"][0])

    def test_shared_abstention_logic_nonexistent_section_and_foreign_jur(self):
        """Shared abstention correctly detects nonexistent sections, foreign jurisdictions, and Act mismatches."""
        # 1. Nonexistent section in query
        q_nonexist = "What is the penalty prescribed under Section 450 of the Bangladesh Labour Act 2006?"
        should_abstain, reason = check_retrieval_abstention(q_nonexist, self.evidence, threshold=5.0)
        self.assertTrue(should_abstain)
        self.assertIn("does not exist in named Act", reason)

        # 2. Foreign jurisdiction in query
        q_foreign = "What is the limitation for contract breach under the California Civil Code?"
        should_abstain, reason = check_retrieval_abstention(q_foreign, self.evidence, threshold=5.0)
        self.assertTrue(should_abstain)
        self.assertIn("foreign jurisdiction", reason)

        # 3. Section exists in different Act -> abstain
        # Query asks about Section 37 of the Contract Act, but evidence only has Section 37 of Consumer Rights Act
        q_diff_act = "Under Section 37 of the Contract Act 1872, what are the obligations?"
        should_abstain, reason = check_retrieval_abstention(q_diff_act, self.evidence, threshold=5.0)
        self.assertTrue(should_abstain)
        self.assertIn("does not exist in named Act 'contract'", reason)

        # 4. Section exists in named Act -> no abstain
        q_same_act = "Under Section 37 of the Consumer Rights Protection Act, what is the penalty?"
        should_abstain, reason = check_retrieval_abstention(q_same_act, self.evidence, threshold=5.0)
        self.assertFalse(should_abstain)

        # 5. Word boundary check: 'fact 3' text is not rejected by leakage pattern
        self.assertIsNone(LEAKAGE_PATTERN.search("Statement of fact 3 applies to this contract."))
        self.assertIsNone(LEAKAGE_PATTERN.search("The impact 2 was significant."))

        # 6. Word boundary check: query containing English word 'us' is not treated as foreign jurisdiction
        q_us = "Can an employer dismiss us without giving statutory notice?"
        self.assertFalse(is_foreign_jurisdiction_query(q_us))

    def test_exit_gate_zero_unverified_citations_and_zero_leakage(self):
        """
        CI Exit Gate (Fix 8): Asserts that across eval/outputs.jsonl for all 4 conditions:
        1. Cited record exists in the corpus database.
        2. Cited section_id and act_title match the corpus record.
        3. For condition=extractive, cited quote appears verbatim in the corpus text.
        4. For LLM conditions without fallback, quote appears verbatim in the cited corpus text.
        5. Model free text contains ZERO unverified citations (regex scan).
        """
        db_records = {}
        with open("data/processed/provisions.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    if not p.get("is_quarantined"):
                        db_records[p["provision_id"]] = p

        outputs_path = Path("eval/outputs.jsonl")
        test_records = []
        if outputs_path.exists() and outputs_path.stat().st_size > 0:
            with open(outputs_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        test_records.append(json.loads(line))

        if not test_records:
            self.skipTest("eval/outputs.jsonl not generated yet; run evaluation first.")

        for idx, rec in enumerate(test_records):
            cond = rec.get("condition", "")
            final_ans = rec.get("final_answer", rec.get("answer", ""))
            flags = rec.get("flags", {})
            fallback_used = flags.get("fallback_used", False)
            claims = rec.get("claims", [])

            # Check 5: Model free text contains ZERO unverified citations (regex scan)
            if cond in ("llm", "llm_validated", "llm_validated_noabstain") and not fallback_used:
                self.assertIsNone(
                    LEAKAGE_PATTERN.search(final_ans),
                    f"Leakage pattern found in model free text at row {idx} ({rec.get('query_id')}): {final_ans}"
                )

            # Checks 1-4 for every claim
            for c_idx, claim in enumerate(claims):
                cit = claim.get("citation") or claim
                rid = cit.get("record_id") or claim.get("record_id")

                if rid:
                    # Check 1: Cited record exists in the corpus database
                    self.assertIn(
                        rid, db_records,
                        f"Cited record '{rid}' not found in DB at row {idx}, claim {c_idx}"
                    )
                    expected_db = db_records[rid]

                    # Check 2: Cited section_id and act_title match the corpus record
                    sec_id = cit.get("section_id") or claim.get("section_id")
                    act_t = cit.get("act_title") or claim.get("act_title")
                    self.assertEqual(
                        str(sec_id), str(expected_db.get("section_number")),
                        f"Section mismatch for {rid} at row {idx}: cit={sec_id}, db={expected_db.get('section_number')}"
                    )
                    self.assertEqual(
                        act_t, expected_db.get("act_title"),
                        f"Act title mismatch for {rid} at row {idx}: cit={act_t}, db={expected_db.get('act_title')}"
                    )

                    # Check 3: For condition=extractive, cited quote appears verbatim in the corpus text
                    if cond == "extractive":
                        quote = cit.get("quote") or claim.get("quote")
                        if quote:
                            db_text = expected_db.get("text", "")
                            self.assertIn(
                                quote, db_text,
                                f"Extractive quote not verbatim in {rid} at row {idx}: {quote}"
                            )

                    # Check 4: For LLM conditions without fallback, quote appears verbatim in the cited corpus text
                    if cond in ("llm_validated", "llm_validated_noabstain") and not fallback_used:
                        quote = cit.get("quote") or claim.get("quote")
                        if quote:
                            db_text = expected_db.get("text", "")
                            self.assertIn(
                                quote, db_text,
                                f"LLM quote not verbatim in {rid} at row {idx}: {quote}"
                            )

    def test_outputs_jsonl_schema_and_four_conditions(self):
        """Asserts eval/outputs.jsonl contains all 4 conditions and required schema fields."""
        outputs_path = Path("eval/outputs.jsonl")
        if not outputs_path.exists() or outputs_path.stat().st_size == 0:
            self.skipTest("eval/outputs.jsonl not generated yet; will be verified after eval run.")

        records = []
        with open(outputs_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        conditions_found = set(r["condition"] for r in records)
        expected_conditions = {"extractive", "llm", "llm_validated_noabstain", "llm_validated"}
        self.assertEqual(conditions_found, expected_conditions)

        # Check required schema fields on every record
        required_keys = {"condition", "query_id", "lang", "retrieved_ids", "raw_model_json", "final_answer", "claims", "flags", "latency_ms"}
        flag_keys = {"timeout", "unreachable", "parse_failure", "truncated", "schema_missing", "fallback_used"}

        for r in records:
            self.assertTrue(required_keys.issubset(r.keys()), f"Missing keys in record: {r}")
            self.assertTrue(flag_keys.issubset(r["flags"].keys()), f"Missing flags in record: {r['flags']}")

        # Verify row count = 4 x n
        n_queries = len(records) // 4
        self.assertEqual(len(records), 4 * n_queries)


if __name__ == "__main__":
    unittest.main()
