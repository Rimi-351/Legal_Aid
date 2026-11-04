# Legal Aid BD: Cross-Script Multilingual Legal Retrieval and Grounded Answer Generation

Legal Aid BD is an academic research prototype evaluating cross-script, multilingual legal information retrieval and factual evidence-grounded answer generation for Bangladesh civil and commercial statutory law. The system processes inquiries across Bengali Unicode, Romanized Banglish transliteration, and English, applying custom character subword tokenization, deterministic citation verification, and fallback extractive summarization to eliminate ungrounded citations. This software is an experimental research system and does not provide legal advice, statutory interpretation, or legal representation.

---

> [!WARNING]
> **Research prototype. Results below come from a small corpus of 17 synthetic fixture provisions (formatted sample text files, not official government gazette publications). Not production. Not legal advice.**

---

## 1. Research Question & Empirical Scope

- **Research Question**: Can an end-to-end multilingual legal information retrieval and generation system reliably retrieve relevant provisions for Bangladesh statutory law across script variations (Bengali Unicode, Romanized Banglish, English) while preventing hallucinated legal citations via deterministic verification?
- **What is Supported by Evidence**:
  - Deterministic string-containment citation validation filters emitted claims against retrieved text fixtures. The reported 100% validator pass rate for emitted claims is measured strictly after filtering; before filtering, the LLM-produced candidate claim pass rate is 12 of 23 (52.17%). Exact substring containment verifies that quoted text exists in the database record, but does not prove the quote semantically supports the substantive legal claim.
  - Okapi BM25 with character 3-gram subwords and phonetic dictionary expansion executes deterministically on local CPU in sub-second latency (0.06 ms to 0.21 ms, per `eval/frozen_retrieval_metrics.json`).
  - Extractive statutory sentence assembly provides a deterministic fallback when candidate generative claims fail citation validation.
  - Multi-tenant directory sandboxing enforces access boundaries and recursive deletion in synthetic test scenarios.
- **What is NOT Claimed**:
  - Production readiness for legal advice, litigation, or real-world citizen guidance is NOT claimed.
  - Statistical superiority of character 3-gram BM25 over standard word BM25 is NOT claimed across the overall test split (Holm-adjusted confidence intervals include 0).
  - Cross-lingual retrieval from Bengali Unicode to English statutory text is NOT claimed (achieves 0.0000 Jaccard token overlap in lexical matching - possible metric artifact (record_id vs (act, section)), unverified).
  - Production dense neural retrieval superiority is NOT claimed (dense models remain unselected feasibility candidates).
  - Historical statutory status accuracy is NOT claimed (0 of 19 provisions [17 active + 2 quarantined] have verified commencement dates).

---

## 2. System Features & Implementation Status

<table>
  <thead>
    <tr>
      <th width="20%">Feature / Component</th>
      <th width="8%">Implemented</th>
      <th width="20%">Tested On What</th>
      <th width="20%">Evidence File</th>
      <th width="32%">Operational Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>BM25 Word Baseline</b></td>
      <td align="center">YES</td>
      <td>Held-out test split (n=30 answerable)</td>
      <td><code>eval/frozen_retrieval_metrics.json</code>, <code>eval/table_cis.json</code></td>
      <td><b>Experimental</b> (per-condition CIs overlap random baseline; at R@10 Word/Char are at or below random since top-10 covers 59% of a 17-provision corpus; n=15)</td>
    </tr>
    <tr>
      <td><b>Char N-Gram BM25 (Production)</b></td>
      <td align="center">YES</td>
      <td>Held-out test split (n=30 answerable)</td>
      <td><code>eval/frozen_retrieval_metrics.json</code>, <code>eval/table_cis.json</code></td>
      <td><b>Experimental</b> (per-condition CIs overlap random baseline; at R@10 Word/Char are at or below random since top-10 covers 59% of a 17-provision corpus; n=15)</td>
    </tr>
    <tr>
      <td><b>Banglish Query Expansion</b></td>
      <td align="center">YES</td>
      <td>Held-out test split (n=4 Banglish queries)</td>
      <td><code>eval/frozen_retrieval_metrics.json</code>, <code>eval/table_cis.json</code></td>
      <td><b>Experimental</b> (tiny sample size n=4; not significantly better)</td>
    </tr>
    <tr>
      <td><b>Dense Retrieval (E5 / BGE-M3)</b></td>
      <td align="center">YES</td>
      <td>Exploratory feasibility scripts (not on test split)</td>
      <td><code>experiments/day3_embedding_feasibility.md</code></td>
      <td><b>Experimental / Provisional</b> (unselected)</td>
    </tr>
    <tr>
      <td><b>Cross-Encoder Reranker</b></td>
      <td align="center">NO</td>
      <td>Deferred due to CPU latency budget</td>
      <td><code>configs/production_retrieval.yaml</code></td>
      <td><b>Not Implemented / Deferred</b></td>
    </tr>
    <tr>
      <td><b>Extractive Answer Generation</b></td>
      <td align="center">YES</td>
      <td>Held-out test split (n=42)</td>
      <td><code>eval/eval_summary.json</code></td>
      <td><b>Validated</b> (on fixture corpus N=17)</td>
    </tr>
    <tr>
      <td><b>Local LLM Answer (<code>qwen2.5:3b</code>)</b></td>
      <td align="center">YES</td>
      <td>Held-out test split (n=42)</td>
      <td><code>eval/eval_summary.json</code></td>
      <td><b>Experimental</b> (high latency 21-35s, 26-60% fallback)</td>
    </tr>
    <tr>
      <td><b>Citation Validator</b></td>
      <td align="center">YES</td>
      <td>Held-out test split (n=42 queries)</td>
      <td><code>eval/eval_summary.json</code>, <code>tests/test_quote_path.py</code></td>
      <td><b>Validated</b> (exact substring containment gate)</td>
    </tr>
    <tr>
      <td><b>Abstention Gate (T=30.0)</b></td>
      <td align="center">YES</td>
      <td>Test split scores inspected prior to choice</td>
      <td><code>eval/eval_summary.json</code>, <code>eval/threshold_sweep.csv</code></td>
      <td><b>Experimental</b> (no clean holdout)</td>
    </tr>
    <tr>
      <td><b>Temporal Versioning (<code>as_of_date</code>)</b></td>
      <td align="center">YES</td>
      <td>Synthetic unit tests (<code>tests/test_versions.py</code>)</td>
      <td><code>eval/version_audit.csv</code></td>
      <td><b>Experimental</b> (0 of 19 provisions verified)</td>
    </tr>
    <tr>
      <td><b>Clause Extraction (PDF / DOCX)</b></td>
      <td align="center">YES</td>
      <td>3 synthetic document fixtures</td>
      <td><code>tests/fixtures/synthetic_commercial_lease.pdf</code></td>
      <td><b>Experimental</b> (synthetic fixtures only)</td>
    </tr>
    <tr>
      <td><b>OCR for Scanned Documents</b></td>
      <td align="center">NO</td>
      <td>Quarantines low-quality text; no Tesseract</td>
      <td><code>src/ingestion/parser.py</code>, <code>eval/diagnosis.json</code></td>
      <td><b>Not Implemented</b></td>
    </tr>
    <tr>
      <td><b>Single-Clause Review</b></td>
      <td align="center">YES</td>
      <td>Synthetic fixtures and heuristic rules</td>
      <td><code>tests/test_review.py</code></td>
      <td><b>Experimental</b> (synthetic rules/fixtures)</td>
    </tr>
    <tr>
      <td><b>Document Isolation & Deletion</b></td>
      <td align="center">YES</td>
      <td>Directory sandboxing and unit tests</td>
      <td><code>tests/test_review.py</code></td>
      <td><b>Experimental</b> (synthetic unit tests only)</td>
    </tr>
    <tr>
      <td><b>FastAPI Endpoint (<code>/ask</code>)</b></td>
      <td align="center">YES</td>
      <td>Synthetic unit tests (<code>tests/test_rag.py</code>)</td>
      <td><code>src/rag/api.py</code>, <code>tests/test_rag.py</code></td>
      <td><b>Experimental</b> (no auth, unverified under load)</td>
    </tr>
    <tr>
      <td><b>Streamlit UI</b></td>
      <td align="center">YES</td>
      <td>Synthetic component tests & manual checklist</td>
      <td><code>tests/test_ui.py</code>, <code>docs/ui_manual_check.md</code></td>
      <td><b>Experimental</b> (no human user study)</td>
    </tr>
    <tr>
      <td><b>Multilingual Pipeline</b></td>
      <td align="center">YES</td>
      <td>36 paired cross-language queries</td>
      <td><code>scripts/eval_paired_languages.py</code></td>
      <td><b>Experimental</b> (0.0000 BN-EN overlap - possible metric artifact (record_id vs (act, section)), unverified)</td>
    </tr>
    <tr>
      <td><b>Voice Interface</b></td>
      <td align="center">NO</td>
      <td>Not present in codebase</td>
      <td>None</td>
      <td><b>Not Implemented</b></td>
    </tr>
  </tbody>
</table>

## 3. Hardware Constraints & Environment

- **OS**: Microsoft Windows 11 Pro 64-bit (Build 10.0.26300, verified via systeminfo)
- **RAM**: 15.6 GB Physical (~8 GB available idle, verified via psutil)
- **CPU**: 4 physical cores / 4 logical threads (verified via psutil)
- **GPU**: Intel Iris Plus Graphics (No discrete NVIDIA GPU; CPU-only PyTorch)
- **Python**: 3.13.5 (64-bit, verified via python --version)
- **Memory Safety Ceiling**: Total process RSS $\le 11.5\text{ GB}$
- **Local Model Backend**: Ollama runtime serving `qwen2.5:3b`
- **Tesseract OCR**: Not installed; scanned documents are quarantined

### Installation Commands
```bash
# 1. Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\activate  # On Linux/macOS: source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Pull required local model weights via Ollama
ollama pull qwen2.5:3b
```

*Note on Packages*: `rank-bm25` is not required as a custom in-memory subword BM25 engine is implemented directly in `src/retrieval/bm25.py`. PDF text extraction uses `pypdf 6.16.2`.

---

## 4. Usage Guide

### 4.1 CLI Pipeline Execution
Run statutory question answering using the verified functional entry point:
```bash
# Extractive summarization mode (verified in audit: 23.55 ms latency)
python src/pipeline.py "Is registration of a deed mandatory to transfer ownership of immovable property?" --mode extractive

# Validated generative mode (not verified in audit; calls local LLM)
python src/pipeline.py "Can an employer terminate a permanent worker without notice?" --mode llm_validated
```

### 4.2 FastAPI HTTP Service
Start the REST API daemon on local loopback (not verified in audit; requires background daemon):
```bash
uvicorn src.rag.api:app --host 127.0.0.1 --port 8000
```
Execute queries against `POST /api/v1/legal/ask` (not verified in audit; requires running daemon):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/legal/ask" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Is registration of a deed mandatory to transfer ownership of immovable property?",
       "lang": "en",
       "mode": "extractive",
       "as_of_date": null
     }'
```
Supported operational modes:
- `extractive`: Verbatim statutory sentence assembly.
- `llm`: Raw unvalidated generation.
- `llm_validated`: Generation gated by abstention threshold (T=30.0) with exact citation verification.
- `llm_validated_noabstain`: Citation validation enabled without retrieval score thresholding.

### 4.3 Streamlit Web Interface
Run the interactive user interface (not verified in audit; interactive GUI):
```bash
streamlit run app/ui.py --server.address 127.0.0.1 --server.port 8501
```
*Host Binding Security*: The web interface binds strictly to `127.0.0.1`. Binding to `0.0.0.0` is refused by default to prevent exposing an unauthenticated service. Binding to all interfaces requires setting `ALLOW_INSECURE_ALL_INTERFACES=1`.

### 4.4 Single-Clause Legal Document Review
Review individual contract or tenancy clauses programmatically (function covered by `tests/test_review.py`; snippet not run as written):
```python
from src.review.extract import ExtractedClause
from src.review.clause_review import review_single_clause

clause = ExtractedClause(
    doc_id="doc_lease_001",
    page=1,
    clause_id="clause_eviction_1",
    char_start=0,
    char_end=120,
    text="The landlord may evict the tenant at any time without notice or assigning any reason."
)
findings = review_single_clause(clause, enable_llm=False)
for finding in findings:
    print(f"Label: {finding.label}, Subject: {finding.apparent_subject}")
    print(f"Explanation: {finding.preliminary_explanation}")
```

---

## 5. Evaluation & Empirical Benchmark Results

### 5.1 Verification Commands
```bash
# 1. Run complete automated unit test suite (112 tests; verified in audit: 112 passed)
pytest -q

# 2. Run frozen test split retrieval evaluation with 10,000 bootstrap resamples
# (Plain scripts/run_frozen_eval.py requires a clean committed tree; it exited 1 on the dirty tree and was not run clean in the audit. Run with --allow-dirty when tree has uncommitted changes.)
python scripts/run_frozen_eval.py

# 3. Compute retrieval benchmark table bootstrap 95% CIs and export to eval/table_cis.json (verified in audit)
python scripts/compute_table_cis.py

# 4. Verify statutory version audit coverage (verified in audit: 0.00% verified coverage)
python scripts/audit_versions.py

# 5. Run cross-language paired consistency evaluation (verified in audit: 0.0000 BN-EN overlap)
python scripts/eval_paired_languages.py

# 6. Generation benchmark smoke test (Limit 4 queries; not verified in audit; calls local LLM)
# WARNING: Full evaluation on 42 queries takes 1+ hours on CPU. Test with --limit 4 first.
python eval/run_rag_eval.py --limit 4
```

### 5.2 Retrieval Benchmark Metrics (Frozen Test Split)
Sources: `eval/frozen_retrieval_metrics.json` and `eval/table_cis.json` (generated via `scripts/compute_table_cis.py`; Corpus size N=17 active provisions, 10,000 bootstrap resamples, seed=42)

#### Table (a): Retrieval on All 30 Answerable Test Queries (n=30)
*Reflects full benchmark queries where 15 target provisions are absent from the 17-provision fixture corpus.*

| Condition | MRR@10 (95% CI) | Recall@5 (95% CI) | Recall@10 (95% CI) | nDCG@10 (95% CI) | Max Ceiling (R@10) | Latency | Peak RAM |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Ranking Baseline** | 0.1062 | 0.1373 | 0.2745 | 0.1368 | 46.7% | 0.00 ms | 0.0 MB |
| **BM25 Word Baseline** | 0.2000 [0.0667, 0.3667] | 0.2000 [0.0667, 0.3667] | 0.2000 [0.0667, 0.3667] | 0.1973 [0.0667, 0.3586] | 46.7% | 0.06 ms | 41.4 MB |
| **BM25 Char 3-Gram (Production)** | 0.2375 [0.1000, 0.4000] | 0.2333 [0.1000, 0.4000] | 0.2667 [0.1333, 0.4333] | 0.2398 [0.1000, 0.3959] | 46.7% | 0.14 ms | 41.5 MB |
| BM25 Banglish Expanded | 0.2464 [0.1083, 0.4083] | 0.2333 [0.1000, 0.4000] | 0.3167 [0.1667, 0.4833] | 0.2573 [0.1176, 0.4111] | 46.7% | 0.21 ms | 41.5 MB |

#### Table (b): Retrieval on Queries with Gold Present in Corpus (n=15)
*Evaluates retrieval efficacy strictly over queries whose target provisions exist in the 17 active provisions.*

| Condition | MRR@10 (95% CI) | Recall@5 (95% CI) | Recall@10 (95% CI) | nDCG@10 (95% CI) | Max Ceiling (R@10) | Latency | Peak RAM |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Ranking Baseline** | 0.2124 | 0.2745 | 0.5490 | 0.2736 | 93.3% | 0.00 ms | 0.0 MB |
| **BM25 Word Baseline** | 0.4000 [0.1333, 0.6667] | 0.4000 [0.1333, 0.6667] | 0.4000 [0.1333, 0.6667] | 0.3946 [0.1333, 0.6560] | 93.3% | 0.06 ms | 41.4 MB |
| **BM25 Char 3-Gram (Production)** | 0.4750 [0.2167, 0.7333] | 0.4667 [0.2000, 0.7333] | 0.5333 [0.2667, 0.8000] | 0.4795 [0.2421, 0.7251] | 93.3% | 0.14 ms | 41.5 MB |
| BM25 Banglish Expanded | 0.4929 [0.2440, 0.7429] | 0.4667 [0.2000, 0.7333] | 0.6333 [0.4000, 0.8667] | 0.5146 [0.2831, 0.7462] | 93.3% | 0.21 ms | 41.5 MB |

> [!NOTE]
> Tables show per-condition bootstrap 95% CIs that overlap the uniform random baseline; no paired BM25-vs-random hypothesis test was run. On queries with gold present in the corpus (n=15), Word BM25 (Recall@10 = 0.4000) and Char BM25 (Recall@10 = 0.5333) are at or below the uniform random ranking baseline (Recall@10 = 0.5490), because top-10 covers ~59% of a 17-provision corpus. At MRR@10 and Recall@5, point estimates exceed random, but per-condition CIs overlap random baseline performance. Paired Holm-adjusted differences between BM25 variants are not significant (see `eval/frozen_retrieval_metrics.json`).

#### Paired Bootstrap Hypothesis Testing & Holm-Bonferroni Correction
Evaluated across m=3 pairwise comparisons (`Char vs Word`, `Banglish vs Word`, `Banglish vs Char`):
- **MRR@10**: Char vs Word delta = +0.0375 (Holm adjusted p = 0.5096, adjusted CI: [0.0000, 0.1083]); Banglish vs Word delta = +0.0464 (Holm adjusted p = 0.0828, adjusted CI: [0.0000, 0.1458]). Neither excludes 0.
- **nDCG@10**: Char vs Word delta = +0.0424 (Holm adjusted p = 0.3836); Banglish vs Word delta = +0.0600 (Holm adjusted p = 0.0816). Neither excludes 0.
- **Recall@10**: Banglish vs Word delta = +0.1167 (raw p = 0.0276, Holm adjusted p = 0.0828, adjusted CI: [0.0000, 0.2667]).
- **Finding**: Under strict family-wise error rate control (Holm-Bonferroni), **no model achieves statistically significant superiority over baseline on MRR@10 or nDCG@10**.

### 5.3 Generation & Citation Verification Metrics
Recomputed directly from `eval/outputs.jsonl` and reconciled with `eval/eval_summary.json` (n=42 test queries, local Ollama `qwen2.5:3b`):

| Operational Mode | n | Emitted LLM Claims | Validator Pass (Emitted) | Fallback Rate | Parse Failure | Abstained Rate | Latency (p50) | Latency (p95) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `extractive` | 42 | N/A (extractive summary) | N/A | 0.00% (0/42) | 0.00% (0/42) | 42.86% (18/42) | 0.02 ms (warm, excluding index load) | 0.05 ms (warm, excluding index load) |
| `llm` (unvalidated) | 42 | 38 | 76.32% (29/38) | 7.14% (3/42) | 11.90% (5/42) | 2.38% (1/42) | 34,982 ms | 131,259 ms |
| `llm_validated_noabstain` | 42 | 16 | 100.0% (16/16) | 59.52% (25/42) | 11.90% (5/42) | 2.38% (1/42) | 34,982 ms | 131,259 ms |
| `llm_validated` (Production) | 42 | 12 | 100.0% (12/12) | 26.19% (11/42) | 4.76% (2/42) | 45.24% (19/42) | 21,637 ms | 78,160 ms |

- **Emitted LLM Claims**: Strictly counts claims generated by the LLM that reached the final answer (excluding extractive fallback claims). In `llm_validated`, 12 LLM claims were emitted across 42 queries, and all 12 (100.0%) passed validator filtering.
- **Shared LLM Latency**: `llm` (unvalidated) and `llm_validated_noabstain` share a single cached LLM call per query via `llm_inference_cache[qid]`, resulting in identical generation latencies (34,982 ms). Extractive latencies (0.02 ms to 0.05 ms) represent warm execution excluding index loading.
- **Query-Level Outcome Breakdown (`llm_validated`)**: Across all 42 test queries:
  - **19 queries abstained** (45.24%): 18 via post-retrieval score threshold ($S(q) < 30.0$) and 1 via model-level abstention flag.
  - **23 queries reached the LLM**:
    - **12 queries passed** citation validation and emitted verified claims.
    - **11 queries fell back** to extractive summarization (7 quote substring mismatches, 2 missing required quotes, 2 JSON parse / context truncation failures). Parse failures are query-level failures that trigger fallback, not rejected claims.
  - Total queries: $19\text{ (abstained)} + 12\text{ (passed)} + 11\text{ (fell back)} = 42\text{ queries}$ (100% reconciled).
- **Abstained Reconciliation**: In `eval/eval_summary.json` and `eval/outputs.jsonl`:
  - `extractive`: 18 of 42 queries abstained (42.86%), comprising 11 answerable queries (`BNCH_*`, false-abstain rate = 11/30 = 36.67%) and 7 unanswerable queries (`INSUF_*`).
  - `llm_validated`: 19 of 42 queries abstained (45.24%), comprising 12 answerable queries (11 score threshold + 1 model-level, false-abstain rate = 12/30 = 40.00%) and 7 unanswerable queries.

---

## 6. Known Limitations & Diagnostic Caveats

1. **Uninterpretable Raw Generative Conditions Due to High Fallback**:
   In `llm_validated`, 26.19% of queries (11 of 42) fell back to extractive summarization because candidate claims failed string containment checks. In `llm_validated_noabstain`, fallback reached 59.52% (25 of 42). Metrics for these conditions largely reflect extractive fallback rather than pure generative fluency.
2. **High False-Abstention Rate on Answerable Queries**:
   In `eval/eval_summary.json`, the false-abstain rate is 40.0% (12 of 30 answerable test queries refused) in `llm_validated` and 36.67% (11 of 30) in `extractive`. Approximately 37% to 40% of queries with answerable statutory provisions in the benchmark are rejected by the post-retrieval score threshold (T=30.0).
3. **Local CPU Latency Overhead**:
   Local Ollama `qwen2.5:3b` generation requires 21.6 s to 35.0 s median latency on CPU, with p95 reaching 131.3 s. BM25 retrieval completes in 0.06 ms to 0.21 ms (<0.001% of response time).
4. **Abstention Precision & Recall Not Computable**:
   `eval/insufficient_audit.csv` maintains 0 of 16 filled human ground-truth labels (`answerable_in_corpus`). Precision, recall, and F1 for abstention remain uncomputable.
5. **Historical Statutory Status Unverified**:
   `eval/version_audit.csv` maintains 0 of 19 provisions (17 active + 2 quarantined) verified against official commencement gazettes (0.00% coverage). The temporal retrieval filter conservatively flags 100% of temporal queries as `uncertain`.
6. **Human Advocate Review Pending**:
   All 42 rows in `eval/reviewer_audit_sheet.csv` remain blank templates. Claims regarding legal correctness or completeness by certified advocates are unverified.
7. **Contaminated Test Split Threshold Inspection**:
   Score threshold candidates (T in {5.0, 10.5, 30.0}) were evaluated after observing retrieval scores on both development and test splits. A pristine, untouched holdout is not claimed.
8. **Cross-script retrieval gap (unverified)**:
   Pure lexical retrieval between Bengali Unicode queries and English statutory text yields 0.0000 Jaccard token overlap on grounded scenarios (possible metric artifact [record_id vs (act, section)], unverified).
9. **OCR and Voice Not Implemented**:
   Scanned PDFs lacking digital text layers are quarantined; raster image OCR and voice interfaces are not implemented.

---

## 7. Reproducibility & Cryptographic Verification

- **Tested from a clean clone: NO** (as of 2026-11-04; development and verification were conducted in the primary working repository).
- **Freeze Manifest Commit Hash**: `5fee1efeef6bb93ff9c31b6aa5329ceb040c585a` (Commit at which `eval/freeze_manifest.json` was generated).
- **Freeze Manifest**: `eval/freeze_manifest.json` (Tracks SHA-256 digests for corpus, split, benchmark files, model parameters, and package versions).
- **Split Hash Verification**: Verified in audit (`[+] Split SHA-256 verified`) using:
  ```bash
  python -c "import hashlib; assert hashlib.sha256(open('eval/split.json','rb').read()).hexdigest() == open('eval/split.sha256').read().strip(); print('[+] Split SHA-256 verified.')"
  ```
- **Frozen Random Seed**: All stochastic components (bootstrap resamples, LLM sampling) use fixed seed `42` with temperature `0.0`.

---

## 8. Project Layout

```
Legal_Aid/
├── README.md                          # Project documentation and entry point
├── requirements.txt                   # Baseline Python dependency specifications
├── app/
│   └── ui.py                          # Streamlit web interface (127.0.0.1 host-confined)
├── configs/
│   └── production_retrieval.yaml      # Frozen production retrieval configuration
├── data/
│   ├── benchmarks/
│   │   ├── benchmark_dev.jsonl        # 140 multi-script development queries
│   │   └── benchmark_test.jsonl       # 60 held-out test queries (42 in frozen eval split)
│   ├── manifests/
│   │   └── processed_manifest.jsonl   # Cryptographic provenance manifest
│   └── processed/
│       └── provisions.jsonl           # 19 statutory provisions (17 active, 2 quarantined)
├── docs/                              # Research reports, error taxonomies, and methodology
├── eval/                              # Evaluation runner, frozen metrics, and reviewer sheets
├── experiments/                       # Feasibility ablation results and embeddings cache
├── scripts/                           # Independent CLI tools for auditing and benchmarking
├── src/
│   ├── pipeline.py                    # Unified entry point returning PipelineResult
│   ├── evaluation/                    # Metrics and memory logging utilities
│   ├── ingestion/                     # Section-aware HTML/text parsers and normalizers
│   ├── rag/                           # Production RAG API, validator, and Ollama caller
│   ├── retrieval/                     # In-memory subword BM25 and temporal filter
│   ├── review/                        # Multi-tenant document review and clause extraction
│   └── schema/                        # Pydantic entity models and legal registry
└── tests/                             # Pytest automated test suite (112 tests)
```

---

## 9. Legal Data Notice & Disclaimers

- **Statutory Data Notice**: The 17 statutory fixture provisions in `data/processed/provisions.jsonl` are sample text files for research and testing. They may not match official government gazette wording, are incomplete, and must not be relied on as authentic or authoritative statute text.
- **Non-Clinical Research Disclaimer**: This software is an experimental research prototype. It does NOT constitute legal advice, cannot substitute for a qualified legal practitioner, and must NOT be used for legal representation or court filings.
- **Citation & Credits**:
  - Principal Researcher: `[Placeholder / Unverified]`
  - Reviewing Counsel: `[Placeholder / Unverified Advocate]`
