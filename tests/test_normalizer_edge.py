"""
tests/test_normalizer_edge.py
-----------------------------
Unit tests for text normalization, Unicode edge cases, and language detection
in src/ingestion/normalizer.py. Verifies idempotency, numeral preservation,
ZWJ/ZWNJ handling, and code-mixed/Banglish detection.
"""
import pytest

from src.ingestion.normalizer import (
    normalize_bengali_english_text,
    detect_language,
    detect_suspect_bijoy,
)


@pytest.mark.parametrize(
    "raw_input, expected",
    [
        ("ধারা   ৩৭", "ধারা ৩৭"),
        ("ধারা  \t\t ৩৭  \n", "ধারা ৩৭"),
        ("Section   37", "Section 37"),
        ("Section  18  (1) (a)", "Section 18 (1) (a)"),
        ("ধারা ২৬(ক)", "ধারা ২৬(ক)"),
    ],
)
def test_section_numbers_and_numerals_preserved(raw_input: str, expected: str):
    """
    Risk: Bengali and ASCII numerals in statutory section headings and references
    must not be altered, transliterated, or corrupted by normalization.
    Whitespace must be collapsed cleanly.
    """
    normalized = normalize_bengali_english_text(raw_input)
    assert normalized == expected


def test_orphaned_zwnj_zwj_stripped():
    """
    Risk: Orphaned Zero-Width Non-Joiner (U+200C) and Joiner (U+200D) between
    Latin letters or at boundary edges cause invisible tokenization mismatches.
    They must be stripped when not touching Bengali characters.
    """
    # Orphaned in Latin words
    assert normalize_bengali_english_text("Doc\u200cument") == "Document"
    assert normalize_bengali_english_text("Test\u200dCode") == "TestCode"
    # Bare joiners
    assert normalize_bengali_english_text("\u200c\u200d") == ""
    # Touching Latin punctuation
    assert normalize_bengali_english_text("Section 37:\u200c") == "Section 37:"


def test_zwnj_zwj_preserved_between_bengali_characters():
    """
    Risk: Legitimate Bengali conjuncts and ligatures (e.g. ক্+ষ, র্+য) rely on
    ZWJ/ZWNJ for correct typographic rendering and must NOT be stripped.
    """
    # ক (U+0995) + ZWJ (U+200D) + ষ (U+09B7)
    bengali_with_zwj = "\u0995\u200d\u09b7"
    assert normalize_bengali_english_text(bengali_with_zwj) == bengali_with_zwj

    # র (U+09B0) + ZWNJ (U+200C) + ্ (U+09CD) + য (U+09AF)
    bengali_with_zwnj = "\u09b0\u200c\u09cd\u09af"
    assert normalize_bengali_english_text(bengali_with_zwnj) == bengali_with_zwnj


def test_mixed_script_normalization():
    """
    Risk: Mixed Bengali-English legal queries and statutory text must preserve
    both scripts without mangling casing, numbers, or Bengali punctuation.
    """
    mixed_text = "The Contract Act, 1872 এর Section 27 অনুযায়ী চুক্তি বাতিল হইবে।"
    normalized = normalize_bengali_english_text(mixed_text)
    assert normalized == mixed_text


@pytest.mark.parametrize("short_input", ["", " ", "\t\n", "a", "১", "।", "॥"])
def test_very_short_and_empty_queries(short_input: str):
    """
    Risk: Boundary queries of length 0, 1, or containing only whitespace or dari
    must not cause indexing errors, regex crashes, or out-of-range slice exceptions.
    """
    result = normalize_bengali_english_text(short_input)
    assert isinstance(result, str)
    if not short_input.strip() or short_input in (" ", "\t\n"):
        assert result == ""


@pytest.mark.parametrize(
    "sample_text",
    [
        "কোন ব্যক্তি কোন পণ্যের মোড়কে খুচরা বিক্রয় মূল্য উল্লেখ না করিলে...",
        "Section 27: Every agreement by which any one is restrained from trade is void.",
        "Labour Act, 2006 (২০০৬ সনের ৪২ নং আইন) এর ধারা ২৬(১)।",
        "  \n\n\n  একাধিক   স্পেস    এবং   লাইন   ব্রেক   ।  \n\n\n",
        "Normal Latin text with 123 numbers and punctuation!",
    ],
)
def test_normalizer_idempotency(sample_text: str):
    """
    Risk: Normalizing an already normalized text must be an identity operation:
    f(f(x)) == f(x). Non-idempotent normalizers cause drift during pipeline passes.
    """
    first_pass = normalize_bengali_english_text(sample_text)
    second_pass = normalize_bengali_english_text(first_pass)
    assert first_pass == second_pass


@pytest.mark.parametrize(
    "text, expected_lang",
    [
        ("ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯ এর বিধানাবলী", "bn"),
        ("The Bangladesh Labour Act 2006 termination provisions and notice requirements", "en"),
        ("Labour Act 2006 এর ধারা ২৬ অনুযায়ী কত দিনের নোটিশ দিতে হবে?", "mixed"),
        ("Contract Act ১৮৭২ এর ধারা ২৭", "mixed"),
        ("Section 18 of the Premises Rent Control Act ১৯৯১", "en"),  # Bengali numerals < 15% ratio
        ("Amar barir bhara koto taka hote pare?", "en"),  # Banglish in Latin script
        ("Bariwala jodi notice chara barite dhuke pore tahole ki korbo?", "en"),
        ("", "empty"),
    ],
)
def test_detect_language_classification(text: str, expected_lang: str):
    """
    Risk: Query routing depends on language classification. Pure Bangla must
    yield 'bn', pure English 'en', mixed Bengali-English 'mixed', and Banglish
    (Bengali semantics written in Latin script) must classify as 'en' (Latin script).
    """
    assert detect_language(text) == expected_lang


def test_detect_suspect_bijoy_ascii_encoding():
    """
    Risk: Documents encoded in legacy ASCII Bijoy (SutonnyMJ) produce gibberish
    when treated as Unicode. The detector must identify Bijoy signature n-grams.
    """
    # Text with 2 or more distinct Bijoy signatures (e.g. 'AvBb' and 'evsjv‡`k')
    bijoy_text = "GB AvBb evsjv‡`k Gi mKj ¯’v‡b cÖ‡hvR¨ nB‡e|"
    is_suspect, found_sigs = detect_suspect_bijoy(bijoy_text)
    assert is_suspect is True
    assert len(found_sigs) >= 2

    # Clean Unicode Bengali must NOT be flagged as Bijoy
    clean_unicode = "এই আইন সমগ্র বাংলাদেশে কার্যকর হইবে।"
    is_clean, found_clean = detect_suspect_bijoy(clean_unicode)
    assert is_clean is False
    assert found_clean == []
