"""
tests/test_quote_path.py
------------------------
Unit tests for the sentence-index citation quote path:
1. Sentence splitting (Bengali dari, English periods, delimiters).
2. Quote extraction from stored evidence record via sentence index (e.g., 'E1:S2').
3. Verbatim-by-construction verification in citation_validator.py.
4. Out-of-bounds evidence and sentence index rejection.
5. Config toggle between legacy quote-copy prompt and sentence-index prompt.
"""
import pytest
from src.rag.citation_validator import (
    split_into_sentences,
    resolve_claim_quote_from_index,
    validate,
)
from src.rag.config import settings
from src.rag.llm_answer import build_prompt


def test_sentence_splitting_bengali_and_english():
    # Bengali sentences with dari (।)
    bn_text = "কোন ব্যক্তি দোষী সাব্যস্ত হইলে এক বৎসর কারাদণ্ড পাইবেন। তদুপরি তিনি অর্থদণ্ডে দণ্ডিত হইবেন। ইহা আইনের বিধান।"
    bn_sents = split_into_sentences(bn_text)
    assert len(bn_sents) == 3
    assert bn_sents[0] == "কোন ব্যক্তি দোষী সাব্যস্ত হইলে এক বৎসর কারাদণ্ড পাইবেন।"
    assert bn_sents[1] == "তদুপরি তিনি অর্থদণ্ডে দণ্ডিত হইবেন।"
    assert bn_sents[2] == "ইহা আইনের বিধান।"

    # English sentences with period (.)
    en_text = "Every worker shall be entitled to leave. This leave shall be with pay. Unauthorized absence is punishable."
    en_sents = split_into_sentences(en_text)
    assert len(en_sents) == 3
    assert en_sents[0] == "Every worker shall be entitled to leave."
    assert en_sents[1] == "This leave shall be with pay."
    assert en_sents[2] == "Unauthorized absence is punishable."

    # Empty or whitespace
    assert split_into_sentences("") == []
    assert split_into_sentences("   \n\t  ") == []


def test_resolve_claim_quote_from_index_compound_citation():
    evidence = [
        {
            "record_id": "REC_001",
            "act_title": "Labour Act, 2006",
            "section_id": "45",
            "text": "Sentence one of section 45. Sentence two detailing maternity benefits. Sentence three with penalties.",
            "source_url": "https://bdlaws.minlaw.gov.bd/act-952/section-45.html"
        }
    ]

    # Test compound format "E1:S2"
    claim_compound = {
        "text": "Maternity benefits are detailed in the provision.",
        "evidence_id": "E1:S2"
    }
    resolved = resolve_claim_quote_from_index(claim_compound, evidence)
    assert resolved.get("_verbatim_by_construction") is True
    assert resolved.get("quote") == "Sentence two detailing maternity benefits."
    assert resolved.get("evidence_ids") == ["E1"]
    assert resolved.get("_extracted_sentence_idx") == 2


def test_resolve_claim_quote_from_index_separate_fields():
    evidence = [
        {
            "record_id": "REC_BN_001",
            "act_title": "ভোক্তা অধিকার",
            "section_id": "৩৭",
            "text": "দোকানদার পণ্যের মূল্য তালিকা প্রদর্শন করিবেন। অন্যথায় তিনি কারাদণ্ডে দণ্ডিত হইবেন।",
            "source_url": "test_url"
        }
    ]

    # Test separate fields: evidence_id="E1", sentence_index=1
    claim_separate = {
        "text": "দোকানদারকে মূল্য তালিকা টানাতে হবে।",
        "evidence_id": "E1",
        "sentence_index": 1
    }
    resolved = resolve_claim_quote_from_index(claim_separate, evidence)
    assert resolved.get("_verbatim_by_construction") is True
    assert resolved.get("quote") == "দোকানদার পণ্যের মূল্য তালিকা প্রদর্শন করিবেন।"
    assert resolved.get("evidence_ids") == ["E1"]


def test_verbatim_by_construction_validation_pass():
    evidence = [
        {
            "record_id": "REC_001",
            "act_title": "Labour Act, 2006",
            "section_id": "45",
            "text": "Sentence one of section 45. Sentence two detailing maternity benefits.",
            "source_url": "https://bdlaws.minlaw.gov.bd/act-952/section-45.html"
        }
    ]
    raw_answer = {
        "claims": [
            {
                "text": "The law provides maternity benefit rules.",
                "evidence_id": "E1:S2"
            }
        ]
    }

    val_res = validate(raw_answer, evidence, query="maternity benefits", lang="en")
    assert val_res.fallback_used is False
    assert len(val_res.validated_claims) == 1
    vc = val_res.validated_claims[0]
    assert vc.is_valid is True
    assert vc.match_type == "exact"
    assert "verbatim_by_construction" in vc.flags
    assert vc.citation is not None
    assert vc.citation.get("quote") == "Sentence two detailing maternity benefits."
    assert vc.citation.get("section_id") == "45"
    assert vc.citation.get("act_title") == "Labour Act, 2006"


def test_out_of_bounds_index_rejection():
    evidence = [
        {
            "record_id": "REC_001",
            "act_title": "Labour Act, 2006",
            "section_id": "45",
            "text": "Single sentence in section 45.",
            "source_url": "test_url"
        }
    ]

    # Sentence index 99 is out of range
    raw_bad_sentence = {
        "claims": [
            {
                "text": "Bad sentence index claim.",
                "evidence_id": "E1:S99"
            }
        ]
    }
    val_res_s = validate(raw_bad_sentence, evidence, query="test", lang="en")
    assert val_res_s.fallback_used is True
    assert len(val_res_s.rejection_log) == 1
    assert "out of range" in str(val_res_s.rejection_log[0]["reasons"])

    # Evidence index E9 is out of range
    raw_bad_evidence = {
        "claims": [
            {
                "text": "Bad evidence index claim.",
                "evidence_id": "E9:S1"
            }
        ]
    }
    val_res_e = validate(raw_bad_evidence, evidence, query="test", lang="en")
    assert val_res_e.fallback_used is True
    assert len(val_res_e.rejection_log) == 1
    assert "out of range" in str(val_res_e.rejection_log[0]["reasons"])


def test_config_toggle_prompt_format():
    evidence = [
        {
            "record_id": "REC_001",
            "act_title": "Test Act",
            "section_id": "1",
            "text": "First sentence. Second sentence.",
            "source_url": "url"
        }
    ]

    orig_val = settings.use_sentence_index_citations
    try:
        # 1. When use_sentence_index_citations is True
        object.__setattr__(settings, "use_sentence_index_citations", True)
        prompt_indexed = build_prompt("what is penalty?", evidence, lang="en")
        assert "[E1:S1]" in prompt_indexed
        assert "[E1:S2]" in prompt_indexed
        assert "E1:S1" in prompt_indexed
        assert "Do NOT copy quotes" in prompt_indexed

        # 2. When use_sentence_index_citations is False (legacy quote copy)
        object.__setattr__(settings, "use_sentence_index_citations", False)
        prompt_legacy = build_prompt("what is penalty?", evidence, lang="en")
        assert "[E1:S1]" not in prompt_legacy
        assert '"quote":' in prompt_legacy
        assert "exact verbatim substring" in prompt_legacy
    finally:
        object.__setattr__(settings, "use_sentence_index_citations", orig_val)
