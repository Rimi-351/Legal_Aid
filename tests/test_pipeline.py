"""
tests/test_pipeline.py
----------------------
Pytest suite verifying Week 7 unified RAG pipeline and language detection:
1. Script-ratio language detection (bn, en, banglish, mixed)
2. Manual language override behavior
3. Original query preservation (never replaced with translation)
4. Full PipelineResult dataclass contract
"""
import unittest
from src.pipeline import detect_language, normalize_query_text, ask, PipelineResult


class TestPipelineUnified(unittest.TestCase):

    def test_detect_language_bengali_unicode(self):
        query = "শ্রম আইনের ধারা ২৬ অনুযায়ী ক্ষতিপূরণ কী?"
        self.assertEqual(detect_language(query), "bn")

    def test_detect_language_banglish_transliteration(self):
        query = "shrom ainer dhara 26 onujayi chatai er khotipuron ki hobe?"
        self.assertEqual(detect_language(query), "banglish")

    def test_detect_language_english(self):
        query = "What is the penalty for selling products without retail price?"
        self.assertEqual(detect_language(query), "en")

    def test_detect_language_code_mixed(self):
        query = "BLA 2006 er ধারা ২৬ এর আওতায় termination notice koto din?"
        self.assertEqual(detect_language(query), "mixed")

    def test_language_override_behavior(self):
        query = "shromik chakri theke borkhasto"  # detected as banglish
        # Manual override to 'en'
        result = ask(query, lang_override="en", mode="extractive")
        self.assertEqual(result.detected_lang, "banglish")
        self.assertTrue(result.lang_overridden)
        self.assertEqual(result.answer_lang, "en")

    def test_original_query_preserved_with_normalized(self):
        raw_query = "  শ্রম   আইনের   ধারা   ২৬   "
        result = ask(raw_query, mode="extractive")
        self.assertEqual(result.original_text, raw_query)
        self.assertEqual(result.normalized_query, "শ্রম আইনের ধারা ২৬")

    def test_pipeline_result_contract_fields(self):
        query = "What is compensation for termination under Section 26?"
        result = ask(query, mode="extractive")
        self.assertIsInstance(result, PipelineResult)
        self.assertIsInstance(result.retrieved, list)
        self.assertIsInstance(result.abstained, bool)
        self.assertIsInstance(result.fallback_used, bool)
        self.assertIsInstance(result.latency_ms, float)
        self.assertIn("statuses", result.version_status)


if __name__ == "__main__":
    unittest.main()

