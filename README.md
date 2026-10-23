# Legal Aid BD (Legal Informatics & Retrieval Research)

An empirical research project investigating **cross-script and multilingual legal retrieval for Bangladesh statutory law** under consumer-grade PC hardware constraints (Windows 11, 16 GB RAM, CPU-only execution).

---

## 1. Project Status: Week 1 Foundation Verified

- **Lexical Baseline (BM25)**: Operational with specialized Bengali-English word and character n-gram tokenization.
- **Dense Bi-Encoder Retrieval**: Genuinely executed on CPU using `csebuetnlp/banglabert` (110M params, 768-dim) with local `.npz` vector caching.
- **Banglish Resilience**: Character 3-gram BM25 doubles retrieval performance on Banglish queries ($MRR = 0.4000$ vs $0.2000$).
- **Experiment Tracking**: Append-only JSONL logger with Git commit hashes, execution time, and process memory monitoring.
- **Unit Testing**: 25 automated unit tests with 100% pass rate.
- **Database Architecture**: PostgreSQL with pgvector deferred to Week 6 in favor of lightweight in-memory and DuckDB vector caching.

---

## 2. Hardware Constraints & Environment

- **OS**: Windows 11 Pro 64-bit (AMD64)
- **RAM**: 15.6 GB Physical (~8 GB available idle)
- **CPU**: 4 physical cores / 4 logical threads
- **GPU**: Intel Iris Plus Graphics (No discrete NVIDIA GPU; CPU-only PyTorch)
- **Python**: 3.13.5 (64-bit)
- **Memory Safety Ceiling**: Total process RSS $\le 11.5\text{ GB}$

---

## 3. Directory Layout

```text
Legal_Aid/
├── configs/                  # Benchmark queries & experiment configs
│   ├── week0_feasibility_config.yaml
│   └── week1_retrieval_config.yaml
├── data/
│   ├── raw/sample_audit_files/   # Permitted statutory documents (HTML/PDF)
│   ├── processed/provisions.jsonl # Normalized statutory provisions
│   └── manifests/processed_manifest.jsonl # Source SHA-256 provenance
├── src/
│   ├── ingestion/            # Conservative Unicode NFC & section parsing
│   ├── retrieval/            # BM25, Dense Bi-Encoder, Hybrid RRF
│   └── evaluation/           # Metrics (MRR, Recall@k, nDCG@k) & JSONL logger
├── scripts/                  # CLI experimental pipeline runners
├── experiments/
│   ├── runs/experiments.jsonl # Append-only experiment run log
│   └── cache/embeddings_*.npz # Cached float32 vector matrices
├── tests/                    # Automated unit tests (25 passing)
└── docs/                     # Research protocol & implementation reports
```

---

## 4. Quickstart & Reproduction Commands

### 1. Run Legal Document Ingestion
Extracts statutory HTML files into normalized, section-level provisions with deterministic IDs:
```bash
python scripts/run_ingestion.py
```

### 2. Run Lexical Retrieval Baseline (Word Tokens)
```bash
python scripts/run_retrieval_experiment.py --method bm25
```

### 3. Run Banglish-Resilient Lexical Retrieval (Character 3-Grams)
```bash
python scripts/run_retrieval_experiment.py --method bm25_char_ngram --ngram-n 3
```

### 4. Run Real Dense Bi-Encoder Retrieval (CPU)
```bash
python scripts/run_retrieval_experiment.py --method dense --model-name csebuetnlp/banglabert
```

### 5. Run Hybrid Retrieval (Reciprocal Rank Fusion)
```bash
python scripts/run_retrieval_experiment.py --method hybrid --model-name csebuetnlp/banglabert
```

### 6. Run Automated Unit Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 7. Run Opt-In Dense Model CPU Inference Smoke Test
```bash
python scripts/smoke_test_dense_inference.py
```

---

## 5. Research Protocol & Ethical Boundaries

1. **Non-Clinical Research System**: This software is an empirical retrieval benchmark. It does **not** provide legal advice, representation, or certified statutory interpretations.
2. **Provisional Benchmarks**: All evaluation annotations are marked `researcher_annotated_provisional` until formal legal review under `docs/reviewer_protocol.md` is completed.
3. **Epistemic Honesty**: All reported latencies and RAM usage are directly measured on CPU. Synthetic estimates are explicitly documented as such.
