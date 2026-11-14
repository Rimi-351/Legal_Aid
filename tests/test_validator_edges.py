"""
tests/test_validator_edges.py
-----------------------------
Unit tests for boundary and edge-case handling in deterministic citation validation
(src/rag/citation_validator.py) and local generation fallback (src/rag/llm_answer.py).
Verifies Unicode NFC/NFD tolerance, sentence boundary crossing, short quote rejections,
schema anomalies, empty model responses, and timeout mid-generation.
"""
import unicodedata
import socket
import pytest

from src.rag.citation_validator import validate, normalize_for_quote_match
from src.rag.llm_answer import generate_answer


@pytest.fixture
def statutory_evidence():
    """Provides verified statutory evidence records for citation testing."""
    return [
        {
            "record_id": "CRPA2009_S37",
            "provision_id": "CRPA2009_S37",
            "act_title": "ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯",
            "section_id": "৩৭",
            "section_number": "৩৭",
            "source_url": "laws_of_bangladesh/crpa2009.html",
            "source_file": "laws_of_bangladesh/crpa2009.html",
            "text": "কোন ব্যক্তি কোন পণ্যের মোড়কে পণ্য বা সেবার খুচরা বিক্রয় মূল্য, ওজন বা মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।",
            "language": "bn",
            "score": 45.0,
        },
        {
            "record_id": "BLA2006_S26",
            "provision_id": "BLA2006_S26",
            "act_title": "বাংলাদেশ শ্রম আইন, ২০০৬",
            "section_id": "২৬",
            "section_number": "২৬",
            "source_url": "laws_of_bangladesh/bla2006.html",
            "source_file": "laws_of_bangladesh/bla2006.html",
            "text": "মালিক কর্তৃক স্থায়ী শ্রমিকের চাকরি অবসান করিতে হইলে লিখিত নোটিশ প্রদান করিতে হইবে। নোটিশের পরিবর্তে মজুরি প্রদান করিয়াও চাকরি অবসান করা যাইবে।",
            "language": "bn",
            "score": 40.0,
        },
    ]


def test_bangla_quote_unicode_nfd_matches_nfc_passage(statutory_evidence):
    """
    Risk: LLMs or foreign environments may emit Bengali quotes in NFD (decomposed)
    normalization form. Since corpus text is stored in NFC, exact string equality fails.
    Validator must normalize both to NFC and grant 'normalized' match.
    """
    # Ensure evidence text is NFC normalized
    evidence_text = unicodedata.normalize("NFC", statutory_evidence[0]["text"])
    statutory_evidence[0]["text"] = evidence_text
    assert unicodedata.is_normalized("NFC", evidence_text)

    # Substring in NFC form (length > 20 chars)
    nfc_substring = unicodedata.normalize("NFC", "কোন ব্যক্তি কোন পণ্যের মোড়কে পণ্য বা সেবার খুচরা বিক্রয় মূল্য")
    assert nfc_substring in evidence_text

    # Decompose into NFD form
    nfd_quote = unicodedata.normalize("NFD", nfc_substring)
    assert not unicodedata.is_normalized("NFC", nfd_quote)
    # Direct substring check fails across different normalization forms
    assert nfd_quote not in evidence_text

    llm_output = {
        "claims": [
            {
                "text": "পণ্যের মোড়কে বিক্রয় মূল্য উল্লেখ না করিলে শাস্তি হইবে।",
                "evidence_ids": ["E1"],
                "quote": nfd_quote,
            }
        ]
    }

    result = validate(llm_output, statutory_evidence)
    assert result.is_valid is True
    assert result.fallback_used is False
    assert len(result.validated_claims) == 1
    assert result.validated_claims[0].is_valid is True
    assert result.validated_claims[0].match_type == "normalized"


def test_quote_spanning_sentence_boundary(statutory_evidence):
    """
    Risk: Quotes that span across sentence delimiters (Bengali dari '।') must
    still validate as normalized substrings of the passage rather than being rejected.
    """
    # Quote spanning sentence 1 and sentence 2 across dari '।'
    spanning_quote = "লিখিত নোটিশ প্রদান করিতে হইবে। নোটিশের পরিবর্তে মজুরি প্রদান"
    assert len(spanning_quote) >= 20

    llm_output = {
        "claims": [
            {
                "text": "মালিক নোটিশ অথবা বিকল্পে মজুরি প্রদান করিতে পারেন।",
                "evidence_ids": ["E2"],
                "quote": spanning_quote,
            }
        ]
    }

    result = validate(llm_output, statutory_evidence)
    assert result.is_valid is True
    assert result.fallback_used is False
    assert result.validated_claims[0].is_valid is True
    assert result.validated_claims[0].match_type in ("exact", "normalized")


def test_very_short_quotes_rejected_under_20_chars(statutory_evidence):
    """
    Risk: Short quotes (< 20 characters after normalization) lack sufficient
    context to ground legal assertions and could match spurious common phrases.
    They must be rejected, triggering safe extractive fallback.
    """
    short_quote = "দণ্ডনীয় হইবেন"  # 13 chars
    assert len(normalize_for_quote_match(short_quote)) < 20

    llm_output = {
        "claims": [
            {
                "text": "আইন অমান্য করিলে শাস্তি পাইবেন।",
                "evidence_ids": ["E1"],
                "quote": short_quote,
            }
        ]
    }

    result = validate(llm_output, statutory_evidence, query="শাস্তি কি?")
    assert result.is_valid is False
    assert result.fallback_used is True
    # Rejection log must cite quote length
    assert any("Quote too short" in reason for reason in result.rejection_log[0]["reasons"])


def test_llm_json_extra_and_unexpected_fields(statutory_evidence):
    """
    Risk: LLMs often emit extra unexpected fields (e.g. reasoning, confidence, scratchpad).
    Validator must ignore extraneous keys without failing or throwing KeyError.
    """
    valid_quote = statutory_evidence[0]["text"][:45]
    llm_output = {
        "claims": [
            {
                "text": "দণ্ডনীয় অপরাধ সংক্রান্ত বিধান।",
                "evidence_ids": ["E1"],
                "quote": valid_quote,
                "extra_model_scratchpad": "Thinking process...",
                "confidence_score": 0.98,
            }
        ],
        "model_temperature": 0.0,
        "unexpected_metadata": {"tokens": 150},
    }

    result = validate(llm_output, statutory_evidence)
    assert result.is_valid is True
    assert result.fallback_used is False
    assert result.validated_claims[0].is_valid is True


def test_llm_json_missing_claims_field(statutory_evidence):
    """
    Risk: LLM responses missing the required 'claims' key must not crash with
    KeyError, but must safely fall back to extractive answers.
    """
    malformed_output = {
        "answer_sections": {
            "source_says": ["Some summary without claims array."]
        }
    }

    result = validate(malformed_output, statutory_evidence, query="অপরাধের শাস্তি কি?")
    assert result.is_valid is False
    assert result.fallback_used is True


def test_empty_llm_output_dict_triggers_extractive_fallback(statutory_evidence):
    """
    Risk: Empty dictionary output from LLM ({}) must gracefully trigger
    safe extractive fallback without throwing exceptions.
    """
    result = validate({}, statutory_evidence, query="শাস্তি কি?")
    assert result.is_valid is False
    assert result.fallback_used is True
    assert "answer" in result.answer


def test_empty_string_llm_output_handled_in_generation(statutory_evidence):
    """
    Risk: Empty string response from LLM backend causes JSON decode failure.
    generate_answer must retry, detect parse failure, and return extractive fallback.
    """
    def empty_caller(prompt: str) -> str:
        return ""

    res = generate_answer("শাস্তি কি?", statutory_evidence, lang="bn", llm_caller=empty_caller)
    assert res.get("fallback_used") is True
    assert res.get("parse_failure") is True
    assert "summary" in res


def test_timeout_mid_generation_handled_cleanly(statutory_evidence):
    """
    Risk: Network or socket timeout mid-generation must be trapped cleanly
    and flagged as timeout in metadata without unhandled exceptions.
    """
    def timeout_caller(prompt: str) -> str:
        raise TimeoutError("Socket read timed out after 300s")

    res = generate_answer("নোটিশের নিয়ম কি?", statutory_evidence, lang="bn", llm_caller=timeout_caller)
    assert res.get("fallback_used") is True
    assert res.get("timeout") is True
    assert res.get("unreachable") is False
    assert "summary" in res

    # If timeout payload without claims reaches validator, it safely falls back
    raw_timeout_payload = {"timeout": True, "error": "timeout"}
    val = validate(raw_timeout_payload, statutory_evidence, query="নোটিশের নিয়ম কি?", lang="bn")
    assert val.fallback_used is True
