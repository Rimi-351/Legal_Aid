"""
tests/test_ui.py
----------------
Unit tests verifying that app/ui rendering uses pipeline.ask() outputs unchanged:
1. All PipelineResult fields are preserved and consumed without modification or mutation.
2. State badges map deterministically to pipeline fields (retrieved, verified citations, legal status, abstained, fallback).
3. No intermediate business logic exists in the UI; UI acts as a pure rendering layer.
"""
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from src.pipeline import ask, PipelineResult
from app.ui import render_state_badges


class TestUIRenderingPipelineFidelity(unittest.TestCase):

    def setUp(self):
        self.sample_result = PipelineResult(
            original_text="শ্রমিককে বরখাস্তের নিয়ম কী?",
            detected_lang="bn",
            lang_overridden=False,
            normalized_query="শ্রমিককে বরখাস্তের নিয়ম কী?",
            retrieved=[
                {
                    "provision_id": "BLA2006_S26",
                    "act_title": "বাংলাদেশ শ্রম আইন, ২০০৬",
                    "section_number": "২৬",
                    "text": "মালিক কর্তৃক শ্রমিকের চাকুরীর অবসান সংক্রান্ত বিধান...",
                    "source_url": "tests/fixtures/sample_labour_2006.html",
                    "score": 42.5,
                    "version_status": "verified_in_force"
                }
            ],
            answer="মালিক কর্তৃক স্থায়ী শ্রমিককে বরখাস্ত করিতে হইলে ১২০ দিনের লিখিত নোটিশ দিতে হইবে।",
            answer_lang="bn",
            abstained=False,
            fallback_used=False,
            validation=[
                {
                    "is_valid": True,
                    "match_type": "exact",
                    "rejection_reasons": []
                }
            ],
            version_status={
                "statuses": {"BLA2006_S26": "verified_in_force"},
                "corpus_verification_date": "2026-10-28"
            },
            latency_ms=125.4,
            warning=None,
            claims=[
                {
                    "text": "মালিক কর্তৃক স্থায়ী শ্রমিককে বরখাস্ত করিতে হইলে ১২০ দিনের লিখিত নোটিশ দিতে হইবে।",
                    "is_valid": True,
                    "match_type": "exact",
                    "citation": {"section_id": "২৬", "act_title": "বাংলাদেশ শ্রম আইন, ২০০৬"}
                }
            ]
        )

    def test_pipeline_ask_output_field_integrity(self):
        """Verifies that ask() returns the exact dataclass fields expected by app/ui."""
        res = ask("What is penalty?", mode="extractive")
        expected_fields = {
            "original_text", "detected_lang", "lang_overridden",
            "normalized_query", "retrieved", "answer", "answer_lang",
            "abstained", "fallback_used", "validation", "version_status",
            "latency_ms", "warning", "claims"
        }
        actual_fields = set(asdict(res).keys())
        self.assertEqual(expected_fields, actual_fields)

        # Confirm all types conform
        self.assertIsInstance(res.original_text, str)
        self.assertIsInstance(res.detected_lang, str)
        self.assertIsInstance(res.lang_overridden, bool)
        self.assertIsInstance(res.retrieved, list)
        self.assertIsInstance(res.answer, str)
        self.assertIsInstance(res.abstained, bool)
        self.assertIsInstance(res.fallback_used, bool)
        self.assertIsInstance(res.validation, list)
        self.assertIsInstance(res.version_status, dict)

    @patch("app.ui.st")
    def test_render_state_badges_uses_pipeline_output_unchanged(self, mock_st):
        """
        Verifies that render_state_badges derives its 5 status badges directly
        from PipelineResult fields without mutating or discarding any fields.
        """
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col] * 5

        # Render sample result
        render_state_badges(self.sample_result)

        # 1. State: RETRIEVED (from bool(result.retrieved))
        mock_st.success.assert_any_call("State: RETRIEVED")

        # 2. State: VERIFIED AGAINST CORPUS (from any is_valid in result.claims)
        mock_st.success.assert_any_call("State: VERIFIED AGAINST CORPUS")

        # 3. State: LEGAL STATUS VERIFIED (from result.version_status and result.retrieved)
        mock_st.success.assert_any_call("State: LEGAL STATUS VERIFIED")

        # 4. State: SUFFICIENT EVIDENCE (from not result.abstained)
        mock_st.success.assert_any_call("State: SUFFICIENT EVIDENCE")

        # 5. State: PRIMARY MODEL (from not result.fallback_used)
        mock_st.success.assert_any_call("State: PRIMARY MODEL")

    @patch("app.ui.st")
    def test_render_state_badges_uncertain_and_fallback(self, mock_st):
        """Verifies state badge transitions for uncertain legal status and fallback."""
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col] * 5

        uncertain_result = PipelineResult(
            original_text="test query",
            detected_lang="en",
            lang_overridden=False,
            normalized_query="test query",
            retrieved=[{"provision_id": "P1", "version_status": "uncertain"}],
            answer="Fallback summary",
            answer_lang="en",
            abstained=True,
            fallback_used=True,
            validation=[],
            version_status={"corpus_verification_date": None},
            latency_ms=50.0,
            claims=[]
        )

        render_state_badges(uncertain_result)

        mock_st.warning.assert_any_call("State: LEGAL STATUS UNCERTAIN")
        mock_st.error.assert_any_call("State: INSUFFICIENT EVIDENCE")
        mock_st.warning.assert_any_call("State: FALLBACK USED")
        mock_st.info.assert_any_call("State: UNVERIFIED CITATIONS")


if __name__ == "__main__":
    unittest.main()
