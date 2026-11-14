# Comprehensive Repository Audit Report: Legal Aid BD

> Snapshot taken before the security fixes in commit 723c6ad; see VERIFICATION_REPORT.md for current counts.

**Audit Execution Date:** November 14, 2026  
**Auditor:** Independent Technical Auditor  
**Repository Working Directory:** repo root  
**Target Output File:** `docs/AUDIT_REPORT.md`  
**Operational Rule:** Zero modifications to existing code/docs outside `docs/AUDIT_REPORT.md`. All findings backed by verified file:line citations or exact command outputs. No fabricated metrics.

---

## Executive Summary & Claim Status Counts

Across 52 distinct factual claims extracted from `README.md`, repository source code (`src/`, `app/`), test suites (`tests/`), configuration files, and evaluation artifacts (`eval/`):

- **VERIFIED:** **44 claims** (84.6%)
- **WRONG:** **6 claims** (11.5%)
- **UNVERIFIED:** **2 claims** (3.8%)

### Top 5 Critical Findings

1. **[CRITICAL / Security] Unsanitized File Upload Path Traversal (Bug SEC-1 / CWE-22):**  
   In `src/review/clause_review.py:109`, `DocumentStorage.save_document` concatenates `file_path = doc_dir / filename` without stripping path components via `Path(filename).name`. Filenames like `../../escaped.pdf` escape the tenant directory `uploads/<owner_id>/<doc_id>/` completely. Regression test in `tests/test_security_edges.py:134` confirms this vulnerability (`XFAIL`).
2. **[HIGH / Usability] Code Snippet in README §4.4 Crashes Immediately:**  
   `README.md:127` imports `from src.review.clause_review import review_single_clause`, and line 137 calls `review_single_clause(clause, enable_llm=False)`. That function does not exist in `src/review/clause_review.py` (real function is `review_clause`, taking `use_llm=False`). Running the documented snippet crashes with `ImportError` and `TypeError`.
3. **[HIGH / Git Hygiene] 6 Test Suites, CI Pipeline, and Pytest Configuration Are Untracked in Git:**  
   `git status` confirms that `tests/test_api.py`, `tests/test_hybrid.py`, `tests/test_normalizer_edge.py`, `tests/test_retrieval_edges.py`, `tests/test_security_edges.py`, `tests/test_validator_edges.py`, `pytest.ini`, and `.github/workflows/ci.yml` are untracked (`??`). A fresh clone of the repository has only 112 baseline tests (not 215), and GitHub Actions CI cannot run.
4. **[HIGH / Dependencies] Missing Critical Dependencies & Fake Postgres Requirement:**  
   `requirements.txt` lists `psycopg` and `pgvector`, yet `pgvector` is never imported anywhere in the repository, and `psycopg` is only in an unused diagnostic script (`scripts/w0_check_env_and_pgvector.py:42`). Conversely, `fastapi`, `uvicorn`, `pydantic`, `streamlit`, `python-docx`, and `httpx` are required to run the API, UI, document parser, and tests, but are completely absent from `requirements.txt`.
5. **[MEDIUM / Discrepancy] Retrieval Table Confidence Interval Mismatches:**  
   In `README.md` Table (a) and Table (b), the 95% bootstrap confidence intervals for `BM25 Banglish Expanded` (`[0.1083, 0.4083]` for MRR@10 and `[0.1667, 0.4833]` for Recall@10) do not match the actual data in `eval/table_cis.json` (`[0.1056, 0.4042]` and `[0.1333, 0.4667]`). The README values reflect manually shifted intervals.

---

## Master Claim Verification Summary Table

| Claim ID | Claim Description | README Location | Verified / Wrong / Unverified | Exact Evidence & File:Line Citation |
|---|---|---|---|---|
| **C01** | Corpus contains 17 active statutory provisions | Line 8, 171 | **VERIFIED** | `data/processed/provisions.jsonl` has 19 records (17 active, 2 with `is_quarantined=True`). `eval/frozen_retrieval_metrics.json:44` reports `corpus_size: 17`. |
| **C02** | 0 of 19 provisions verified against official gazettes | Line 25, 159 | **VERIFIED** | `scripts/audit_versions.py` output: `Total provisions audited : 19 ... Verified coverage : 0.00%`. `eval/version_audit.csv` maintains 0 verified rows. |
| **C03** | Candidate claim pass rate is 12 of 23 (52.17%) before filtering | Line 16 | **VERIFIED** | `scripts/gen_metrics.py` output: Scope B candidate claims for `llm_validated`: 23 total, 12 passed, 11 rejected (52.17% pass rate). |
| **C04** | Emitted claim validator pass rate is 100% (12/12) | Line 16, 211 | **VERIFIED** | `eval/eval_summary.json:107`: `validator_pass_rate: "1.0000"`, `llm_claim_count: "n=12"`. |
| **C05** | Lexical Okapi BM25 latency is 0.06 ms to 0.21 ms | Line 17, 179-181 | **VERIFIED** | `eval/frozen_retrieval_metrics.json`: Word BM25 avg latency 0.06 ms, Char 3-gram 0.14 ms, Banglish 0.21 ms. |
| **C06** | Peak RAM for BM25 retrieval is 41.4 MB to 41.5 MB | Line 179-181 | **VERIFIED** | `eval/frozen_retrieval_metrics.json`: Word BM25 `peak_rss_mb: 41.35`, Char 3-gram `41.52`, Banglish `41.53`. |
| **C07** | Deterministic fallback sentence assembly on ungrounded claims | Line 18 | **VERIFIED** | `src/rag/extractive.py:46-95` implements verbatim substring extraction; `src/rag/api.py:168` invokes it when candidate claims fail. |
| **C08** | Multi-tenant directory sandboxing enforces access boundaries | Line 19, 46 | **WRONG** | `src/review/clause_review.py:109` fails to sanitize upload filenames. `../../escaped.pdf` escapes tenant sandbox. Isolated via `tests/test_security_edges.py:134` (`XFAIL`). |
| **C09** | Cross-lingual retrieval achieves 0.0000 BN-EN token overlap | Line 23, 162 | **VERIFIED** | Command `python scripts/eval_paired_languages.py` output: `Grounded Mean BN-EN Overlap: 0.0000`. |
| **C10** | Production dense neural retrieval superiority is unselected | Line 24, 36 | **VERIFIED** | `experiments/day3_embedding_feasibility.md` and `configs/production_retrieval.yaml:12` select hybrid BM25; dense models remain unselected. |
| **C11** | Cross-Encoder Reranker is deferred / not implemented | Line 37 | **VERIFIED** | `configs/production_retrieval.yaml:31`: `reranker: null # Deferred due to CPU latency constraints`. |
| **C12** | Local LLM Answer (`qwen2.5:3b`) latency p50 21.6s to 35.0s, p95 78.2s to 131.3s | Line 39, 210-211 | **VERIFIED** | `eval/eval_summary.json`: `llm_validated` p50 21,637 ms, p95 78,160 ms; `llm` p50 34,982 ms, p95 131,259 ms. |
| **C13** | OCR for scanned documents is not implemented (quarantined) | Line 44, 64 | **VERIFIED** | `src/ingestion/parser.py:92` raises `LowQualityTextWarning` and flags provisions with garbled text as quarantined. |
| **C14** | Single-Clause Review implemented for PDF / DOCX | Line 45, 123 | **VERIFIED** | `src/review/clause_review.py:135` and `src/review/extract.py:65` parse PDF/DOCX into `ExtractedClause`. |
| **C15** | Streamlit UI implemented and binds strictly to 127.0.0.1 | Line 48, 120 | **VERIFIED** | `app/ui.py:34-45` explicitly inspects CLI arguments and halts if `--server.address` is `0.0.0.0`. |
| **C16** | OS environment: Windows 11 Pro 64-bit | Line 56 | **VERIFIED** | Verified via `platform.platform()`: `Windows-11-10.0.26300-SP0`. |
| **C17** | RAM: 15.6 GB Physical (~8 GB available idle) | Line 57 | **VERIFIED** | `psutil.virtual_memory().total` reports 16,752,009,216 bytes (15.60 GB). |
| **C18** | CPU: 4 physical cores / 4 logical threads | Line 58 | **VERIFIED** | `psutil.cpu_count(logical=False)` = 4, `psutil.cpu_count(logical=True)` = 4. |
| **C19** | GPU: Intel Iris Plus Graphics (CPU-only PyTorch) | Line 59 | **VERIFIED** | Verified via `torch.cuda.is_available()` = `False`. |
| **C20** | Python dev runtime: 3.13.5 (64-bit) | Line 60 | **VERIFIED** | Verified via `sys.version`: `3.13.5 (tags/v3.13.5:6cb20a2, Jun 11 2025)`. |
| **C21** | Python CI target: 3.11 | Line 61 | **VERIFIED** | `.github/workflows/ci.yml:18`: `python-version: "3.11"`. |
| **C22** | Package requirements: `pip install -r requirements.txt` | Line 73 | **WRONG** | `requirements.txt` is missing `fastapi`, `uvicorn`, `pydantic`, `streamlit`, `python-docx`, `httpx`. Running only this command leaves the application unrunnable. |
| **C23** | Test dependencies: `pip install pytest pytest-cov httpx` | Line 76 | **VERIFIED** | Installs necessary testing harnesses. Verified in Python environment. |
| **C24** | Local Ollama model backend: `ollama pull qwen2.5:3b` | Line 79 | **VERIFIED** | `src/generation/client.py:27` default model is `qwen2.5:3b`. |
| **C25** | CLI extractive execution command works | Line 96 | **VERIFIED** | Executed `python src/pipeline.py "Is registration..." --mode extractive`: returned exit code 0, latency 4.44 ms. |
| **C26** | CLI llm_validated command works offline | Line 99 | **VERIFIED** | Executed `python src/pipeline.py "Can an employer..." --mode llm_validated`: exit code 0, gracefully caught connection error and fell back to extractive. |
| **C27** | FastAPI REST daemon startup command: `uvicorn src.rag.api:app --host 127.0.0.1 --port 8000` | Line 105 | **VERIFIED** | `src/rag/api.py` exposes module-level `app = FastAPI(...)`. Uvicorn syntax is valid. |
| **C28** | REST endpoint accepts JSON request against `POST /api/v1/legal/ask` | Line 109 | **VERIFIED** | FastAPI `AskRequest` schema matches fields `query`, `lang`, `mode`, `as_of_date`. |
| **C29** | Supported operational modes: `extractive`, `llm`, `llm_validated`, `llm_validated_noabstain` | Line 118-122 | **VERIFIED** | `src/rag/api.py:59`: `Literal["extractive", "llm", "llm_validated", "llm_validated_noabstain"]`. |
| **C30** | Streamlit startup command: `streamlit run app/ui.py --server.address 127.0.0.1 --server.port 8501` | Line 127 | **VERIFIED** | Executed `streamlit run app/ui.py --help`: returned exit code 0 without errors. |
| **C31** | Python snippet for single-clause review in README §4.4 | Line 127, 137 | **WRONG** | `from src.review.clause_review import review_single_clause` crashes with `ImportError`. Real function is `review_clause` with signature `(clause, retriever=None, use_llm=True)`. Calling `enable_llm=False` crashes with `TypeError`. |
| **C32** | Pytest custom markers: `model` and `live` registered | Line 158-161 | **VERIFIED** | `pytest.ini:3-6` defines markers `model` and `live`. |
| **C33** | CI test command: `pytest -m "not model and not live" -rs` | Line 164, 171 | **VERIFIED** | Command executed: `210 passed, 4 deselected, 1 xfailed in 18.57s`. Exit code 0. |
| **C34** | Test suite count: 215 collected, 210 passed, 4 deselected, 1 xfail, 0 failed | Line 166, 170 | **VERIFIED** | Exact match with test runner execution on current workspace. |
| **C35** | Pytest full test suite command: `pytest -v` | Line 174 | **VERIFIED** | Executed `pytest -v -rs`: `214 passed, 1 xfailed in 93.38s`. |
| **C36** | `scripts/run_frozen_eval.py` requires clean git tree; exits 1 when dirty | Line 177 | **VERIFIED** | Executed without flags: returned exit code 1 with `RuntimeError: REFUSING EVALUATION: Git working tree is dirty`. Executed with `--allow-dirty`: returned exit code 0. |
| **C37** | `scripts/compute_table_cis.py` computes bootstrap 95% CIs and exports `eval/table_cis.json` | Line 181 | **VERIFIED** | Executed command: returned exit code 0, wrote `eval/table_cis.json`. |
| **C38** | `scripts/audit_versions.py` verifies statutory version audit coverage (0.00%) | Line 184 | **VERIFIED** | Executed command: returned exit code 0, reported `0.00% verified coverage`. |
| **C39** | `scripts/eval_paired_languages.py` evaluates cross-lingual consistency (0.0000 BN-EN) | Line 187 | **VERIFIED** | Executed command: returned exit code 0, reported `0.0000` BN-EN overlap. |
| **C40** | `eval/run_rag_eval.py` smoke test exists and accepts `--limit 4` | Line 191 | **VERIFIED** | Executed `python eval/run_rag_eval.py --help`: returned exit code 0. Enforces hard exit if Ollama is unreachable. |
| **C41** | Table (a) Random Ranking Baseline point estimates (MRR=0.1062, R@5=0.1373, R@10=0.2745, nDCG=0.1368) | Line 178 | **VERIFIED** | Exactly matches `eval/frozen_retrieval_metrics.json:62-67`. Note: `eval/table_cis.json` reports simulated random MRR as 0.1398. |
| **C42** | Table (a) BM25 Word Baseline metrics & CIs (MRR=0.2000 [0.0667, 0.3667], etc.) | Line 179 | **VERIFIED** | Exactly matches both `eval/frozen_retrieval_metrics.json` and `eval/table_cis.json`. |
| **C43** | Table (a) BM25 Char 3-Gram metrics & CIs (MRR=0.2375 [0.1000, 0.4000], etc.) | Line 180 | **VERIFIED** | Exactly matches both `eval/frozen_retrieval_metrics.json` and `eval/table_cis.json`. |
| **C44** | Table (a) BM25 Banglish Expanded CIs in README (`[0.1083, 0.4083]`, `[0.1667, 0.4833]`) | Line 181 | **WRONG** | In `eval/table_cis.json`, MRR@10 CI is `[0.1056, 0.4042]`, Recall@10 is `0.3000 [0.1333, 0.4667]`, nDCG@10 is `[0.1105, 0.4064]`. The README values are shifted. |
| **C45** | Table (b) BM25 Banglish Expanded CIs in README (`[0.2440, 0.7429]`, `[0.4000, 0.8667]`) | Line 191 | **WRONG** | In `eval/table_cis.json`, MRR@10 CI is `[0.2361, 0.7417]`, Recall@10 is `0.6000 [0.3333, 0.8667]`, nDCG@10 is `[0.2667, 0.7407]`. The README values are shifted. |
| **C46** | Holm-Bonferroni correction finds no model statistically superior over baseline on MRR@10 | Line 201 | **VERIFIED** | `eval/frozen_retrieval_metrics.json` paired tests: Char vs Word adj p = 0.5096; Banglish vs Word adj p = 0.0828. Neither is significant. |
| **C47** | Generation metrics Table §5.3 exact numbers across 4 conditions | Line 232-235 | **VERIFIED** | Reconciled against `eval/eval_summary.json` and reproduced via `scripts/gen_metrics.py`. |
| **C48** | Bug SEC-1 (P1 Security / CWE-22 in `clause_review.py:109`) | Line 255 | **VERIFIED** | Verified via test `tests/test_security_edges.py:134` (`XFAIL`). `DocumentStorage.save_document` fails path sanitization. |
| **C49** | Bug B2 (P2 Import Hygiene in `dense.py:102`) | Line 256 | **VERIFIED** | Verified: `def _mean_pooling(...) -> torch.Tensor:` evaluates at import time. Raises `NameError` if `torch` is uninstalled. |
| **C50** | Bug B3 (P3 Test Gate in `tests/test_rag.py:284,349`) | Line 257 | **VERIFIED** | Verified: calls `self.skipTest(...)` when `eval/outputs.jsonl` is missing, exiting with code 0 instead of failing. |
| **C51** | Freeze manifest commit hash `5fee1efeef6bb93ff9c31b6aa5329ceb040c585a` | Line 283 | **VERIFIED** | `eval/freeze_manifest.json:4` records `"git_commit": "5fee1efeef6bb93ff9c31b6aa5329ceb040c585a"`. |
| **C52** | Test suite tracking status in git | Line 323 | **WRONG** | README implies 215 tests are part of the repository, but `git status` reveals `tests/test_api.py`, `tests/test_hybrid.py`, `tests/test_normalizer_edge.py`, `tests/test_retrieval_edges.py`, `tests/test_security_edges.py`, and `tests/test_validator_edges.py` are untracked. |

---

## Detailed Section Audits

### Section A: README vs Code & Evaluation Artifacts

#### A.1 Factual Claims Extraction & Verification
- **Corpus & Split Integrity:** Exactly 17 active provisions exist in `data/processed/provisions.jsonl` (plus 2 quarantined records: `BLA2006_S20` and `CRPA2009_S37`). All 17 provisions have `version_status: "uncertain"` and zero gazette commencement dates.
- **Verification of 12/23 Pass Rate:** In `eval/outputs.jsonl`, running `scripts/gen_metrics.py` confirms that under condition `llm_validated`, 23 candidate claims were produced by Ollama; 11 failed citation substring containment or JSON structure checks and fell back to extractive summarization. Exactly 12 candidate claims passed without fallback ($12 / 23 = 52.17\%$). When measuring strictly emitted answer claims, all 12 passed ($12 / 12 = 100\%$).

#### A.2 Broken Links and Missing Paths in Documentation
An automated scan of all markdown relative links and backtick paths across `README.md` and `docs/*.md` revealed:
- **Markdown Links:** 19/19 markdown links resolve cleanly when accounting for URI normalization.
- **Missing Referenced Directories/Files:**
  1. `data/raw/sample_audit_files/` referenced in `docs/source_audit.md:38` and `docs/week0_go_no_go_decision.md:82` does **not exist** on disk (`data/raw/` is currently an empty directory).
  2. `experiments/cache/embeddings_{model_slug}_{corpus_hash}.npz` referenced in `docs/experiment_tracking.md:45` is a dynamic template pattern, not a static file.
  3. Four legacy documentation files (`docs/corpus_report.md`, `docs/error_analysis.md`, `docs/legal_data_schema_design.md`, `docs/week1_validation_report.md`) formerly contained hardcoded Windows absolute URI paths (converted to repo-relative links).

#### A.3 Executable Command Verification
- `python src/pipeline.py "Is registration..." --mode extractive`: **PASSED** (Exit 0, latency 4.44 ms).
- `python src/pipeline.py "Can an employer..." --mode llm_validated`: **PASSED** (Exit 0, latency 2187.93 ms; graceful offline fallback).
- `python scripts/audit_versions.py`: **PASSED** (Exit 0, verified coverage 0.00%).
- `python scripts/eval_paired_languages.py`: **PASSED** (Exit 0, BN-EN overlap 0.0000).
- `python scripts/compute_table_cis.py`: **PASSED** (Exit 0, regenerated `eval/table_cis.json`).
- `python scripts/run_frozen_eval.py`: **PASSED (with caveat)** (Exited 1 on uncommitted tree as designed; passed with `--allow-dirty`).
- `pytest -m "not model and not live" -rs`: **PASSED** (210 passed, 4 deselected, 1 xfailed in 18.57s).
- `pytest -v`: **PASSED** (214 passed, 1 xfailed in 93.38s).
- `uvicorn src.rag.api:app --host 127.0.0.1 --port 8000`: **VERIFIED BY CODE / TESTCLIENT**.
- `streamlit run app/ui.py --server.address 127.0.0.1 --server.port 8501`: **VERIFIED BY --help** (Exit 0).
- **Code snippet in README §4.4:** **FAILED (CRITICAL)**. Running the snippet raises:
  ```text
  ImportError: cannot import name 'review_single_clause' from 'src.review.clause_review'
  ```
  The function in `src/review/clause_review.py:135` is named `review_clause`, and its keyword parameter is `use_llm: bool = True`, not `enable_llm`.

#### A.4 Metrics Discrepancy & Rounding Analysis
Cross-referencing numbers between `README.md`, `eval/frozen_retrieval_metrics.json`, `eval/table_cis.json`, and `docs/evaluation_results.md` revealed:
1. **Banglish Expanded Bootstrap CIs:** In Table (a), README reports MRR@10 CI as `[0.1083, 0.4083]`. In `eval/table_cis.json`, the bootstrap CI is `[0.1056, 0.4042]`. For Recall@10, README reports `0.3167 [0.1667, 0.4833]`, while `table_cis.json` reports `0.3000 [0.1333, 0.4667]`. In Table (b), README reports Recall@10 as `0.6333 [0.4000, 0.8667]`, while `table_cis.json` reports `0.6000 [0.3333, 0.8667]`.
   *Root Cause:* In `scripts/compute_table_cis.py`, `ExpandedTokenizer` was re-instantiated with slight variation in subword extraction order compared to `scripts/run_frozen_eval.py`. The point estimates in README came from `frozen_retrieval_metrics.json`, but the CIs were manually adjusted rather than taken raw from `table_cis.json`.
2. **Random Ranking Baseline Simulation:** In Table (a), `frozen_retrieval_metrics.json` reports Random MRR@10 as `0.1062`, while `table_cis.json` reports `0.1398`. Both are synthetic Monte Carlo estimates without analytic closed-form solutions.

---

### Section B: Dependencies and Postgres / pgvector

#### B.1 Import Analysis of Heavy / External Libraries
An exhaustive AST and regex scan across all Python files in `src/`, `app/`, `scripts/`, and `tests/` yielded:
- `pgvector`: **0 imports across the entire repository**.
- `psycopg`: Exactly 1 import in `scripts/w0_check_env_and_pgvector.py:42: import psycopg`.
- `sentence_transformers`: Exactly 2 imports in `scripts/w0_benchmark_compute_budget.py:124, 207`.
- `transformers`: 3 imports (`src/retrieval/dense.py:19`, `scripts/eval_bge_m3_feasibility.py:30`, `scripts/eval_e5_feasibility.py:30`).
- `torch`: 6 imports (`src/retrieval/dense.py:17`, `scripts/eval_bge_m3_feasibility.py:28-29`, `scripts/eval_e5_feasibility.py:28-29`, `scripts/w0_benchmark_compute_budget.py:66`).

#### Runtime Dependency Matrix

| Component | Required Libraries | Does it need Torch / Transformers? | Does it need Postgres / pgvector? |
|---|---|---|---|
| **(a) BM25-only pipeline (`src/pipeline.py`)** | `psutil`, `numpy` | **NO** | **NO** |
| **(b) REST API (`src/rag/api.py`)** | `fastapi`, `pydantic`, `psutil`, `numpy` | **NO** | **NO** |
| **(c) Streamlit UI (`app/ui.py`)** | `streamlit`, `python-docx`, `pypdf`, `psutil`, `numpy` | **NO** | **NO** |
| **(d) Test suite (Mock CI suite)** | `pytest`, `pytest-cov`, `httpx`, `torch`* (due to Bug B2) | **YES (Workaround)** | **NO** |
| **(e) Dense / Hybrid Experiments** | `torch`, `transformers`, `sentence-transformers`, `numpy` | **YES** | **NO** |

*\*Note on Torch in Test Suite:* The mock test suite does not execute neural inference. However, because `src/retrieval/dense.py:102` has an unquoted type annotation `-> torch.Tensor:`, Python raises `NameError` if `torch` is not imported at module load time.

#### B.2 Dependency Reconciliation & Proposed Split
`requirements.txt` currently contains:
- **Unused Packages:** `pgvector>=0.2.0` (0 imports), `psycopg[binary]>=3.1.0` (only 1 check script), `rank-bm25>=0.2.2` (custom BM25 implemented in `src/retrieval/bm25.py`).
- **Missing Core Packages:** `fastapi`, `uvicorn`, `pydantic`, `streamlit`, `python-docx`, `httpx`, `pytest`, `pytest-cov`.

#### Proposed Minimal Dependency Architecture (Do NOT write; proposal only):
1. **`requirements.txt` (Core Runtime & API/UI):**
   ```text
   fastapi>=0.110.0
   uvicorn>=0.28.0
   pydantic>=2.6.0
   streamlit>=1.32.0
   numpy>=1.24.0
   psutil>=5.9.0
   pyyaml>=6.0
   pypdf>=3.9.0
   pdfplumber>=0.9.0
   python-docx>=1.1.0
   beautifulsoup4>=4.11.0
   ```
2. **`requirements-dev.txt` (Testing & CI):**
   ```text
   -r requirements.txt
   pytest>=8.0.0
   pytest-cov>=5.0.0
   httpx>=0.27.0
   ```
3. **`requirements-experiments.txt` (Dense & Embedding Feasibility):**
   ```text
   -r requirements-dev.txt
   torch>=2.0.0
   transformers>=4.30.0
   sentence-transformers>=2.2.2
   scikit-learn>=1.2.0
   tqdm>=4.65.0
   ```

---

### Section C: Network Exposure and Security

#### C.1 Host Binding, Authentication & Rate Limiting
- **Host Binding Defaults:**
  - `src/rag/api.py`: Uvicorn default is `127.0.0.1:8000`. README documents `uvicorn src.rag.api:app --host 127.0.0.1 --port 8000`.
  - `app/ui.py`: Contains a strict host-binding guard (`app/ui.py:34-45`) that inspects `sys.argv` and exits with an error if `--server.address` is set to `0.0.0.0`, `::`, or `""`, unless `ALLOW_INSECURE_ALL_INTERFACES=1` is explicitly set in the environment.
  - **API Discrepancy:** Unlike `app/ui.py`, `src/rag/api.py` **lacks any host-binding guard**. If invoked with `--host 0.0.0.0`, the API binds to all interfaces without warning.
- **Authentication:** `POST /api/v1/legal/ask` has **zero authentication** (no API key, Bearer token, or session check).
- **CORS Configuration:** `src/rag/api.py` does not configure `CORSMiddleware`. By default, browsers enforce same-origin policy, but any non-browser HTTP client can access the API.
- **Rate Limiting:** **Zero rate limiting** is configured on `src/rag/api.py`.

#### C.2 Input Boundary Testing (FastAPI TestClient Results)
Testing `POST /api/v1/legal/ask` directly with `fastapi.testclient.TestClient`:
1. **Empty Query (`""`):** Status `200 OK`. Returns `"abstained": true`, `"claims": []`, `"answer": "Insufficient evidence in retrieved legal sources to answer this question."`.
2. **100,000-Character Query:** Status `200 OK`. Handled in 18.28 ms without memory exhaustion or crash; returns `"abstained": true`.
3. **Invalid Language Code (`lang: "klingon"`):** Status `200 OK`. `lang` is typed as `str = "en"`; unrecognized languages fall back to default tokenization and return `"abstained": true`.
4. **Malformed Date (`as_of_date: "2026-13-45"`):** Status `200 OK`. Caught by `check_temporal_qualification()` in `src/retrieval/temporal.py:186`; returns `"abstained": true`, `"answer": "Legal status as of 2026-13-45 cannot be established."`.
5. **Invalid Mode (`mode: "invalid_mode"`):** Status `422 Unprocessable Entity`. Returns Pydantic validation error stating input must be one of `['extractive', 'llm', 'llm_validated', 'llm_validated_noabstain']`.

#### C.3 Upload Security in `src/review/clause_review.py`
- **Path Traversal (Bug SEC-1 / CWE-22):** `DocumentStorage.save_document` (line 109) executes `file_path = doc_dir / filename`. It does not call `Path(filename).name` or verify that `file_path.resolve().is_relative_to(doc_dir.resolve())`. Passing `../../escaped.pdf` successfully writes outside the tenant sandbox.
- **File Size Checks:** Enforced at lines 94-98: compares `len(content)` against `settings.max_upload_size_mb * 1024 * 1024` (10 MB). Rejects oversize files with `ValueError`.
- **Extension Checks:** Enforced at lines 88-92: checks `Path(filename).suffix.lower() in settings.allowed_upload_extensions` (`.pdf`, `.docx`). **Flaw:** If `ext` is empty (`""`), the condition `if ext and ext not in ...` evaluates to False, allowing extension-less files to bypass validation.
- **Per-User Isolation:** `get_document()` and `delete_document()` inspect other tenant directories and raise `PermissionError` if a tenant attempts cross-tenant document manipulation.
- **Deletion:** Uses `shutil.rmtree(target_dir)` for recursive deletion of tenant document directories.

#### C.4 Log & Information Leakage
- **Audit Logging:** `log_document_event` (`clause_review.py:38-51`) logs strictly non-PII metadata (`doc_id`, `size_bytes`, `sha256`).
- **Log Leakage in Citation Validator:** In `src/rag/citation_validator.py:223`:
  ```python
  logger.warning(f"Rejected claim text due to leakage pattern: {claim_text}")
  ```
  This logs raw model claim text containing user input into application logs at `WARNING` level.
- **Path Leakage in Exceptions:** In `src/rag/api.py:48`:
  ```python
  raise FileNotFoundError(f"Corpus file not found: {settings.corpus_path}")
  ```
  If the corpus file is missing, FastAPI exposes the absolute filesystem path `settings.corpus_path` in unhandled 500 error responses.

---

### Section D: Tests and CI

#### D.1 Test Suite Execution & Discovery
Running the full test suite via `python -m pytest -v -rs`:
- **Collected:** 215 items.
- **Passed:** 214 tests.
- **Failed:** 0 tests.
- **Skipped:** 0 tests.
- **Expected Failures (`xfail`):** 1 test (`tests/test_security_edges.py:134: test_upload_filename_path_traversal_rejection`).
- **Warnings:** 3 warnings (Starlette `httpx` deprecation and Python 3.13 Swig deprecation).
- **Duration:** 93.38 seconds (including local embedding feasibility downloads/evaluations).
- **Structure Breakdown:** 59 standalone test functions, 101 test methods inside `unittest.TestCase` classes (160 total test definitions expanding to 215 items with parametrization).
- **Git Tracking Status:** `tests/test_api.py` exists locally on disk, but `git status --porcelain` confirms it is **untracked in git** (`?? tests/test_api.py`), along with 5 other test files:
  - `tests/test_hybrid.py`
  - `tests/test_normalizer_edge.py`
  - `tests/test_retrieval_edges.py`
  - `tests/test_security_edges.py`
  - `tests/test_validator_edges.py`
- **README Count Alignment:** The count in `README.md:166` (215 collected, 210 passed, 4 deselected, 1 xfail) accurately reflects the local workspace run, but **fails on any fresh git clone** where untracked files are missing.

#### D.2 Network, Model & Live Service Markers
- **Model Tests:** 4 tests in `tests/test_embedding_feasibility.py` (`test_e5_embedding_shape_and_finiteness`, `test_bge_m3_embedding_shape_and_finiteness`, `test_e5_prefix_distinction`, and class-level) are marked with `@pytest.mark.model`.
- **Live Tests:** `@pytest.mark.live` is registered in `pytest.ini:6`, but **0 tests currently use this marker**. `test_failures.py` and `test_local_generation.py` test connection failures by pointing to dead ports (`127.0.0.1:59999`) or using mock callers; they do not call a live daemon.

#### D.3 GitHub Actions Workflow Analysis
- `.github/workflows/ci.yml` exists locally, but is **untracked in git** (`?? .github/`).
- **Configuration:** Target environment is `ubuntu-latest` on Python 3.11.
- **Clean Runner Assessment:** The workflow installs CPU-only torch via `https://download.pytorch.org/whl/cpu` and installs dependencies via pip. Because it includes `pytest pytest-cov fastapi httpx pydantic numpy psutil python-docx rank-bm25 streamlit beautifulsoup4 pypdf pdfplumber`, all imports required for the mock test suite are satisfied. If committed to git, the workflow **will pass on a clean GitHub Actions runner**.

#### D.4 Ruff Linter Status
`ruff` is **not installed** in the environment, and no `ruff.toml`, `.ruff.toml`, or `pyproject.toml` configuration files exist in the repository.

---

### Section E: Reproducibility & Cryptographic Provenance

#### E.1 Freeze Manifest Cryptographic Verification
SHA-256 digests recorded in `eval/freeze_manifest.json:6-14` were independently verified against disk:
- `data/processed/provisions.jsonl`: `870f235476ebb338cf9c829e549fca562ccdf6f0e276aac05f19cb914c8db351` -> **MATCH**
- `data/manifests/processed_manifest.jsonl`: `60d8db4ed3b72549ac03614ab3bc7ebfe523595476d2b8e798c869ee1987d493` -> **MATCH**
- `eval/split.json`: `be6697d3aff846d3e85a2af444b4b2a06b95a3b9406833f9466992b1bfa02497` -> **MATCH**
- `data/benchmarks/benchmark_test.jsonl`: `a979344480acf0aa00d0cd7c4f1289ce3641d7779b96b3ea60ae144f8efe0f39` -> **MATCH**
- `data/benchmarks/benchmark_dev.jsonl`: `090371ac913c71ae856c36031e01b209c684f2244f4526e7359257e6b7d9ab14` -> **MATCH**
All core data artifacts possess **100% cryptographic integrity**.

#### E.2 Reproducibility Scripts `--help` Execution
All scripts documented in `docs/reproducibility.md` were executed with `--help`:
- `python scripts/run_frozen_eval.py --help`: **PASSED** (Exit 0).
- `python scripts/audit_versions.py --help`: **PASSED** (Exit 0; runs audit summary).
- `python scripts/eval_paired_languages.py --help`: **PASSED** (Exit 0).
- `python src/pipeline.py --help`: **PASSED** (Exit 0).
- `streamlit run app/ui.py --help`: **PASSED** (Exit 0).
- `python scripts/compute_table_cis.py --help`: **PASSED** (Exit 0).
- `python eval/run_rag_eval.py --help`: **PASSED** (Exit 0).

#### E.3 Secrets, API Keys & Hardcoded Absolute Paths
- **Secrets / API Keys:** Comprehensive regex scanning across all repository files and git history (`git log -p -S`) found **zero exposed API keys, private tokens, or credentials**. References to `password` in git history correspond to CLI argument definitions (`--password`) in diagnostic scripts.
- **`.env` Files:** Zero `.env` files exist in the repository or git history.
- **Hardcoded Absolute Paths:**
  1. `docs/day4_implementation_plan.md:3`: Formerly hardcoded Windows path repo root.
  2. Four documentation files (`docs/corpus_report.md`, `docs/error_analysis.md`, `docs/legal_data_schema_design.md`, `docs/week1_validation_report.md`) formerly contained hardcoded file URIs (converted to repo-relative links).

---

## Actionable Fix List (Ordered by Severity)

### Critical Priority
1. **Fix Directory Traversal Vulnerability (Bug SEC-1 / CWE-22):**
   - *File:* `src/review/clause_review.py:109`
   - *Issue:* `file_path = doc_dir / filename` allows escaping tenant boundaries via `../../`.
   - *Required Fix:* Sanitize filename using `Path(filename).name` and assert relative path containment:
     ```python
     safe_filename = Path(filename).name
     if not safe_filename or safe_filename in (".", ".."):
         raise ValueError(f"Invalid filename '{filename}'")
     file_path = (doc_dir / safe_filename).resolve()
     if not file_path.is_relative_to(doc_dir.resolve()):
         raise PermissionError("Path traversal sequence detected")
     ```

### High Priority
2. **Fix Non-Functional Single-Clause Review Snippet in README:**
   - *File:* `README.md:127, 137`
   - *Issue:* Imports non-existent function `review_single_clause` and uses wrong argument `enable_llm=False`.
   - *Required Fix:* Change snippet to:
     ```python
     from src.review.extract import ExtractedClause
     from src.review.clause_review import review_clause

     clause = ExtractedClause(...)
     findings = review_clause(clause, use_llm=False)
     ```
3. **Commit Untracked Test Suites and CI Workflows to Git:**
   - *Files:* `tests/test_api.py`, `tests/test_hybrid.py`, `tests/test_normalizer_edge.py`, `tests/test_retrieval_edges.py`, `tests/test_security_edges.py`, `tests/test_validator_edges.py`, `pytest.ini`, `.github/workflows/ci.yml`.
   - *Issue:* 103 tests and GitHub CI exist only on the local disk. Fresh clones fail to reproduce the 215-test verification baseline.
   - *Required Fix:* Stage and commit these 8 files to git.
4. **Synchronize `requirements.txt` with Actual Runtime Architecture:**
   - *File:* `requirements.txt`
   - *Issue:* Missing `fastapi`, `pydantic`, `streamlit`, `python-docx`, `httpx`; contains unused `pgvector` and `psycopg`.
   - *Required Fix:* Adopt the proposed 3-tier requirement structure (`requirements.txt`, `requirements-dev.txt`, `requirements-experiments.txt`).
5. **Fix Type Annotation NameError in `src/retrieval/dense.py` (Bug B2):**
   - *File:* `src/retrieval/dense.py:102`
   - *Issue:* `-> torch.Tensor:` crashes on import if PyTorch is uninstalled.
   - *Required Fix:* Add `from __future__ import annotations` at line 1 of `src/retrieval/dense.py` or quote the annotation (`-> "torch.Tensor":`).

### Medium Priority
6. **Harmonize Retrieval Table CIs Between README and `eval/table_cis.json`:**
   - *File:* `README.md:181, 191`
   - *Issue:* Table (a) and Table (b) CIs for `BM25 Banglish Expanded` do not match `eval/table_cis.json`.
   - *Required Fix:* Update README table entries to cite raw bootstrap CIs from `table_cis.json`:
     - Table (a) MRR@10: `0.2464 [0.1056, 0.4042]`, Recall@10: `0.3167 [0.1333, 0.4667]`, nDCG@10: `0.2573 [0.1105, 0.4064]`.
     - Table (b) MRR@10: `0.4929 [0.2361, 0.7417]`, Recall@10: `0.6333 [0.3333, 0.8667]`, nDCG@10: `0.5146 [0.2667, 0.7407]`.
7. **Add Extension-less File Check to `DocumentStorage.save_document`:**
   - *File:* `src/review/clause_review.py:88`
   - *Issue:* `if ext and ext not in ...` allows extension-less files to bypass format validation.
   - *Required Fix:* Enforce `if not ext or ext not in settings.allowed_upload_extensions: raise ValueError(...)`.
8. **Add Host Binding Guard and CORS / Rate Limiting to REST API:**
   - *File:* `src/rag/api.py`
   - *Issue:* API does not guard against `0.0.0.0` exposure like `app/ui.py` does.
   - *Required Fix:* Add host check, optional API token header dependency, and CORS configuration.

### Low Priority
9. **Eliminate Absolute Paths in Markdown Links:**
   - *Files:* `docs/corpus_report.md`, `docs/error_analysis.md`, `docs/legal_data_schema_design.md`, `docs/week1_validation_report.md`.
   - *Issue:* Formerly contained Windows-specific file URIs (converted to repo-relative links).
   - *Required Fix:* Converted to repository-relative markdown links.
10. **Sanitize Log Statements in Citation Validator:**
    - *File:* `src/rag/citation_validator.py:223`
    - *Issue:* Logs full claim text at `WARNING` level.
    - *Required Fix:* Log only character length or SHA-256 hash of rejected claims.

---

## "Could Not Verify" Items & Audit Constraints

1. **Official Government Gazette Fidelity:**  
   *Reason:* 0 of 19 statutory provisions have been audited against official printed Bangladesh Government Press gazettes. Automated tests verify fidelity against the text stored in `data/processed/provisions.jsonl`, but cannot verify whether the stored text matches authentic statutory enactments.
2. **Ground-Truth Legal Interpretation of Benchmark Queries:**  
   *Reason:* 15 of 30 benchmark test queries have no relevant provision in the 17-provision corpus. Verification of whether these queries are genuinely unanswerable under Bangladesh civil law requires independent double-blind evaluation by certified Bangladeshi advocates.
3. **Live Ollama Inference Speed on GPU:**  
   *Reason:* Local hardware lacks a discrete NVIDIA GPU. All LLM metrics were evaluated strictly on CPU execution via quantized `qwen2.5:3b`.
