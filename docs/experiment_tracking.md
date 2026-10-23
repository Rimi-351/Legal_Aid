# Legal Aid BD — Experiment Tracking & Reproducibility Guide

**Document Identifier**: `DOC-EXP-W1-002`  
**Research Project**: *Cross-Script and Multilingual Legal Retrieval for Bangladesh*  
**Milestone**: Week 1 Data & Experiment Management Foundation  
**Status**: ACTIVE & VERSION-CONTROLLED  

---

## 1. Overview & Research Integrity Architecture

To uphold empirical reproducibility, the Legal Aid BD project enforces an append-only, machine-readable experiment tracking framework. Every retrieval experiment automatically logs its exact Git revision, execution latency, process memory utilization (RSS), configuration hyperparameters, and per-query evaluation results.

Experiments are logged in two synchronised formats:
1. **Machine-Readable JSONL**: `experiments/runs/experiments.jsonl` (untruncated, append-only).
2. **Human-Readable Markdown Summary**: `experiments/runs/experiment_summary.md` (tabular comparison).
3. **Deterministic Vector Caches**: `experiments/cache/embeddings_{model_slug}_{corpus_hash}.npz` (reusable compressed NumPy arrays).

---

## 2. Experiment Schema Specification

Each record in `experiments/runs/experiments.jsonl` conforms to the following schema:

```json
{
  "experiment_id": "EXP_20261023_211016_24ffec",
  "experiment_name": "BM25_Lexical_Baseline_CharNgram",
  "timestamp_utc": "2026-10-23T15:10:16Z",
  "git_commit": "df5ab6ca00b6510f96894c48a735c024ec49174e",
  "retrieval_method": "bm25_char_ngram",
  "model_name": "none",
  "corpus_manifest": "data/manifests/processed_manifest.jsonl",
  "num_provisions_indexed": 17,
  "num_queries_evaluated": 12,
  "config_parameters": {
    "k1": 1.5,
    "b": 0.75,
    "top_k": 5,
    "use_char_ngrams": true,
    "ngram_n": 3
  },
  "overall_metrics": {
    "mrr_at_5": 0.5417,
    "recall_at_5": 0.5417,
    "precision_at_5": 0.1083,
    "ndcg_at_5": 0.5489,
    "mrr_by_language": {
      "bn": 1.0,
      "en": 0.375,
      "banglish": 0.4
    }
  },
  "execution_time_sec": 0.015,
  "process_rss_mb": 41.5,
  "python_version": "3.13.5",
  "warnings": [],
  "query_evaluations": [
    {
      "query_id": "Q_BL_01",
      "language": "banglish",
      "scenario_id": "SCENARIO_01_CONTRACT_BREACH",
      "gold_provisions": ["CA1872_S10", "CA1872_S25"],
      "retrieved_provisions": ["CA1872_S10", "BLA2006_S26", "CA1872_S25"],
      "reciprocal_rank": 1.0,
      "recall_at_5": 1.0,
      "precision_at_5": 0.4,
      "ndcg_at_5": 0.8124
    }
  ]
}
```

---

## 3. Reproduction Commands

To reproduce the Week 1 experimental results from scratch, execute the following commands from the repository root:

### Step 1: Legal Document Ingestion
Extracts permitted statutory HTML documents, applies conservative Unicode NFC normalization, detects suspect Bijoy encodings, derives deterministic IDs, and writes provisions:
```bash
python scripts/run_ingestion.py
```
*Output Artifacts*:
- `data/processed/provisions.jsonl` (19 extracted provisions: 17 active, 2 quarantined)
- `data/manifests/processed_manifest.jsonl` (Source file SHA-256 digests and provenance)

### Step 2: Lexical Baseline — Standard Word Tokens
```bash
python scripts/run_retrieval_experiment.py --method bm25
```
*Expected Metrics*: Overall MRR@5: `0.4444`, Bangla MRR: `1.0000`, English MRR: `0.3333`, Banglish MRR: `0.2000`.

### Step 3: Lexical Baseline — Character 3-Grams (Banglish-Resilient)
```bash
python scripts/run_retrieval_experiment.py --method bm25_char_ngram --ngram-n 3
```
*Expected Metrics*: Overall MRR@5: `0.5417`, Bangla MRR: `1.0000`, English MRR: `0.3750`, Banglish MRR: `0.4000`.

### Step 4: Real Dense Bi-Encoder (CPU)
```bash
python scripts/run_retrieval_experiment.py --method dense --model-name csebuetnlp/banglabert
```
*Expected Metrics*: Overall MRR@5: `0.4375`, Recall@5: `0.6250`, nDCG@5: `0.4851`. Process RSS: `~505 MB`.

### Step 5: Hybrid RRF Retrieval
```bash
python scripts/run_retrieval_experiment.py --method hybrid --model-name csebuetnlp/banglabert
```
*Expected Metrics*: Overall MRR@5: `0.4194`, Recall@5: `0.6250`, nDCG@5: `0.4780`.

### Step 6: Automated Unit Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py"
```
*Expected Output*: `Ran 25 tests in ~0.17s ... OK`.

### Step 7: Opt-In Dense Model CPU Inference Smoke Test
```bash
python scripts/smoke_test_dense_inference.py
```
*Expected Output*: Verified 768-dim embeddings with finite floats and safe memory bounds.

---

## 4. Comparing Experimental Runs

The logger continuously generates and updates `experiments/runs/experiment_summary.md`. A sample comparative view:

| Experiment ID | Timestamp (UTC) | Method | Model | Queries | Duration | Peak RSS | Reciprocal Rank | Status |
|---|---|---|---|---|---|---|---|---|
| `EXP_20261023_210948_5473ea` | 2026-10-23T15:09:48Z | `bm25_word` | `none` | 12 | 0.015 s | 38.2 MB | 0.4444 | OK |
| `EXP_20261023_211016_24ffec` | 2026-10-23T15:10:16Z | `bm25_char_ngram` | `none` | 12 | 0.015 s | 41.5 MB | 0.5417 | OK |
| `EXP_20261023_211218_bd9e0f` | 2026-10-23T15:12:18Z | `dense` | `csebuetnlp/banglabert` | 12 | 7.13 s | 505.6 MB | 0.4375 | OK |
| `EXP_20261023_211259_66393b` | 2026-10-23T15:12:59Z | `hybrid` | `csebuetnlp/banglabert` | 12 | 8.44 s | 505.6 MB | 0.4194 | OK |

---

## 5. Preventing Data Leakage: Scenario-Grouped Partitioning

To avoid synthetic inflation of retrieval performance:
1. **Strict Scenario Independence**: Queries are grouped by high-level statutory scenarios (`SCENARIO_01_CONTRACT_BREACH`, `SCENARIO_02_CONSUMER_FRAUD`, etc.).
2. **No Cross-Partition Variants**: Linguistic variants (e.g. Bangla vs Banglish vs English formulations of the same contractual dispute) **must never be split across development and test sets**. If a scenario is in Development, all its script variants reside in Development.
3. **Provisional Label Status**: All relevance annotations are marked `researcher_annotated_provisional`. No claims of lawyer-validated correctness are made until independent legal practitioner review (protocol outlined in `docs/reviewer_protocol.md`) is completed.
