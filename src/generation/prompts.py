"""
src/generation/prompts.py
-------------------------
Fixed prompt templates and strict evidence grounding instructions for legal answer generation.
"""

from typing import List, Dict, Any

LEGAL_SYSTEM_PROMPT = """You are an evidence-grounded legal assistant specializing in Bangladesh statutory law.
Your task is to provide accurate, concise legal explanations based STRICTLY and ONLY on the provided legal passages.

CRITICAL INSTRUCTIONS:
1. Base all substantive claims SOLELY on the provided passages.
2. For each claim, cite the exact Provision ID in brackets, e.g. [CA1872_S11] or [CRPA2009_S৩৭].
3. If the provided passages DO NOT contain sufficient information to answer the question, you MUST explicitly state: "The provided legal passages do not contain sufficient evidence to answer this question."
4. DO NOT invent, extrapolate, or hallucinate legal sections, act titles, penalties, limitation periods, court rules, or procedures not present in the text.
5. Distinguish what the passage explicitly says from what is not established.
6. Answer in the language requested by the query (Bangla questions in Bangla, English in English, Banglish in clear Bangla or English).
"""

USER_PROMPT_TEMPLATE = """Below are the relevant legal passages retrieved from Bangladesh statutory sources:

--- EVIDENCE START ---
{evidence_block}
--- EVIDENCE END ---

QUESTION:
{query}

Provide a concise, evidence-grounded legal explanation citing the relevant Provision ID for each claim. If the evidence is insufficient, explicitly state so."""


def format_evidence_block(provisions: List[Dict[str, Any]]) -> str:
    """Formats retrieved provisions into a clean structured evidence text block."""
    if not provisions:
        return "[No legal passages available]"

    blocks = []
    for idx, prov in enumerate(provisions, 1):
        pid = prov.get("provision_id", "UNKNOWN_ID")
        act = prov.get("act_title", "Unknown Act")
        sec = prov.get("section_number", "")
        heading = prov.get("section_heading", "")
        text = prov.get("text", "").strip()

        block = (
            f"Passage {idx} [ID: {pid}]:\n"
            f"Act: {act}\n"
            f"Section: {sec} - {heading}\n"
            f"Statutory Text:\n{text}\n"
        )
        blocks.append(block)

    return "\n".join(blocks)


def build_user_prompt(query: str, provisions: List[Dict[str, Any]]) -> str:
    """Constructs the full user prompt containing evidence block and query."""
    evidence_block = format_evidence_block(provisions)
    return USER_PROMPT_TEMPLATE.format(evidence_block=evidence_block, query=query.strip())
