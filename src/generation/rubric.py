"""
src/generation/rubric.py
------------------------
Evaluation rubric and scoring logic for legal answer generation and extractive baselines.
Evaluates 0-2 per criterion:
  0 = Failed
  1 = Partially Satisfied
  2 = Satisfied
"""

import re
from typing import Dict, Any, List, Set, Tuple, Optional


PROVISION_ID_REGEX = re.compile(
    r"\b([A-Z]{2,5}[0-9]{4}_S[০-৯0-9]+)\b|\[([A-Z]{2,5}[0-9]{4}_S[০-৯0-9]+)\]"
)

# Common abstention indicators
ABSTENTION_KEYWORDS_EN = [
    "insufficient evidence",
    "do not contain sufficient",
    "does not contain",
    "cannot be determined",
    "not established in the provided",
    "not mentioned in the provided",
    "no sufficient",
]

ABSTENTION_KEYWORDS_BN = [
    "পর্যাপ্ত তথ্য নেই",
    "পর্যাপ্ত প্রমাণ নেই",
    "পর্যাপ্ত তথ্য বা প্রমাণ নেই",
    "তথ্য বা প্রমাণ নেই",
    "অপর্যাপ্ত প্রমাণ",
    "অপর্যাপ্ত তথ্য",
    "উল্লেখ নেই",
    "পাওয়া যায়নি",
    "তথ্য অপ্রতুল",
    "আইনগত বিধান নেই",
]


class GenerationRubricEvaluator:
    """
    Computes rule-based and rubric-guided evaluation scores for legal answers.
    """

    def __init__(self, valid_corpus_pids: Optional[Set[str]] = None):
        if valid_corpus_pids is None:
            self.valid_corpus_pids = {
                "CA1872_S1", "CA1872_S2", "CA1872_S10", "CA1872_S11",
                "TPA1882_S5", "TPA1882_S54", "TPA1882_S106", "TPA1882_S107",
                "CRPA2009_S১", "CRPA2009_S৩৭", "CRPA2009_S৪৫",
                "BLA2006_S১", "BLA2006_S২০", "BLA2006_S২৬",
                "BLAA2013_S১", "BLAA2013_S৭",
                "PRCA1991_S১", "PRCA1991_S১৩", "PRCA1991_S১৮",
            }
        else:
            self.valid_corpus_pids = valid_corpus_pids

    def extract_citations(self, text: str) -> List[str]:
        """Extracts provision ID citations matching the schema format."""
        matches = PROVISION_ID_REGEX.findall(text)
        citations = []
        for m in matches:
            cid = m[0] or m[1]
            if cid:
                citations.append(cid)
        return list(dict.fromkeys(citations))  # Deduplicate preserving order

    def check_abstention(self, text: str) -> bool:
        """Determines if the response is an explicit abstention."""
        lower_text = text.lower()
        for kw in ABSTENTION_KEYWORDS_EN:
            if kw in lower_text:
                return True
        for kw in ABSTENTION_KEYWORDS_BN:
            if kw in text:
                return True
        return False

    def evaluate(
        self,
        case: Dict[str, Any],
        answer_text: str,
        condition: str,
        supplied_pids: List[str],
    ) -> Dict[str, Any]:
        """
        Scores a single case output against the 0-2 rubric criteria.
        """
        is_answerable = case.get("is_answerable", True)
        target_pids = set(case.get("target_provision_ids", []))
        expected_concepts = case.get("expected_concepts", [])
        prohibited_hallucinations = case.get("prohibited_hallucinations", [])

        citations = self.extract_citations(answer_text)
        is_abstention = self.check_abstention(answer_text)

        # 1. Citation Validity (0, 1, 2)
        # 2 = All citations exist in corpus and are in supplied evidence
        # 1 = Some valid citations, or citations formatted loosely
        # 0 = Completely hallucinated or non-existent citation IDs (when answerable)
        if not is_answerable:
            citation_validity = 2 if len(citations) == 0 else 0
        elif condition == "extractive":
            if not citations:
                citation_validity = 0
            else:
                valid_count = sum(1 for c in citations if c in self.valid_corpus_pids)
                supplied_match = sum(1 for c in citations if c in supplied_pids)
                citation_validity = 2 if (valid_count == len(citations) and supplied_match == len(citations)) else (1 if valid_count > 0 else 0)
        else:
            if not citations:
                citation_validity = 0
            else:
                valid_count = sum(1 for c in citations if c in self.valid_corpus_pids)
                if valid_count == len(citations):
                    # Check if they match supplied evidence
                    supplied_match = sum(1 for c in citations if c in supplied_pids)
                    citation_validity = 2 if supplied_match == len(citations) else 1
                elif valid_count > 0:
                    citation_validity = 1
                else:
                    citation_validity = 0

        # 2. Evidence Support (0, 1, 2)
        # Does the cited provision actually support the answer?
        if not is_answerable:
            evidence_support = 2 if is_abstention else 0
        else:
            supported_citations = set(citations).intersection(supplied_pids)
            matched_targets = supported_citations.intersection(target_pids)
            if matched_targets == target_pids:
                evidence_support = 2
            elif len(matched_targets) > 0:
                evidence_support = 1
            else:
                evidence_support = 0

        # 3. Factual Fidelity & Hallucination Check (0, 1, 2)
        # 2 = No prohibited hallucinations found, facts stay within passage
        # 0 = Hallucinated sections, penalties, or procedures found
        hallucination_found = any(h in answer_text for h in prohibited_hallucinations)
        if hallucination_found:
            factual_fidelity = 0
        elif not is_answerable and not is_abstention:
            factual_fidelity = 0
        else:
            factual_fidelity = 2

        # 4. Cross-Language Meaning Preservation (0, 1, 2)
        # For cross-lingual cases (A and B), verify key concepts survived translation
        if case.get("category") in ("A_EN_STATUTE_BN_EXP", "B_BN_STATUTE_EN_EXP"):
            if not answer_text or hallucination_found:
                cross_lang_score = 0
            else:
                # Check concepts
                concept_hits = sum(
                    1 for c in expected_concepts
                    if any(w.lower() in answer_text.lower() for w in c.split("/"))
                )
                if concept_hits >= len(expected_concepts) * 0.7:
                    cross_lang_score = 2
                elif concept_hits > 0:
                    cross_lang_score = 1
                else:
                    cross_lang_score = 0
        else:
            cross_lang_score = 2  # Not applicable or monolingual

        # 5. Completeness (0, 1, 2)
        if not is_answerable:
            completeness = 2 if is_abstention else 0
        else:
            concept_hits = sum(
                1 for c in expected_concepts
                if any(w.lower() in answer_text.lower() for w in c.split("/"))
            )
            if concept_hits == len(expected_concepts):
                completeness = 2
            elif concept_hits > 0:
                completeness = 1
            else:
                completeness = 0

        # 6. Abstention Correctness (0, 1, 2)
        if not is_answerable:
            abstention_score = 2 if is_abstention else 0
        else:
            abstention_score = 0 if is_abstention else 2

        # Overall Rubric Score (Average out of 2.0)
        rubric_scores = {
            "citation_validity": citation_validity,
            "evidence_support": evidence_support,
            "factual_fidelity": factual_fidelity,
            "cross_language_preservation": cross_lang_score,
            "completeness": completeness,
            "abstention_correctness": abstention_score,
        }
        total_score = round(sum(rubric_scores.values()) / len(rubric_scores), 2)

        return {
            "case_id": case.get("case_id"),
            "category": case.get("category"),
            "condition": condition,
            "extracted_citations": citations,
            "is_abstention": is_abstention,
            "scores": rubric_scores,
            "mean_rubric_score": total_score,
            "hallucination_detected": hallucination_found or (factual_fidelity == 0),
        }
