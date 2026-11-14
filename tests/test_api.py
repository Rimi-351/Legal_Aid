"""
tests/test_api.py
-----------------
Functional API test suite for FastAPI endpoint POST /api/v1/legal/ask.
Verifies input validation, error handling, mode support, and response schemas
without network calls or live LLM dependencies.

DESIGN PRINCIPLES:
- Tests the REAL app (src.rag.api), not a fallback stub.
- LLM modes use unittest.mock.patch to avoid Ollama calls.
- All assertions grounded in observed pipeline behaviour (steps 1-6 audit).
- Pydantic AskResponse used as the contract validator on every 200 response.

KNOWN BEHAVIOUR (not bugs):
- Empty/whitespace queries: return 200 with abstained=True  (BM25 returns [], pipeline handles).
- Unknown lang codes:        return 200  (lang: str has no enum restriction in schema).
- Malformed as_of_date:     return 200 with abstained=True (temporal qualification gate).
- These are intentional design decisions; tests verify the behaviour, not change it.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.rag.api import AskResponse, app


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> TestClient:
    """Module-scoped TestClient — avoids per-test lifespan overhead."""
    return TestClient(app)


@pytest.fixture
def mock_llm_response():
    """
    Deterministic LLM stub that returns a structurally valid claim
    grounded in the first retrieved evidence record.

    Returned as a callable so patch(side_effect=...) works naturally
    with generate_answer(query, evidence, lang).
    """
    def _generator(
        query: str,
        evidence: List[Dict[str, Any]],
        lang: str = "en",
    ) -> Dict[str, Any]:
        quote_text = (
            evidence[0]["text"][:40]
            if evidence and evidence[0].get("text")
            else "Default sample statutory quote for testing."
        )
        return {
            "answer": "Mock grounded legal response.",
            "claims": [
                {
                    "text": "Mock grounding claim.",
                    "evidence_id": "E1",
                    "evidence_ids": ["E1"],
                    "quote": quote_text,
                }
            ],
            "fallback_used": False,
            "abstain": False,
        }

    return _generator


# ---------------------------------------------------------------------------
# 1. Input validation — empty / whitespace
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("empty_query", ["", "   ", "\t\n\r  "])
def test_empty_or_whitespace_query_returns_200_not_500(
    client: TestClient, empty_query: str
) -> None:
    """
    Risk: Empty or whitespace-only queries must not crash the BM25 tokeniser
    or return an unhandled HTTP 500. The pipeline must degrade gracefully,
    returning either abstained=True or an empty evidence notice.

    DO NOT assert 422 here — the schema accepts any non-None string.
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={"query": empty_query, "mode": "extractive"},
    )
    assert response.status_code == 200, (
        f"Expected 200 for empty query, got {response.status_code}: {response.text}"
    )
    data = response.json()
    validated = AskResponse(**data)
    assert validated.abstained is True or isinstance(validated.answer, str)
    assert validated.latency_ms > 0
    assert validated.peak_rss_mb > 0


# ---------------------------------------------------------------------------
# 2. Mode validation — Pydantic Literal enforces allowed set
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "invalid_mode",
    ["invalid_mode", "hybrid", "dense", "bm25", "temporal", "gpt-4", ""],
)
def test_invalid_mode_rejected_with_422(
    client: TestClient, invalid_mode: str
) -> None:
    """
    Risk: Modes outside the declared Literal["extractive","llm","llm_validated",
    "llm_validated_noabstain"] must be rejected immediately by Pydantic with 422.

    NOTE: "hybrid", "dense", "bm25", "temporal" are NOT valid modes for this API.
    A passing test with these would mask a regression — they should 422.
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={
            "query": "contract termination notice period?",
            "mode": invalid_mode,
        },
    )
    assert response.status_code == 422, (
        f"Mode '{invalid_mode}' should be rejected (422), got {response.status_code}"
    )
    detail = response.json().get("detail", [])
    assert any("mode" in str(loc) for loc in detail)


# ---------------------------------------------------------------------------
# 3. Language parameter — free string, any value accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "unknown_lang", ["klingon", "xyz_unknown", "12345", "invalid_lang_code"]
)
def test_invalid_lang_accepted_gracefully_as_200(
    client: TestClient, unknown_lang: str
) -> None:
    """
    Risk: lang is declared as `str = "en"` with no Pydantic enum restriction.
    The API accepts any string and routes it to language-aware extractive logic.

    DO NOT assert 422 — that never fires. Assert 200 and a valid AskResponse.
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={
            "query": "contract termination notice period",
            "lang": unknown_lang,
            "mode": "extractive",
        },
    )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    assert isinstance(validated.answer, str)
    assert validated.latency_ms > 0


# ---------------------------------------------------------------------------
# 4. Temporal date validation — malformed dates trigger abstention, not 422
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_date",
    ["2026-13-45", "yesterday", "not-a-date", "2024-02-30", "01-01-2026"],
)
def test_malformed_as_of_date_triggers_temporal_abstention(
    client: TestClient, bad_date: str
) -> None:
    """
    Risk: Malformed or non-ISO dates cannot be parsed by parse_date_string().
    The temporal qualification gate MUST intercept these and return a safe
    abstention (200 + abstained=True + empty claims), never a 500.

    DO NOT assert 422 — as_of_date is Optional[str] with no Pydantic date format
    validation. The pipeline consumes it and gates.
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={
            "query": "What is the minimum wage for factory workers?",
            "mode": "extractive",
            "as_of_date": bad_date,
        },
    )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    assert validated.abstained is True, (
        f"Expected abstained=True for bad date '{bad_date}', got False"
    )
    assert "cannot be established" in validated.answer.lower()
    assert validated.claims == []


# ---------------------------------------------------------------------------
# 5. Extreme payload length — ReDoS / memory safety
# ---------------------------------------------------------------------------

def test_large_query_40k_characters(client: TestClient) -> None:
    """
    Risk: 10,000–40,000+ character queries can trigger:
    - Regex catastrophic backtracking (ReDoS) in LEAKAGE_PATTERN / ACT_PATTERNS.
    - Memory exhaustion in BM25 tokenisation.
    - Unhandled MemoryError or OverflowError.
    API must respond 200 (or 413) but NEVER 500.
    """
    large_query = "contract breach damages liability landlord tenant " * 1000
    assert len(large_query) > 10_000

    response = client.post(
        "/api/v1/legal/ask",
        json={"query": large_query, "mode": "extractive"},
    )
    assert response.status_code in (200, 413), (
        f"Large query caused unexpected status {response.status_code}: {response.text[:300]}"
    )
    if response.status_code == 200:
        validated = AskResponse(**response.json())
        assert validated.latency_ms > 0
        assert validated.peak_rss_mb > 0


# ---------------------------------------------------------------------------
# 6. Symbol / emoji-only queries — tokeniser zero-token safety
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "symbol_query",
    [
        "⚖️📜🇧🇩",
        "⚠️❗❓",
        "@@@###$$$",
        "⚖️🏛️",          # original suggestion's example
        "???",
        "@@@",
        "###...",
    ],
)
def test_symbols_and_emojis_only_query(
    client: TestClient, symbol_query: str
) -> None:
    """
    Risk: Queries containing only emojis, symbols, or punctuation produce empty
    token lists in BM25 tokenisation. This can cause zero-division in avg_doc_len
    or index out-of-bounds. API must return 200, never 500.
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={"query": symbol_query, "mode": "extractive"},
    )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    assert isinstance(validated.answer, str)
    assert validated.latency_ms > 0


# ---------------------------------------------------------------------------
# 7. All 4 valid modes — schema contract compliance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "mode",
    ["extractive", "llm", "llm_validated", "llm_validated_noabstain"],
)
def test_all_modes_return_valid_askresponse_shape(
    client: TestClient, mock_llm_response: Any, mode: str
) -> None:
    """
    Risk: Mode-specific branches may construct AskResponse inconsistently,
    missing required fields or returning wrong types. Each of the 4 modes
    must satisfy the AskResponse Pydantic contract on every invocation.

    LLM modes are mocked so no Ollama daemon is required.
    """
    with patch("src.rag.api.generate_answer", side_effect=mock_llm_response):
        response = client.post(
            "/api/v1/legal/ask",
            json={
                "query": "contract termination notice requirements",
                "mode": mode,
                "lang": "en",
            },
        )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    assert isinstance(validated.answer, str)
    assert isinstance(validated.claims, list)
    assert isinstance(validated.abstained, bool)
    assert isinstance(validated.fallback_used, bool)
    assert validated.latency_ms > 0
    assert validated.peak_rss_mb > 0


# ---------------------------------------------------------------------------
# 8. Telemetry fields — monitoring / observability contract
# ---------------------------------------------------------------------------

def test_latency_ms_and_peak_rss_mb_are_positive_floats(
    client: TestClient,
) -> None:
    """
    Risk: Uninitialised or zero telemetry fields break monitoring dashboards
    and SLA tracking. Both must be explicitly typed and > 0 on every response.
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={"query": "landlord rent increase limits", "mode": "extractive"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "latency_ms" in data, "latency_ms missing from response"
    assert "peak_rss_mb" in data, "peak_rss_mb missing from response"
    assert isinstance(data["latency_ms"], (int, float))
    assert isinstance(data["peak_rss_mb"], (int, float))
    assert data["latency_ms"] > 0
    assert data["peak_rss_mb"] > 0


# ---------------------------------------------------------------------------
# 9. Bangla-script query — Unicode tokenisation safety
# ---------------------------------------------------------------------------

def test_pure_bangla_query_handled_without_crash(client: TestClient) -> None:
    """
    Risk: Bangla-script queries must pass through BM25 tokenisation (Bengali
    Unicode block U+0980–U+09FF regex) without TypeError, UnicodeDecodeError,
    or silent truncation. Response must be a valid AskResponse.
    """
    bangla_query = "কর্মচারী ছাঁটাই নোটিশের নিয়ম কী?"
    response = client.post(
        "/api/v1/legal/ask",
        json={"query": bangla_query, "mode": "extractive", "lang": "bn"},
    )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    assert isinstance(validated.answer, str)


# ---------------------------------------------------------------------------
# 10. Banglish query — mixed-script tokenisation
# ---------------------------------------------------------------------------

def test_banglish_query_handled_without_crash(client: TestClient) -> None:
    """
    Risk: Code-mixed Banglish queries (Bengali semantics in Latin script) must
    tokenise through BM25's char-ngram layer without crashing, even if
    retrieval produces zero results.
    """
    banglish_query = "malik jokhon notice na diye worker ke chhatai kore tahole ki hobe?"
    response = client.post(
        "/api/v1/legal/ask",
        json={"query": banglish_query, "mode": "extractive", "lang": "banglish"},
    )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    assert isinstance(validated.answer, str)
    assert validated.latency_ms > 0


# ---------------------------------------------------------------------------
# 11. warning field — optional field present / absent contract
# ---------------------------------------------------------------------------

def test_warning_field_is_string_or_none(client: TestClient) -> None:
    """
    Risk: AskResponse.warning is Optional[str]. Clients must handle both
    None and non-empty string without crashing. Verify the field is never
    an unexpected type (e.g. list, dict, int).
    """
    response = client.post(
        "/api/v1/legal/ask",
        json={"query": "consumer rights price labelling", "mode": "extractive"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "warning" in data
    assert data["warning"] is None or isinstance(data["warning"], str)


# ---------------------------------------------------------------------------
# 12. abstained + fallback co-occurrence — logical consistency gate
# ---------------------------------------------------------------------------

def test_abstained_response_has_empty_claims(client: TestClient) -> None:
    """
    Risk: When the pipeline abstains (evidence below threshold or temporal
    unverifiable), it MUST return an empty claims list. A non-empty claims
    list combined with abstained=True is a logical contradiction that breaks
    downstream answer rendering.
    """
    # Trigger temporal abstention with a valid ISO date that has no verified evidence
    response = client.post(
        "/api/v1/legal/ask",
        json={
            "query": "What was the rent law in 1850?",
            "mode": "extractive",
            "as_of_date": "1850-01-01",
        },
    )
    assert response.status_code == 200
    validated = AskResponse(**response.json())
    if validated.abstained:
        assert validated.claims == [], (
            "abstained=True must co-occur with empty claims list"
        )


# ---------------------------------------------------------------------------
# 13. Thread safety — concurrent request simulation
# ---------------------------------------------------------------------------

def test_concurrent_requests_do_not_corrupt_state(client: TestClient) -> None:
    """
    Risk: Module-level singletons (_retriever, _corpus_cache in api.py) are
    shared across requests. Concurrent initialisation could cause data races,
    double-fit of BM25, or corrupted index state under WSGI/ASGI threading.
    Send 5 simultaneous requests and verify all return structurally valid responses.
    """
    results: list[int] = []

    def make_request() -> None:
        resp = client.post(
            "/api/v1/legal/ask",
            json={"query": "termination notice period labour act", "mode": "extractive"},
        )
        results.append(resp.status_code)

    threads = [threading.Thread(target=make_request) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(s == 200 for s in results), (
        f"Thread-safety failure: status codes = {results}"
    )
