"""
tests/test_ingestion.py
-----------------------
Unit tests for legal document ingestion, Unicode preservation, section parsing,
quarantine detection, and stable identifier generation.
"""

import unittest
import tempfile
import hashlib
from pathlib import Path

from src.ingestion.normalizer import (
    normalize_bengali_english_text,
    detect_suspect_bijoy,
    detect_language
)
from src.ingestion.parser import (
    Provision,
    compute_sha256,
    derive_act_code,
    LegalDocumentParser
)


class TestIngestionNormalizer(unittest.TestCase):

    def test_unicode_normalization_nfc(self):
        """Verify conservative NFC normalization preserves Bengali conjuncts and strips orphan ZWNJ."""
        # Decomposed form vs Composed form
        text_with_nbsp = "ধারা\u00a0৫।\u200b চুক্তির\u00a0শর্ত।"
        normalized = normalize_bengali_english_text(text_with_nbsp)
        self.assertNotIn("\u00a0", normalized)
        self.assertNotIn("\u200b", normalized)
        self.assertIn("ধারা ৫।", normalized)
        self.assertIn("চুক্তির", normalized)

        # Conjunct preservation (ক্ষ = ক + ্ + ষ)
        conjunct = "ক্ষতিপূরণ ও বিশেষজ্ঞ"
        norm_conjunct = normalize_bengali_english_text(conjunct)
        self.assertEqual(norm_conjunct, conjunct)

    def test_suspect_bijoy_detection(self):
        """Verify Bijoy (SutonnyMJ ASCII layout) signatures are detected."""
        bijoy_text = "GB AvBb evsjv‡`k m¤úwË AvBbvbyhvqx cÖavb weavb|"
        is_suspect, found = detect_suspect_bijoy(bijoy_text)
        self.assertTrue(is_suspect)
        self.assertGreaterEqual(len(found), 2)
        self.assertIn("AvBb", found)
        self.assertIn("evsjv‡`k", found)

        # Standard clean Unicode Bengali should NOT trigger suspect Bijoy
        clean_bn = "এই আইনটি বাংলাদেশ শ্রম আইন হিসেবে পরিচিত হইবে।"
        is_clean, clean_found = detect_suspect_bijoy(clean_bn)
        self.assertFalse(is_clean)
        self.assertEqual(len(clean_found), 0)

    def test_language_detection(self):
        """Verify accurate categorization of bn, en, and mixed scripts."""
        bn_text = "ধারা ২৫। কোনো চুক্তি অকার্যকর হইবে যদি উহার উদ্দেশ্য বেআইনি হয়।"
        en_text = "Section 25. An agreement made without consideration is void."
        mixed_text = "Section 25: চুক্তি বা Agreement সংক্রান্ত বিধান।"

        self.assertEqual(detect_language(bn_text), "bn")
        self.assertEqual(detect_language(en_text), "en")
        self.assertEqual(detect_language(mixed_text), "mixed")


class TestDocumentParser(unittest.TestCase):

    def setUp(self):
        self.parser = LegalDocumentParser()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sha256_computation(self):
        """Verify SHA-256 digest computation matches Python standard hashlib."""
        test_file = self.temp_path / "test_doc.txt"
        test_content = b"Bangladesh Legal Aid Research Pipeline Week 1"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        computed_hash = compute_sha256(test_file)
        self.assertEqual(computed_hash, expected_hash)

    def test_derive_act_code(self):
        """Verify stable Act codes for statutory domains."""
        self.assertEqual(derive_act_code("The Contract Act, 1872", Path("act.html")), "CA1872")
        self.assertEqual(derive_act_code("ভোক্তা অধিকার সংরক্ষণ আইন, ২০০৯", Path("act.html")), "CRPA2009")
        self.assertEqual(derive_act_code("বাংলাদেশ শ্রম আইন, ২০০৬", Path("act.html")), "BLA2006")
        self.assertEqual(derive_act_code("The Transfer of Property Act, 1882", Path("act.html")), "TPA1882")
        self.assertEqual(derive_act_code("The Specific Relief Act, 1877", Path("act.html")), "SRA1877")

    def test_html_parsing_and_stable_id(self):
        """Verify HTML document parses sections with deterministic IDs and preserved metadata."""
        sample_html = """<!DOCTYPE html>
<html>
<head><title>The Contract Act, 1872</title></head>
<body>
    <div class="act-title">The Contract Act, 1872</div>
    <div class="act-no">Act No. IX of 1872</div>
    <div class="section">
        <h3 class="sec-title">Section 10. What agreements are contracts</h3>
        <p class="sec-text">All agreements are contracts if they are made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object.</p>
    </div>
    <div class="section">
        <h3 class="sec-title">Section 25. Agreement without consideration, void</h3>
        <p class="sec-text">An agreement made without consideration is void, unless it is in writing and registered.</p>
    </div>
</body>
</html>"""
        html_file = self.temp_path / "sample_contract.html"
        html_file.write_text(sample_html, encoding="utf-8")

        provisions = self.parser.parse_file(html_file)
        self.assertGreaterEqual(len(provisions), 2)

        p10 = next((p for p in provisions if p.section_number == "10"), None)
        self.assertIsNotNone(p10)
        self.assertEqual(p10.provision_id, "CA1872_S10")
        self.assertEqual(p10.act_title, "The Contract Act, 1872")
        self.assertIn("free consent", p10.text)
        self.assertFalse(p10.is_quarantined)

        p25 = next((p for p in provisions if p.section_number == "25"), None)
        self.assertIsNotNone(p25)
        self.assertEqual(p25.provision_id, "CA1872_S25")
        self.assertIn("without consideration is void", p25.text)

    def test_quarantined_source_handling(self):
        """Verify corrupted or legacy-encoded documents are quarantined with explicit reasons."""
        corrupted_bijoy = "AvBb m¤úwË evsjv‡`k weavb weavbweavb " * 5
        bijoy_file = self.temp_path / "legacy_bijoy.html"
        bijoy_file.write_text(corrupted_bijoy, encoding="utf-8")

        provisions = self.parser.parse_file(bijoy_file)
        self.assertEqual(len(provisions), 1)
        self.assertTrue(provisions[0].is_quarantined)
        self.assertIn("QUARANTINED", provisions[0].provision_id.upper())
        self.assertIn("Bijoy", provisions[0].quarantine_reason)


if __name__ == "__main__":
    unittest.main()
