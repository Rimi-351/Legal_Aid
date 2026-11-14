# Verification & Test Suite Audit Report: Legal Aid BD

**Date:** November 14, 2026  
**Repository:** `Legal_Aid` (Multilingual Legal Information Retrieval & Grounded Generation for Bangladesh Law)  
**Environment:** Python 3.13.5 (Windows 11) / Target CI: Python 3.11 (Linux)  
**Test Framework:** Pytest 9.2.0, Pytest-Cov 7.1.0, Coverage 7.17.3, FastAPI TestClient (HTTPX 0.28.1)

---

## 1. Executive Summary & Test Counts

Prior to this verification effort, repository tests had high baseline pass rates but significant blind spots: 0% coverage on hybrid retrieval fusion (`src/retrieval/hybrid.py`), 0 API endpoint tests, untested security edge cases, unhandled path traversal vulnerabilities, and silent skips in critical exit-gate evaluation tests. 

Over Steps 1–4, the test suite was hardened from 112 baseline tests to 225 total tests (+113 new tests), all security defects in `DocumentStorage` fixed, with separated non-model execution using pytest marker hygiene.

### 1.1 Test Suite Progression

| Metric | Step 1 (Baseline) | Step 2 (Missing Tests Added) | Step 3 & 4 (Hygiene & Markers) | Post-Fix (Current) | Net Change |
|---|---|---|---|---|---|
| **Total Test Items Collected** | 112 | 199 | 199 | 225 | **+113** |
| **Passed Tests** | 112 | 198 (with model tests) | 194 (`not model and not live`) | 221 (`not model and not live`) | **+109 passed** |
| **Failed Tests** | 0 | 0 | 0 | 0 | **0 unhandled failures** |
| **Expected Failures (`xfail`)** | 0 | 1 | 1 | 0 | **SEC-1 path-traversal bug fixed; regression tests pass** |
| **Deselected (Heavy Models)** | 0 | 0 | 4 (`test_embedding_feasibility.py`) | 4 | **+4 cleanly deselected** |
| **Skipped Tests** | 0 | 0 | 0 | 0 | **0 silent skips** |

> **Note on Test Counts:** In Step 1, `python -m unittest discover tests` discovered 101 tests, whereas `pytest -v` collected 112 items. The 11-test discrepancy consists of 11 standalone test functions in `tests/test_metrics_fix.py` (5 functions) and `tests/test_quote_path.py` (6 functions) that do not inherit from `unittest.TestCase`.

---

## 2. Test Coverage & Module Impact

Coverage was measured using `pytest-cov` on `src/` modules. Focus was placed on the four primary under-tested modules identified in the Step 1 baseline.

### 2.1 Per-Module Coverage Comparison

| Module | Purpose | Step 1 Baseline Coverage | Post-Step 2 Coverage | Lines Remaining Uncovered |
|---|---|---|---|---|
| `src/retrieval/hybrid.py` | Reciprocal Rank Fusion (RRF) | **0%** (0/33 stmts) | **100%** (33/33 stmts) | None (Full branch & line coverage) |
| `src/rag/api.py` | FastAPI `POST /api/v1/legal/ask` | **53%** (74/140 stmts) | **86%** (121/140 stmts) | 50, 188-189, 212-219, 224-226, 261-263, 294-299 |
| `src/ingestion/normalizer.py` | Unicode NFC, ZWJ/ZWNJ & Language Detection | **88%** (37/42 stmts) | **93%** (39/42 stmts) | 101-104 (Fallback ratio edges) |
| `src/retrieval/temporal.py` | Enactment/Repeal Date Status Logic | **60%** (69/115 stmts) | **66%** (76/115 stmts) | 63, 65, 67, 71, 87-90, 96-103, 110-117, 137, 145, 152, 162, 180, 193-195, 204-208, 224, 235 |
| `src/rag/citation_validator.py` | Substring & Schema Citation Validation | **73%** (134/184 stmts) | **73%** (134/184 stmts) | 32, 56-57, 59-65, 67-73, 78-93, 106, 147, 167, 182, 205, 215, 218, 222-223, 228, 233, 246-247, 251, 261, 267, 285-290 |
| `src/review/clause_review.py` | Clause Analysis & Document Storage | **48%** (96/198 stmts) | **52%** (103/198 stmts) | 90, 95, 102, 136-157, 164-186, 193-200, 206-211, 258-265, 273, 282-304, 326, 369-390, 395-401, 413-424 |
| **Total Across Targeted Modules** | — | **59.2%** (410/692 stmts) | **71.1%** (506/712 stmts) | **+11.9% absolute coverage gain** |

---

## 3. Bugs Discovered & Cataloged

Per the engineering guidelines, no files in `src/` were modified to force tests to pass. Real misbehaviors were isolated and cataloged below.

> [!NOTE]
> **Reachability note:** DocumentStorage is not called by app/ui.py, src/rag/api.py or any script; SEC defects were latent, reachable only by direct use of the class.

---

### SEC-1: Path Traversal via Upload Filename in `save_document`
- **Location:** `src/review/clause_review.py` — `DocumentStorage.save_document`
- **Severity:** Critical (CWE-22: Path Traversal)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_upload_filename_path_traversal_rejection`, `test_storage_absolute_and_backslash_filename`
- **Steps to Reproduce:**
  ```python
  storage = DocumentStorage(base_dir=td)
  saved = storage.save_document("tenant_1", "doc_A", "../../escape.pdf", b"%PDF-1.4")
  # Pre-fix: saved resolves to <td>/escape.pdf — outside the tenant sandbox
  ```
- **Expected:** `ValueError` or the path confined to `<td>/tenant_1/doc_A/escape.pdf`.
- **Actual (pre-fix):** File written to `<td>/escape.pdf`, escaping `uploads/<owner_id>/<doc_id>`.

---

### SEC-2: `doc_id ".."` Causes `delete_document` to Wipe the Entire Store
- **Location:** `src/review/clause_review.py` — `DocumentStorage._get_doc_dir`, `delete_document`
- **Severity:** Critical (CWE-22; destructive)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_storage_invalid_doc_id_traversal`
- **Steps to Reproduce:**
  ```python
  storage = DocumentStorage(base_dir=td)
  storage.save_document("tenant_1", "doc_1", "f.pdf", b"%PDF-1.4")
  storage.delete_document("tenant_1", "..")
  # Pre-fix: shutil.rmtree resolves to <td>/tenant_1 — entire tenant dir deleted
  ```
- **Expected:** `ValueError` with message matching `"Invalid doc_id"`.
- **Actual (pre-fix):** `_get_doc_dir` accepted `".."`, `delete_document` called `shutil.rmtree(<td>/tenant_1)`.

---

### SEC-3: `owner_id "../x"` and Key Traversal via `save_derived_data`
- **Location:** `src/review/clause_review.py` — `_get_doc_dir`, `save_derived_data`, `get_derived_data`
- **Severity:** High (CWE-22)
- **Status:** Fixed. Regressions: `tests/test_security_edges.py::test_storage_invalid_owner_id_traversal`, `test_storage_key_traversal`
- **Steps to Reproduce:**
  ```python
  storage._get_doc_dir("../x", "doc_1")           # owner_id traversal
  storage.save_derived_data("t", "d", "../../key", {})  # key traversal
  ```
- **Expected:** `ValueError` for `"Invalid owner_id"` / `"Invalid key"`.
- **Actual (pre-fix):** Paths resolved outside `base_dir`; files written or read across tenant boundaries.

---

### SEC-4: No-Extension Upload Bypass
- **Location:** `src/review/clause_review.py` — `DocumentStorage.save_document`
- **Severity:** Medium (input validation bypass)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_storage_no_extension_filename_rejected`
- **Steps to Reproduce:**
  ```python
  storage.save_document("t1", "d1", "exploit_no_ext", b"binary")
  # Pre-fix: `if ext and ext not in allowed` skipped when ext == "" (falsy)
  ```
- **Expected:** `ValueError` matching `"Unsupported file format"`.
- **Actual (pre-fix):** File saved without extension check; arbitrary binary content accepted.

---

### SEC-5: Trailing-Newline IDs Accepted (`re.match` vs `re.fullmatch`)
- **Location:** `src/review/clause_review.py` — `_validate_id`
- **Severity:** Medium (input validation bypass enabling injection via newline-suffixed IDs)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_validate_id_rejects_embedded_newline`
- **Steps to Reproduce:**
  ```python
  _validate_id("user_a\n", "owner_id")  # pre-fix: does not raise
  _validate_id("doc\n", "doc_id")       # pre-fix: does not raise
  ```
- **Expected:** `ValueError` — `re.fullmatch` rejects trailing `\n` outside `[A-Za-z0-9_-]{1,64}`.
- **Actual (pre-fix):** `re.match` only anchors at start; `"user_a\n"` passed validation.

---

### SEC-6: Cross-Tenant Read/Delete via Case-Variant `owner_id` on Case-Insensitive Filesystems
- **Location:** `src/review/clause_review.py` — `get_document`, `delete_document`
- **Severity:** High (tenant isolation bypass; Windows/macOS case-insensitive FS)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_cross_tenant_case_mismatch`
- **Steps to Reproduce:**
  ```python
  storage.save_document("user_a", "doc1", "contract.pdf", b"%PDF-1.4")
  storage.get_document("USER_A", "doc1")    # pre-fix: returns user_a's doc on Windows
  storage.delete_document("USER_A", "doc1") # pre-fix: deletes user_a's doc on Windows
  ```
- **Expected:** `PermissionError` or `FileNotFoundError` for the case-variant caller.
- **Actual (pre-fix):** Windows resolved `USER_A/doc1` to the same inode as `user_a/doc1`; meta `owner_id` check was absent.

---

### SEC-7: Cross-Tenant Overwrite and Ownership Takeover via `save_document`
- **Location:** `src/review/clause_review.py` — `DocumentStorage.save_document`
- **Severity:** Critical (tenant isolation bypass; ownership poisoning)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_save_document_cross_tenant_overwrite_blocked`
- **Steps to Reproduce:**
  ```python
  storage.save_document("user_a", "doc1", "a.pdf", b"%PDF-ORIGINAL")
  storage.save_document("USER_A", "doc1", "a.pdf", b"%PDF-HACKED")
  # pre-fix on Windows: a.pdf overwritten with HACKED; meta.json owner_id changed to "USER_A"
  ```
- **Expected:** `PermissionError` before any write; original content and `owner_id` untouched.
- **Actual (pre-fix):** No guard before `open(file_path, "wb")`; file and metadata silently overwritten.

---

### SEC-8: `derived/` Symlink Escape in `save_derived_data` / `get_derived_data`
- **Location:** `src/review/clause_review.py` — `save_derived_data`, `get_derived_data`
- **Severity:** High (CWE-61: UNIX Symbolic Link Attack)
- **Status:** Fixed. Regression: `tests/test_security_edges.py::test_derived_dir_symlink_escape`
- **Steps to Reproduce:**
  ```python
  storage.save_document("tenant1", "doc1", "file.pdf", b"%PDF-1.4")
  (doc_dir / "derived").symlink_to(outside_dir)  # attacker plants symlink
  storage.save_derived_data("tenant1", "doc1", "result", {"x": 1})
  # pre-fix: data written into outside_dir via symlink
  ```
- **Expected:** `ValueError` matching `"derived_dir escapes doc_dir"` before any read or write; nothing written to `outside_dir`.
- **Actual (pre-fix):** `(doc_dir / "derived").resolve()` followed the symlink; `is_relative_to(doc_dir)` check was absent; data written outside the tenant boundary.

---

### Bug 2: Unquoted `torch.Tensor` Type Annotation Breaking Test Import Hygiene
- **Location:** `src/retrieval/dense.py:102`
- **Severity:** Medium (Packaging / Import Hygiene)
- **Priority:** P2
- **Status:** Verified during CI dependency analysis.
- **Steps to Reproduce:**
  In a clean Python environment without `torch` installed (or by running `python -c "import sys; sys.modules['torch'] = None; import src.retrieval.dense"`):
- **Expected Behavior:** `src/retrieval/dense.py` wraps `import torch` in a `try...except ImportError` block (lines 16–22) so that environments without PyTorch can still import `DenseRetriever` and run mock tests.
- **Actual Behavior:** At line 102, `def _mean_pooling(self, model_output, attention_mask) -> torch.Tensor:` evaluates `torch.Tensor` at class definition time, causing Python to raise:
  `NameError: name 'torch' is not defined`.
  This cascades to `tests/test_dense.py` and `tests/test_hybrid.py`, preventing all test collection unless PyTorch is installed.
- **Smallest Recommended Fix:**
  Add `from __future__ import annotations` at line 1 of `src/retrieval/dense.py`, or change the type annotation to `-> "torch.Tensor":` or `-> Any:`.

---

### Bug 3: Silent Skips Masking Missing Evaluation Artifacts in CI Gates
- **Location:** `tests/test_rag.py:284` and `tests/test_rag.py:349`
- **Severity:** Low (Test Reliability / Masked Gate Failure)
- **Priority:** P3
- **Status:** Verified via code inspection and skipTest analysis.
- **Steps to Reproduce:**
  Delete or rename `eval/outputs.jsonl` (e.g., in a clean git clone before running the frozen eval pipeline) and run `pytest tests/test_rag.py`.
- **Expected Behavior:** Exit gate tests (`test_exit_gate_zero_unverified_citations_and_zero_leakage` and `test_outputs_jsonl_schema_and_four_conditions`) are intended as CI exit gates verifying that evaluation outputs adhere to schema and zero-leakage requirements. If the artifact does not exist, the exit gate should fail or be explicitly flagged.
- **Actual Behavior:** Both tests catch the missing/empty file and call `self.skipTest(...)`:
  - Line 284: `self.skipTest("eval/outputs.jsonl not generated yet; run evaluation first.")`
  - Line 349: `self.skipTest("eval/outputs.jsonl not generated yet; will be verified after eval run.")`
  Pytest records them as SKIPPED, reporting a green CI exit code 0 even when evaluation results have not been generated.
- **Smallest Recommended Fix:**
  Add a dedicated CI flag or fixture: in strict evaluation mode, raise `FileNotFoundError("eval/outputs.jsonl is missing; exit gate failed")` instead of silently skipping.

---

## 4. Components Not Verifiable by Automated Tests

Automated tests provide proof of programmatic execution, schema conformity, and string manipulation. However, several core assumptions and claims in legal AI cannot be validated by unit tests alone. Below is an exhaustive list and the exact manual audit required for each.

### 4.1 Statute Text vs. Official Gazettes (0 / 17 Verified)
- **Current State:** The repository corpus consists of 17 provisions across 4 Acts stored in `data/processed/provisions.jsonl`. In metadata, every single record has `review_status: "pending"` or `"uncertain"`. Zero records have been cross-checked against official Bangladesh Government Press (BG Press) gazettes.
- **Why Tests Cannot Verify This:** Tests only verify that retrieved text matches what was indexed in `data/processed/provisions.jsonl`. If the indexed text contains transcription errors, unofficial wording, or missing sub-clauses, the tests still pass.
- **Required Manual Audit:**
  1. Download authenticated Gazette PDFs from the Bangladesh Law Commission / BG Press for:
     - The Contract Act, 1872 (Act IX of 1872)
     - The Premises Rent Control Act, 1991 (Act III of 1991)
     - The Bangladesh Labour Act, 2006 (Act XLII of 2006)
     - The Consumer Rights Protection Act, 2009 (Act XXVI of 2009)
  2. Perform an exact character-by-character text diff between the official gazette text and `data/processed/provisions.jsonl`.
  3. Verify that section numbering, Bengali diacritics, and legislative punctuation (dari `।` and double-dari `॥`) correspond exactly to the official enactment.

---

### 4.2 Ground-Truth Correctness of the 30 Evaluation Queries
- **Current State:** The benchmark query set contains 30 queries (`data/manifests/query_manifest.jsonl` and `eval/outputs.jsonl`). Exactly 15 queries have relevant provisions present in the 17-provision corpus; the remaining 15 queries have no gold provision in the corpus (unanswerable / negative queries).
- **Why Tests Cannot Verify This:** Automated retrieval benchmarks measure Recall@K and MRR relative to author-annotated gold IDs. The test suite cannot evaluate whether an author incorrectly labeled a question as unanswerable or whether the gold answer reflects authoritative statutory interpretation.
- **Required Manual Audit:**
  1. Provide the 30 queries and the 17 provisions blindly to at least 2 qualified Bangladeshi advocates / legal practitioners.
  2. Ask annotators to independently identify:
     - Whether the query is answerable from the provided 17 provisions.
     - Which specific Act and Section governs the question.
     - Whether the query requires unindexed statutes (e.g. Penal Code, Specific Relief Act).
  3. Reconcile disagreements and update gold IDs in the benchmark manifest.

---

### 4.3 Cross-Lingual 0.0000 Metric Artifact (`record_id` vs `(act, section)`)
- **Current State:** In cross-lingual retrieval experiments (e.g. Banglish or English queries retrieving Bengali provisions), cross-lingual match metrics frequently report `0.0000`.
- **Why Tests Cannot Verify This:** The scoring scripts compute string equality on `record_id` (e.g., checking if `CRPA2009_S37` equals `CRPA2009_S৩৭`). Because Bengali numerals (`৩৭`) do not match ASCII digits (`37`), the metric records 0.0000 overlap even when the search engine retrieved the exact right legal section.
- **Required Manual Audit:**
  1. Inspect `eval/frozen_retrieval_metrics.json` and examine queries where cross-lingual score is recorded as 0.0.
  2. Check the retrieved provision title and section number manually.
  3. Recompute retrieval metrics using normalized `(canonical_act_slug, normalized_section_int)` tuples rather than raw string identifiers to establish whether the 0.0 score is a retrieval failure or a metric artifact.

---

### 4.4 Semantic Entailment & Legal Support of Citations
- **Current State:** The citation validator (`src/rag/citation_validator.py`) enforces substring containment: a claim is marked valid if its cited quote is an exact or normalized substring of the retrieved DB provision (minimum 20 characters).
- **Why Tests Cannot Verify This:** Substring containment proves *presence in text*, but **not semantic support**. An LLM can quote a real sentence from Section 26 of the Labour Act ("The employment of a permanent worker may be terminated...") to support a fabricated or contradictory legal claim ("Workers can be dismissed without any compensation or notice"). The automated validator marks this valid because the quote exists.
- **Required Manual Audit:**
  1. Extract the 12 LLM answers that passed validator filtering in `eval/outputs.jsonl`.
  2. Have legal reviewers classify each claim into one of three categories:
     - **Entailed:** The cited statutory quote directly proves and justifies the claim.
     - **Contradicted:** The claim contradicts or misstates the legal effect of the cited quote.
     - **Irrelevant / Non-sequitur:** The quote is real, but does not support the specific proposition asserted.

---

### 4.5 Inter-Annotator Agreement (Cohen's Kappa / Krippendorff's Alpha)
- **Current State:** All query labels, relevance judgments, and contract review findings currently reflect annotations produced by a single source or model runs. Inter-annotator agreement has not been computed.
- **Why Tests Cannot Verify This:** Tests execute deterministically against static fixtures; they cannot compute human consensus metrics without independent multi-annotator datasets.
- **Required Manual Audit:**
  1. Select a stratified sample of 50 clauses from contract fixtures.
  2. Have 2 independent legal auditors assign labels from `{drafting_concern, possible_legal_issue, unsupported_finding}`.
  3. Calculate Cohen's Kappa ($\kappa$) and report inter-rater agreement before claiming benchmark validation.

---


