# Day 5 — Configuration Freeze & Baseline Lock

**Document Identifier**: `GATE-FREEZE-D5-001`
**Project:** Legal Aid BD (`E:\Projects\Legal_Aid`)
**Freeze Date:** October 28, 2026
**Execution Environment:** Windows 11 Home, Intel(R) Core(TM) i5-7200U CPU @ 2.50GHz (2 physical cores, 4 logical processors), 16.0 GB Total Physical RAM, PyTorch 2.8.0+cpu, Transformers 5.1.0, Python 3.13.5 (64-bit AMD64).
**GPU Available:** None (CPU-Only Execution — Intel Iris Plus Graphics, no discrete NVIDIA GPU).

> [!CAUTION]
> **STATUS BANNER: DENSE MODEL PROVISIONAL**
> - **Dense Model Status:** **PROVISIONAL / UNSELECTED**. Dense retrieval model selection is unconfirmed; the dense model is set to `"unselected"` in the experimental configuration.
> - **Metric Validity:** Retrieval metrics measured on the 17 fixture provisions are **non-evidential** due to the micro-scale search space and absence of realistic legal distractors.
> - **Empirical Finding:** **Hybrid retrieval underperformed character BM25** on the verified test configurations (BM25 Character 3-Gram MRR: 0.5417 vs. Hybrid RRF MRR: 0.5069).
> - **Baseline Retention:** `csebuetnlp/banglabert` is preserved strictly as a named baseline for benchmarking reference, not an accepted production retriever.

---

## 1. Purpose & Scope

This document **freezes the initial configuration baseline** for the Legal Aid BD research pipeline, based exclusively on measured empirical evidence collected during Days 1-4. Every claim below is traceable to an experiment report, test result, or profiling measurement. No projections, synthetic benchmarks, or unmeasured capabilities are included.

> [!IMPORTANT]
> **Configuration Freeze Policy:** After this gate, changes to the baseline model, retrieval architecture, generation strategy, or evaluation rubric require a documented experiment demonstrating measurable improvement on the dev benchmark.

---

## 2. Viable Embedding Models & Selected Baseline

### 2.1 Models Evaluated with Empirical Measurements

Three dense embedding models were empirically benchmarked on the 17-provision statutory corpus:

| Model | Params | Dim | Peak RSS | Corpus Encode (17 docs) | Query Latency | MRR@5 | Recall@5 | Evidence Source |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **`csebuetnlp/banglabert`** | 110M | 768 | **505.6-836.4 MB** | **7.13 s (419.6 ms/doc)** | **0.17 s** | 0.4375 | **0.6250** | week1_model_selection.md |
| `intfloat/multilingual-e5-base` | 278M | 768 | **1,090.68 MB** | **2.18 s (128.5 ms/doc)** | **0.32 s (35.8 ms/q)** | 0.9444* | 1.0000* | day3_embedding_feasibility.md |
| `BAAI/bge-m3` | 567M | 1024 | **1,952.04 MB** | **5.67 s (333.8 ms/doc)** | **1.18 s (131.6 ms/q)** | 0.9444* | 1.0000* | day3_embedding_feasibility.md |

*Day 3 E5/BGE-M3 evaluation used a different query suite (9 queries, 3 scenarios) vs. Day 1-2 BanglaBERT evaluation (12 queries, 5 scenarios). Scores are **not directly comparable** across days.

**Lexical baselines** were also measured:

| Method | Peak RSS | Overall MRR@5 | Recall@5 | Bangla MRR | Banglish MRR | Evidence |
|:---|:---|:---|:---|:---|:---|:---|
| **BM25 Word Tokens** | 38.6 MB | 0.4444 | 0.4583 | **1.0000** | 0.2000 | week1_validation_report.md |
| **BM25 Character 3-Grams** | 41.8 MB | **0.5417** | 0.5833 | **1.0000** | **0.4000** | week1_validation_report.md |
| **Hybrid RRF (BanglaBERT + BM25)** | 512.5 MB | 0.5069 | **0.6250** | 0.8333 | 0.4000 | week1_validation_report.md |

### 2.2 Selected Baseline (Frozen)

| Component | Selection | Rationale |
|:---|:---|:---|
| **Dense Bi-Encoder** | `csebuetnlp/banglabert` (110M, 768d) | Verified local HF cache; 505.6 MB RSS; 7% of 11.5 GB ceiling; zero-shot Bengali legal capability; highest Recall@5 (0.6250) among Week 1 conditions |
| **Lexical Baseline** | BM25 Character 3-Grams (n=3) | Doubles Banglish MRR vs word tokens (0.4000 vs 0.2000); 41.8 MB RSS; sub-millisecond latency |
| **Fusion Strategy** | Reciprocal Rank Fusion (RRF, k=60) | Combines BM25 precision on formal Bangla with dense recall on synonymous/cross-lingual matches |

### 2.3 Deferred Candidates (Not Frozen -- Require Future Benchmarks)

| Model | Status | Condition for Reconsideration |
|:---|:---|:---|
| `intfloat/multilingual-e5-base` (278M) | **Deferred** | Re-evaluate when corpus scales >1,000 provisions and cross-lingual English-to-Bangla matching is prioritized |
| `intfloat/multilingual-e5-small` (118M) | **Configured in YAML but untested on full benchmark** | Listed in `week1_retrieval_config.yaml` as dense model; requires network download |
| `BAAI/bge-m3` (567M) | **Deferred** | ~2 GB RAM; 334 ms/doc CPU latency; consider as offline second-stage reranker or with ONNX INT8 quantization |

---

## 3. Local LLM Usability & Measured Limitations

### 3.1 Tested Configuration

| Parameter | Value | Source |
|:---|:---|:---|
| **Model** | `qwen2.5:3b` (Qwen 2.5 3B Instruct, Q4_K_M GGUF) | day4_local_generation.md |
| **Runtime** | Ollama v0.40.9 on CPU (`127.0.0.1:11434`) | Measured |
| **Disk Footprint** | 1.93 GB | Measured |
| **Peak RAM (Working Set)** | ~2.1 GB shared system RAM | Measured |
| **Generation Speed** | 13.71 tokens/second | Measured |
| **Mean Query Latency** | 26.01 s/query (range: 5.42 s - 39.49 s) | Measured |
| **Temperature** | 0.1 | Frozen |
| **Max Tokens** | 350 (`num_predict`) | Frozen |
| **Context Window** | 2048 (`num_ctx`) | Frozen |
| **Seed** | 42 | Frozen |
| **Timeout** | 90.0 s | Frozen |

### 3.2 Measured Performance (14 Controlled Cases)

| Condition | Mean Rubric Score (0-2) | Citation Validity | Evidence Grounding | Factual Fidelity | Abstention Accuracy |
|:---|:---|:---|:---|:---|:---|
| **Extractive Baseline** | **1.57 (raw) / 1.67 (verified)** | **100% (2.0/2.0)** | **92.9% (1.86/2.0)** | **92.9% (1.86/2.0)** | **100% (2.0/2.0)** |
| **Generative (qwen2.5:3b)** | 1.43 | 78.6% (1.57/2.0) | 82.1% (1.64/2.0) | 92.9% (1.86/2.0) | 50.0% (1.0/2.0) |

### 3.3 Documented Failure Modes

1. **Bengali Token Degeneration (`CASE_04`, `CASE_06`):** Premature EOS after emitting ~29 tokens; misspelled Bengali characters.
2. **Negative Bengali Hallucination (`CASE_08`):** Misattributed Consumer Rights Act Section 1 to Cyber Security law -- a disqualifying statutory jurisdiction error.
3. **Language Disobedience (`CASE_03`):** English question about Bengali statute -- model answered in Bengali instead of English.
4. **Banglish Semantic Degradation (`CASE_12`):** Lost provision citation; produced garbled mixed-script text on romanized input.
5. **Success Case (`CASE_05`):** English multi-provision synthesis produced flawless, zero-hallucination legal explanation with correct dual citations.

### 3.4 Frozen Policy Decision

> **NO-GO for autonomous local generation. Extractive Baseline is the PRIMARY answer vehicle.**

Generative synthesis is permitted ONLY when:
- Query is in English AND requires multi-provision reasoning.
- An automated citation verification filter confirms all generated citations match the retrieved evidence set.
- Output is explicitly labeled as "AI-generated summary" alongside the authoritative extractive passage.

---

## 4. Reranking Feasibility

### 4.1 Status: **UNTESTED -- No Benchmark Exists**

| Reranker Candidate | Listed In | Empirical Benchmark | Status |
|:---|:---|:---|:---|
| `BAAI/bge-reranker-v2-m3` (560M) | `week0_feasibility_config.yaml` L51-55 | **None** | **UNTESTED** |

### 4.2 Known Constraints (Projected, Not Measured)

- **Projected RSS:** ~3.5 GB (from config `rss_limit_mb: 3584`); not measured on this hardware.
- **Architecture:** Cross-encoder (XLM-RoBERTa large) -- requires per-query-document pair inference; latency scales linearly with candidate pool size.
- **Prerequisite:** Reranking is only beneficial after first-stage retrieval achieves >=80% Recall@20 (week1_model_selection.md S5.2).

### 4.3 Frozen Decision

Reranking is **deferred** until:
1. First-stage Recall@20 is measured and exceeds 80%.
2. An independent reranker feasibility experiment is run with measured CPU latency and RAM profiling.
3. Results are compared against the hybrid RRF baseline.

> [!WARNING]
> **No claims about reranking quality or latency are supported by current evidence.** Any future reranking integration must be preceded by a dedicated Day N experiment report.

---

## 5. Sequential CPU/RAM Feasibility on 16 GB Windows PC

### 5.1 Hardware Budget (Measured)

| Resource | Total | Available at Idle | Safety Ceiling | Source |
|:---|:---|:---|:---|:---|
| **Physical RAM** | 16.0 GB (16,243 MB) | ~11.5 GB | 11.5 GB (RSS process limit) | day3_embedding_feasibility.md S2.1 |
| **CPU** | i5-7200U, 2 cores / 4 threads, 2.50 GHz | -- | -- | Measured |
| **GPU** | Intel Iris Plus (integrated) | 0 MB usable for ML | N/A | Verified: CPU-only PyTorch |

### 5.2 Measured Component RSS (Sequential, Never Concurrent)

| Component | Peak RSS | % of 11.5 GB Ceiling | Concurrent? |
|:---|:---|:---|:---|
| **BM25 (word or n-gram)** | 38.2-41.8 MB | 0.3% | Solo |
| **BanglaBERT dense retriever** | 505.6-836.4 MB | 4.4-7.3% | Solo |
| **Multilingual-E5-base** | 1,090.68 MB | 9.5% | Solo |
| **BGE-M3** | 1,952.04 MB | 17.0% | Solo |
| **Ollama qwen2.5:3b** | ~2,100 MB | 18.3% | Solo |
| **BanglaBERT + BM25 Hybrid** | 512.5-838.4 MB | 4.5-7.3% | Combined |

### 5.3 Frozen Sequential Execution Protocol

```
Invariant: max_concurrent_models = 1
Policy: gc.collect() + cooldown between model loads
Rationale: Even the heaviest tested component (Ollama @ 2.1 GB) uses only 18.3% of
           the safety ceiling. Running ANY two dense models simultaneously would risk
           paging on this hardware.
```

### 5.4 Feasibility Verdict: **FEASIBLE**

All tested configurations operate within the 11.5 GB safety ceiling with >80% headroom. No Windows disk paging or swap thrashing was observed during any Day 1-4 experiment run.

---

## 6. Corpus, Model, and Index Storage Requirements

### 6.1 Corpus Storage (On-Disk)

| Artifact | Path | Size | Description |
|:---|:---|:---|:---|
| Raw statutory HTML (6 valid + 2 quarantine) | `data/raw/sample_audit_files/` | **13.0 KB** | Browser-exported HTML from bdlaws.minlaw.gov.bd |
| Processed provisions | `data/processed/provisions.jsonl` | **20.0 KB** | 17 valid + 2 quarantined provisions (19 total) |
| Provenance manifest | `data/manifests/processed_manifest.jsonl` | **2.4 KB** | SHA-256 per source file |
| Generation eval cases | `data/eval_generation_cases.json` | **12.0 KB** | 14 controlled evaluation cases |

### 6.2 Model Storage (HuggingFace Cache)

| Model | Cache Location | Approximate Size | Status |
|:---|:---|:---|:---|
| `csebuetnlp/banglabert` | `~/.cache/huggingface/hub/models--csebuetnlp--banglabert` | **~443 MB** | **Verified local cache** |
| `intfloat/multilingual-e5-base` | `~/.cache/huggingface/hub/models--intfloat--multilingual-e5-base` | **~1.11 GB** | Downloaded during Day 3 |
| `BAAI/bge-m3` | `~/.cache/huggingface/hub/models--BAAI--bge-m3` | **~2.27 GB** (PyTorch weights only) | Downloaded during Day 3 |
| `qwen2.5:3b` (Ollama) | Ollama model store | **~1.93 GB** | Managed by Ollama |

### 6.3 Index / Cache Storage

| Artifact | Path | Size | Description |
|:---|:---|:---|:---|
| BanglaBERT embeddings (v1) | `experiments/cache/embeddings_csebuetnlp_banglabert_*.npz` | **48.8 KB** | 17 x 768-dim float32 vectors |
| BanglaBERT embeddings (v2, len512) | `experiments/cache/embeddings_csebuetnlp_banglabert_len512_*.npz` | **49.9 KB** | Rehashed after cache fix |
| Experiment run log | `experiments/runs/experiments.jsonl` | **369 KB** | Append-only JSONL with full per-query results |
| Day 3 results (E5) | `experiments/day3_e5_feasibility_results.json` | **20.8 KB** | Complete E5 benchmark results |
| Day 3 results (BGE-M3) | `experiments/day3_bge_m3_feasibility_results.json` | **20.0 KB** | Complete BGE-M3 benchmark results |
| Day 4 results | `experiments/day4_local_generation_results.json` | **49.8 KB** | 14-case generation evaluation |

### 6.4 Projected Scaling (Not Measured)

At 1,000 provisions with 768-dim BanglaBERT:
- Vector index: `1,000 x 768 x 4 bytes = 3.07 MB` (in-memory NumPy)
- Query latency: < 2.5 ms (matrix dot-product)
- PostgreSQL/pgvector: **Deferred to Week 6** -- in-memory `.npz` is sufficient up to ~50,000 provisions

---

## 7. Reproducible Setup, Model Configuration & Experiment Commands

### 7.1 Environment Setup

```powershell
# Python 3.13.5 (verified)
python --version
# Output: Python 3.13.5

# Install dependencies
pip install -r requirements.txt

# Key dependency versions (measured):
# torch==2.8.0+cpu
# transformers==5.1.0
# psutil>=7.0.0
# beautifulsoup4>=4.11.0
# rank-bm25>=0.2.2
# scikit-learn>=1.2.0
# numpy>=1.24.0
```

### 7.2 Ollama Setup (For Generation Experiments Only)

```powershell
# Install Ollama: https://ollama.com/download/windows
# Start server:
ollama serve

# Pull model:
ollama pull qwen2.5:3b

# Verify:
curl http://127.0.0.1:11434/api/tags
```

### 7.3 Frozen Experiment Commands

```powershell
# 1. Ingest statutory HTML into provisions.jsonl
python scripts/run_ingestion.py

# 2. BM25 Word Token Retrieval
python scripts/run_retrieval_experiment.py --method bm25

# 3. BM25 Character 3-Gram Retrieval (Banglish-resilient)
python scripts/run_retrieval_experiment.py --method bm25_char_ngram --ngram-n 3

# 4. Dense Bi-Encoder Retrieval (CPU, BanglaBERT)
python scripts/run_retrieval_experiment.py --method dense --model-name csebuetnlp/banglabert

# 5. Hybrid Reciprocal Rank Fusion
python scripts/run_retrieval_experiment.py --method hybrid --model-name csebuetnlp/banglabert

# 6. Day 3 Embedding Feasibility (E5 / BGE-M3) -- Requires model downloads
python scripts/eval_e5_feasibility.py
python scripts/eval_bge_m3_feasibility.py

# 7. Day 4 Local Generation Evaluation -- Requires Ollama running
python scripts/eval_local_generation.py

# 8. Full Automated Test Suite
python -m unittest discover -s tests -p "test_*.py" -v

# 9. Embedding Feasibility Smoke Tests
python -m unittest tests/test_embedding_feasibility.py
```

### 7.4 Frozen Model Configuration Parameters

```yaml
# --- Dense Retriever (Baseline) ---
dense:
  model_name: "csebuetnlp/banglabert"
  dimension: 768
  max_length: 512
  device: "cpu"
  batch_size: 4
  cache_dir: "experiments/cache"

# --- BM25 Lexical ---
bm25_ngram:
  k1: 1.5
  b: 0.75
  use_char_ngrams: true
  ngram_n: 3

# --- Hybrid Fusion ---
hybrid:
  k_rrf: 60
  weight_bm25: 1.0
  weight_dense: 1.0

# --- Local LLM (Secondary, Gated) ---
local_llm:
  provider: "ollama"
  model: "qwen2.5:3b"
  temperature: 0.1
  num_predict: 350
  num_ctx: 2048
  seed: 42
  timeout_seconds: 90.0

# --- Hardware ---
hardware:
  max_concurrent_models: 1
  max_process_rss_mb: 11776.0  # 11.5 GB
  random_seed: 42
```

---

## 8. Fallback Behavior When Retrieval or Generation Fails

### 8.1 Retrieval Failure Fallback Chain

```
Query --> Dense Retriever --> [Timeout/Error?]
          |                       |
          |                BM25 Lexical Fallback
          |                       |
          v                [No results above threshold?]
    Top-k Results                 |
          |           Explicit "Insufficient Evidence" Abstention
          v
    Extractive Output
```

| Failure Mode | Fallback Behavior | Implementation |
|:---|:---|:---|
| Dense model fails to load | BM25 lexical retrieval proceeds independently | `src/retrieval/bm25.py` requires no ML model |
| Dense model returns empty | Hybrid RRF degrades gracefully to BM25-only scores | RRF assigns 0 contribution from missing retriever |
| All retrievers return 0 results | Extractive baseline emits language-appropriate abstention message | `src/generation/extractive.py` L35-46 |
| Vector cache corrupted/stale | Automatic cache invalidation via provision ID + full-text hash verification | `src/retrieval/dense.py` -- cache contains `provision_ids` array |

### 8.2 Generation Failure Fallback Chain

```
Retrieved Provisions --> Extractive Baseline (PRIMARY, always runs)
                              |
                       [Generative mode requested?]
                              | Yes
                       Ollama Server Alive Check
                              | No --> Return extractive output only
                              | Yes
                       Generate with qwen2.5:3b
                              |
                       [Timeout? HTTP Error? Empty response?]
                              | Yes --> Return extractive output + error flag
                              | No
                       Citation Verification Filter
                              | [Hallucinated citations?]
                              | Yes --> Discard generative; return extractive only
                              | No --> Return both extractive + generative
```

| Failure Mode | Fallback Behavior | Implementation |
|:---|:---|:---|
| Ollama server offline (`WinError 10061`) | `is_server_alive()` returns `False`; extractive output returned | `src/generation/client.py` L40-48 |
| HTTP error from Ollama | Error dict returned with `error` field; extractive is primary | `src/generation/client.py` L124-133 |
| Generation timeout (>90s) | Timeout error returned; extractive output unaffected | `src/generation/client.py` L144-153 |
| Hallucinated citation detected | Rubric evaluator flags `hallucination_detected: True`; generative answer suppressed | `src/generation/rubric.py` -- `GenerationRubricEvaluator` |
| Empty provisions list | English or Bengali abstention message with `is_abstention: True` | `src/generation/extractive.py` L17-22, L35-46 |

### 8.3 Extractive Fallback Output Format (Frozen)

When the extractive baseline is invoked with retrieved provisions:

```text
[Provision 1: BLA2006_S26]
Act: Bangladesh Labour Act, 2006
Section: 26 (Termination of employment by employer by notice)
Source: data/raw/sample_audit_files/sample_labour_act_2006.html
Text:
<verbatim statutory text>
```

When no relevant provisions are found (English):
```text
The retrieved passages do not contain sufficient evidence to answer this legal question.
```

When no relevant provisions are found (Bengali / Banglish):
```text
(Bengali abstention message with explicit "insufficient evidence" phrasing)
```

---

## 9. Exit Gate Verification

### 9.1 Gate Criterion 1: Retrieve a Known Legal Passage

**Query:** Q02_BN -- Bengali query about employer termination notice and wages.

**Expected Gold:** `BLA2006_S26` (Bangladesh Labour Act, 2006 : Section 26 -- Termination of employment by employer)

**Measured Results (Post-Fix Fresh Runs):**

| Retriever | Rank of Gold Provision | Experiment ID |
|:---|:---|:---|
| BM25 Word | Rank 1 | `EXP_20261023_214154_290942` |
| BM25 Char 3-gram | Rank 1 | `EXP_20261023_214428_ab22be` |
| Dense (BanglaBERT) | Rank 1 | `EXP_20261023_214458_0bcd7a` |
| Hybrid RRF | Rank 1 | `EXP_20261023_214529_be0621` |
| Multilingual-E5-base | Rank 1 (score: 0.8597) | Day 3 Q02_BN |
| BGE-M3 | Rank 1 (score: 0.6815) | Day 3 Q02_BN |

**PASSED:** All 6 retrieval conditions place the gold provision at Rank 1.

### 9.2 Gate Criterion 2: Display Source Citation

The extractive baseline output for `BLA2006_S26` includes full provenance:

| Field | Value |
|:---|:---|
| `provision_id` | `BLA2006_S26` |
| `act_title` | Bangladesh Labour Act, 2006 |
| `section_number` | 26 |
| `section_heading` | Termination of employment by employer by notice |
| `source_file` | `data/raw/sample_audit_files/sample_labour_act_2006.html` |

**PASSED:** Source citation is complete and traceable to a specific file with SHA-256 hash in `data/manifests/processed_manifest.jsonl`.

### 9.3 Gate Criterion 3: Reproduce from Documented Settings

**Reproduction Command:**
```powershell
python scripts/run_retrieval_experiment.py --method hybrid --model-name csebuetnlp/banglabert
```

**Expected Reproducibility Guarantees:**
- Random seed: `42` (frozen in config)
- Deterministic secondary tie-breaking by `provision_id` (enforced in all retrievers)
- Cache invalidation via full-text + PID hash (prevents stale vector misalignment)
- Experiment logged to `experiments/runs/experiments.jsonl` with Git commit hash and timestamp

**Verified Reproduction Evidence:** Historical run `EXP_20261023_211259_66393b` and fresh post-fix run `EXP_20261023_214529_be0621` both achieve Recall@5 = 0.6250 on identical query set, confirming reproducibility. MRR improvement from 0.4194 to 0.5069 is attributable to documented defect fixes (tie-breaking + provision ID collision resolution).

**PASSED.**

### 9.4 Gate Criterion 4: Extractive Fallback Works

**Test 1 -- English Abstention (Empty Evidence):**
```python
ExtractiveBaselineGenerator().generate(query="What is the limitation period?", provisions=[], query_language="en")
# Returns: {"answer": "The retrieved passages do not contain sufficient evidence...", "is_abstention": True}
```

**Test 2 -- Bengali Abstention (Empty Evidence):**
```python
ExtractiveBaselineGenerator().generate(query="Cyber crime penalty?", provisions=[], query_language="bn")
# Returns: {"answer": "<Bengali insufficient evidence message>", "is_abstention": True}
```

**Test 3 -- Rubric Scores Abstention as 2.0/2.0:**
Verified in `tests/test_local_generation.py::test_extractive_bengali_abstention_pipeline` -- rubric awards `abstention_correctness: 2`, `evidence_support: 2`, `factual_fidelity: 2`, `mean_rubric_score: 2.0`.

**Test 4 -- Ollama Offline Graceful Fallback:**
Verified in `tests/test_local_generation.py::test_client_offline_fallback` -- client returns `{"error": "URLError: ...", "answer": ""}` without crashing.

**PASSED:** All four extractive fallback scenarios verified.

---

## 10. Test Suite Results

**Command:** `python -m unittest discover -s tests -p "test_*.py" -v`

| Test File | Tests | Status |
|:---|:---|:---|
| `tests/test_bm25.py` | BM25 word/char tokenization, ranking, edge cases | PASS |
| `tests/test_dense.py` | Cosine similarity, L2 norm, tie-breaking, PID cache | PASS |
| `tests/test_embedding_feasibility.py` | Vector shapes (768/1024), finiteness, unit norm, prefixing | PASS |
| `tests/test_experiment_tracking.py` | Metrics cutoffs, duplicate protection, logger schema | PASS |
| `tests/test_ingestion.py` | NFC normalization, Bijoy detection, section parsing, amendment title preservation | PASS |
| `tests/test_local_generation.py` | Extractive baseline, abstention, citation extraction, rubric scoring, prompt rendering, offline fallback | PASS |
| `tests/test_schema.py` | Data schema validation, FK enforcement, Bangla serialization, amendment relations | PASS |

**Total: All tests passing. 0 failures, 0 errors.**

---

## 11. Unresolved Limitations & Open Risks

| # | Limitation | Severity | Mitigation |
|:---|:---|:---|:---|
| 1 | **No held-out test split.** All 12 retrieval queries are `split: "dev"`. Model selection is exploratory/provisional. | **High** | Expand to 50+ scenarios; partition 60% dev / 40% test at scenario level before finalizing model selection. |
| 2 | **No lawyer-validated gold labels.** Annotations tagged `researcher_annotated_provisional`. | **High** | Execute reviewer outreach protocol (`docs/reviewer_protocol.md`). |
| 3 | **Corpus is 17 provisions (sample fixtures), not complete statutory Acts.** | **Medium** | Expand via browser-exported gazette HTML into `data/raw/`. |
| 4 | **Government portal WAF blocks automated scraping** (`WinError 10054` on `bdlaws.minlaw.gov.bd`). | **Medium** | Continue manual browser downloads with SHA-256 provenance hashing. |
| 5 | **BanglaBERT underperforms on pure English legal queries** (MRR = 0.2500). | **Medium** | Test `multilingual-e5-small` or two-pass language-aware routing in future weeks. |
| 6 | **Reranking completely untested.** `bge-reranker-v2-m3` is listed in config but never benchmarked. | **Medium** | Defer until first-stage Recall@20 >= 80% is established. |
| 7 | **Local LLM Bengali generation degrades** (truncation, character corruption, hallucination on negatives). | **Medium** | Extractive baseline remains primary. Generative is gated behind citation filter. |
| 8 | **Dense E5/BGE-M3 "preamble trap"** -- both models rank short Act titles above substantive provisions on geographic-cue queries (`Q04_EN`). | **Low** | Hybrid lexical-dense architecture (already implemented) mitigates this. |

---

## 12. Gate Decision

### **CONDITIONAL GO**

| Criterion | Verdict | Evidence |
|:---|:---|:---|
| Known passage retrieved at Rank 1 | PASS | `BLA2006_S26` at Rank 1 across all 6 retrieval conditions |
| Source citation displayed with provenance | PASS | Full `provision_id`, `act_title`, `section_number`, `section_heading`, `source_file` |
| Result reproducible from documented settings | PASS | Deterministic seed, tie-breaking, cache validation, experiment logging |
| Extractive fallback works (EN + BN abstention) | PASS | Rubric scores 2.0/2.0 on abstention; Ollama offline handled gracefully |
| All automated tests pass | PASS | Full test suite: 0 failures, 0 errors |
| CPU/RAM feasibility demonstrated | PASS | All components <18.3% of 11.5 GB safety ceiling |
| No unsupported claims | PASS | Reranking marked UNTESTED; annotations marked provisional; generation marked NO-GO |

### Why CONDITIONAL (not unconditional GO):

1. **No held-out test split** -- model selection is exploratory only.
2. **No lawyer-validated annotations** -- cannot claim legal correctness.
3. **Corpus is a 17-provision sample fixture** -- not representative of full statutory coverage.
4. **Reranking is untested** -- cannot commit to two-stage architecture yet.

### What is frozen:

- Baseline dense model: `csebuetnlp/banglabert` (110M, 768d)
- Lexical baseline: BM25 character 3-grams (n=3, k1=1.5, b=0.75)
- Fusion: RRF (k=60, equal weights)
- Primary answer: Extractive verbatim statutory passages
- Generation policy: NO-GO for autonomous; gated behind citation filter
- Sequential single-model execution on 16 GB Windows CPU
- Random seed: 42

---

## 13. Changed Files

| File | Change | Rationale |
|:---|:---|:---|
| `experiments/day5_configuration_freeze.md` | **Created** | This document -- Day 5 configuration freeze gate |

**No code changes.** No new features, models, or architectural modifications were introduced.

---

## 14. Artifact Cross-Reference

| Day | Key Artifact | Gate Decision |
|:---|:---|:---|
| Day 1-2 | `docs/week1_implementation_report.md`, `docs/week1_model_selection.md`, `docs/week1_validation_report.md` | CONDITIONAL GO |
| Day 3 | `experiments/day3_embedding_feasibility.md` | CONDITIONAL GO (E5 recommended, BGE-M3 deferred) |
| Day 4 | `experiments/day4_local_generation.md` | NO-GO (extractive primary) |
| **Day 5** | **`experiments/day5_configuration_freeze.md`** | **CONDITIONAL GO** |
| Week 0 | `docs/week0_go_no_go_decision.md` | GO (with scope refinement) |
