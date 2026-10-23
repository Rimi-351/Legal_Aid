"""
src/generation/extractive.py
----------------------------
Condition A: Deterministic Extractive Baseline.
Returns retrieved statutory provisions verbatim with complete provenance,
without inferring or synthesizing legal text.
"""

from typing import List, Dict, Any, Optional


class ExtractiveBaselineGenerator:
    """
    Produces deterministic extractive outputs directly from retrieved provisions.
    """

    INSUFFICIENT_EVIDENCE_MSG_EN = (
        "The retrieved passages do not contain sufficient evidence to answer this legal question."
    )
    INSUFFICIENT_EVIDENCE_MSG_BN = (
        "সরবরাহকৃত আইনগত ধারাগুলোতে এই প্রশ্নের উত্তর দেওয়ার মতো পর্যাপ্ত তথ্য বা প্রমাণ নেই।"
    )

    def generate(
        self,
        query: str,
        provisions: List[Dict[str, Any]],
        query_language: str = "en",
        score_threshold: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Formats retrieved provisions verbatim with full provenance.
        """
        # If no provisions or explicitly marked unanswerable
        if not provisions:
            msg = (
                self.INSUFFICIENT_EVIDENCE_MSG_BN
                if query_language.lower() in ("bn", "banglish")
                else self.INSUFFICIENT_EVIDENCE_MSG_EN
            )
            return {
                "answer": msg,
                "is_abstention": True,
                "cited_provision_ids": [],
                "passages_count": 0,
            }

        cited_ids = []
        formatted_blocks = []

        for idx, prov in enumerate(provisions, 1):
            pid = prov.get("provision_id", "")
            act = prov.get("act_title", "")
            sec = prov.get("section_number", "")
            heading = prov.get("section_heading", "")
            text = prov.get("text", "").strip()
            source_file = prov.get("source_file", "")

            if pid:
                cited_ids.append(pid)

            block = (
                f"[Provision {idx}: {pid}]\n"
                f"Act: {act}\n"
                f"Section: {sec} ({heading})\n"
                f"Source: {source_file}\n"
                f"Text:\n{text}"
            )
            formatted_blocks.append(block)

        full_answer = "\n\n---\n\n".join(formatted_blocks)

        return {
            "answer": full_answer,
            "is_abstention": False,
            "cited_provision_ids": cited_ids,
            "passages_count": len(provisions),
        }
