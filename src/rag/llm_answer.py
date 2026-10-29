"""
src/rag/llm_answer.py
----------------------
Local LLM generative answer pipeline with evidence-ID-only prompting,
strict JSON schema validation, retry logic, and extractive fallback.
"""
import json
import socket
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Callable, Union, Tuple

from .config import settings
from .extractive import extractive_answer
from .citation_validator import split_into_sentences, resolve_claim_quote_from_index


def build_prompt(
    query: str,
    evidence: List[Dict[str, Any]],
    lang: str,
    use_sentence_index: Optional[bool] = None
) -> str:
    """
    Constructs prompt containing ONLY query, user language, and text-only evidence blocks.
    Strictly omits Act titles, section numbers, and source URLs.
    
    If use_sentence_index is True (or enabled in settings):
      Formats sentences with tags [E{block}:S{sent}] and instructs LLM to emit
      evidence_id + sentence_index (e.g. "E1:S2") instead of copying verbatim quotes.
    If use_sentence_index is False:
      Legacy Week 5 mode where LLM copies verbatim quote text directly.
    """
    use_idx = settings.use_sentence_index_citations if use_sentence_index is None else use_sentence_index

    if use_idx:
        evidence_blocks = []
        for idx, item in enumerate(evidence, 1):
            text = item.get("text", "").strip()
            sents = split_into_sentences(text)
            if sents:
                sent_lines = [f"  [E{idx}:S{s_idx}] {s}" for s_idx, s in enumerate(sents, 1)]
                evidence_blocks.append(f"[E{idx}]:\n" + "\n".join(sent_lines))
            else:
                evidence_blocks.append(f"[E{idx}:S1] {text}")

        evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "None"

        prompt = (
            f"You are a legal assistant. Answer the user's question using ONLY the provided evidence blocks.\n\n"
            f"User Language: {lang}\n"
            f"User Query: {query}\n\n"
            f"Evidence Blocks:\n{evidence_text}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. If the evidence blocks are insufficient to answer the question, return JSON:\n"
            f'   {{"abstain": true, "reason": "Brief explanation in {lang}"}}\n'
            f"2. Otherwise, return JSON matching this exact structure:\n"
            f"   {{\n"
            f'     "answer_sections": {{\n'
            f'       "source_says": ["..."],\n'
            f'       "relation_to_facts": ["..."],\n'
            f'       "missing_facts": ["..."],\n'
            f'       "uncertain": ["..."]\n'
            f"     }},\n"
            f'     "claims": [\n'
            f'       {{"text": "claim text", "evidence_id": "E1:S1"}}\n'
            f"     ]\n"
            f"   }}\n"
            f"3. In claims, cite ONLY evidence_id and sentence_index in format 'E{{block}}:S{{sent}}' (e.g., 'E1:S2').\n"
            f"   Do NOT copy quotes; code extracts the quote from the stored record directly.\n"
            f"   NEVER emit Act titles, section numbers, or URLs anywhere in your output.\n"
            f"4. Answer strictly in {lang}.\n"
            f"5. Output ONLY valid JSON. No markdown fences or extraneous text."
        )
        return prompt

    evidence_blocks = []
    for idx, item in enumerate(evidence, 1):
        text = item.get("text", "").strip()
        evidence_blocks.append(f"[E{idx}] {text}")

    evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "None"

    prompt = (
        f"You are a legal assistant. Answer the user's question using ONLY the provided evidence blocks.\n\n"
        f"User Language: {lang}\n"
        f"User Query: {query}\n\n"
        f"Evidence Blocks:\n{evidence_text}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. If the evidence blocks are insufficient to answer the question, return JSON:\n"
        f'   {{"abstain": true, "reason": "Brief explanation in {lang}"}}\n'
        f"2. Otherwise, return JSON matching this exact structure:\n"
        f"   {{\n"
        f'     "answer_sections": {{\n'
        f'       "source_says": ["..."],\n'
        f'       "relation_to_facts": ["..."],\n'
        f'       "missing_facts": ["..."],\n'
        f'       "uncertain": ["..."]\n'
        f"     }},\n"
        f'     "claims": [\n'
        f'       {{"text": "claim text", "evidence_ids": ["E1"], "quote": "exact excerpt from cited evidence block"}}\n'
        f"     ]\n"
        f"   }}\n"
        f"3. In claims and answer sections, cite ONLY evidence IDs (e.g., 'E1', 'E2').\n"
        f"   NEVER emit Act titles, section numbers, or URLs anywhere in your output.\n"
        f"4. The quote in each claim MUST be an exact verbatim substring from the cited evidence block.\n"
        f"5. Answer strictly in {lang}.\n"
        f"6. Output ONLY valid JSON. No markdown fences or extraneous text."
    )
    return prompt


def _call_ollama(prompt: str) -> Dict[str, Any]:
    """Calls local Ollama generate API using fixed settings (num_predict=1024, num_ctx=4096, keep_alive=30m)."""
    url = f"{settings.llm_base_url}/api/generate"
    payload = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": settings.llm_keep_alive,
        "options": {
            "temperature": settings.llm_temperature,
            "top_p": settings.llm_top_p,
            "seed": settings.llm_seed,
            "num_predict": settings.llm_max_tokens,
            "num_ctx": settings.llm_num_ctx,
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=settings.llm_timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def warm_model(llm_caller: Optional[Callable[[str], Any]] = None) -> bool:
    """Warms the model with one throwaway call before timing starts."""
    caller = llm_caller or _call_ollama
    try:
        caller('{"ping": "pong"}')
        return True
    except Exception:
        return False


def generate_answer(
    query: str,
    evidence: List[Dict[str, Any]],
    lang: str = "en",
    llm_caller: Optional[Callable[[str], Union[str, Dict[str, Any]]]] = None
) -> Dict[str, Any]:
    """
    Generates structured answer from local LLM with retry on malformed JSON,
    truncation detection, and automatic extractive fallback.
    Distinguishes failure types: timeout, unreachable, parse_failure, truncated, schema_missing.
    """
    caller = llm_caller or _call_ollama

    # Cap evidence passed to LLM: top 3 records, each text truncated to 1200 chars
    capped_evidence = []
    for rec in evidence[:settings.llm_max_evidence_records]:
        r = dict(rec)
        t = r.get("text", "")
        if len(t) > settings.llm_max_evidence_chars:
            r["text"] = t[:settings.llm_max_evidence_chars]
        capped_evidence.append(r)

    prompt = build_prompt(query, capped_evidence, lang)

    raw_response_text = ""
    parsed_json = None
    parse_failure = False
    truncated = False

    def invoke_backend(p: str) -> Tuple[str, bool]:
        res = caller(p)
        if isinstance(res, dict):
            text = res.get("response", "")
            is_trunc = (res.get("done_reason") == "length")
            return text, is_trunc
        elif isinstance(res, str):
            return res, False
        return str(res), False

    # Attempt 1
    try:
        raw_response_text, truncated = invoke_backend(prompt)
    except (TimeoutError, socket.timeout):
        fallback = extractive_answer(query, evidence, lang=lang)
        fallback["fallback_used"] = True
        fallback["timeout"] = True
        fallback["unreachable"] = False
        fallback["parse_failure"] = False
        fallback["truncated"] = False
        fallback["schema_missing"] = False
        return fallback
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        is_to = isinstance(getattr(e, "reason", None), socket.timeout) or "timed out" in str(e).lower()
        fallback = extractive_answer(query, evidence, lang=lang)
        fallback["fallback_used"] = True
        fallback["timeout"] = is_to
        fallback["unreachable"] = not is_to
        fallback["parse_failure"] = False
        fallback["truncated"] = False
        fallback["schema_missing"] = False
        return fallback

    # Parse JSON attempt 1
    try:
        parsed_json = json.loads(raw_response_text)
    except (json.JSONDecodeError, ValueError):
        parse_failure = True
        # Attempt 2: retry once with strict reminder
        retry_prompt = prompt + "\n\nCRITICAL: Your previous response was invalid JSON. Output strictly valid raw JSON only."
        try:
            raw_response_text, truncated = invoke_backend(retry_prompt)
            parsed_json = json.loads(raw_response_text)
        except (TimeoutError, socket.timeout):
            fallback = extractive_answer(query, evidence, lang=lang)
            fallback["fallback_used"] = True
            fallback["timeout"] = True
            fallback["unreachable"] = False
            fallback["parse_failure"] = True
            fallback["truncated"] = truncated
            fallback["schema_missing"] = False
            return fallback
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            is_to = isinstance(getattr(e, "reason", None), socket.timeout) or "timed out" in str(e).lower()
            fallback = extractive_answer(query, evidence, lang=lang)
            fallback["fallback_used"] = True
            fallback["timeout"] = is_to
            fallback["unreachable"] = not is_to
            fallback["parse_failure"] = True
            fallback["truncated"] = truncated
            fallback["schema_missing"] = False
            return fallback
        except Exception:
            fallback = extractive_answer(query, evidence, lang=lang)
            fallback["fallback_used"] = True
            fallback["timeout"] = False
            fallback["unreachable"] = False
            fallback["parse_failure"] = True
            fallback["truncated"] = truncated
            fallback["schema_missing"] = False
            return fallback

    # Check for valid dict structure
    if not isinstance(parsed_json, dict):
        fallback = extractive_answer(query, evidence, lang=lang)
        fallback["fallback_used"] = True
        fallback["timeout"] = False
        fallback["unreachable"] = False
        fallback["parse_failure"] = True
        fallback["truncated"] = truncated
        fallback["schema_missing"] = True
        return fallback

    # Handle explicit abstention
    if parsed_json.get("abstain") is True:
        return {
            "abstain": True,
            "reason": parsed_json.get("reason", "Evidence insufficient"),
            "answer_sections": {},
            "claims": [],
            "fallback_used": False,
            "timeout": False,
            "unreachable": False,
            "parse_failure": parse_failure,
            "truncated": truncated,
            "schema_missing": False
        }

    # Validate structure has answer_sections and claims
    if "answer_sections" not in parsed_json or "claims" not in parsed_json:
        fallback = extractive_answer(query, evidence, lang=lang)
        fallback["fallback_used"] = True
        fallback["timeout"] = False
        fallback["unreachable"] = False
        fallback["parse_failure"] = parse_failure
        fallback["truncated"] = truncated
        fallback["schema_missing"] = True
        return fallback

    # Resolve quote from sentence index if active
    if settings.use_sentence_index_citations:
        resolved_claims = []
        for c in parsed_json.get("claims", []):
            resolved_claims.append(resolve_claim_quote_from_index(c, evidence))
        parsed_json["claims"] = resolved_claims

    parsed_json["fallback_used"] = False
    parsed_json["timeout"] = False
    parsed_json["unreachable"] = False
    parsed_json["parse_failure"] = parse_failure
    parsed_json["truncated"] = truncated
    parsed_json["schema_missing"] = False
    return parsed_json
