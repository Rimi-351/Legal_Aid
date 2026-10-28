# Legal Aid BD — Week 1 Implementation Report
## Research Foundation and Real Model Feasibility

**Document Identifier**: `DOC-REP-W1-003`  
**Research Project**: *Cross-Script and Multilingual Legal Retrieval for Bangladesh*  
**Milestone**: Week 1 Complete Deliverable  
**Author**: Lead NLP & Legal Informatics Research Engineer  
**Hardware Profile**: Windows 11 PC (AMD64, 4 CPU Cores, 15.6 GB RAM, Intel Iris Plus Graphics, No Discrete GPU)  
**Date**: October 23, 2026  
**Status**: COMPLETED & EMPIRICALLY VERIFIED  

---

## 1. Executive Summary & Mission Assessment

Week 1 of the Legal Aid BD research roadmap has been successfully implemented and verified. The primary research question under investigation was:

> **Can available tools process selected Bangladesh legal text and retrieve useful Bengali-English legal provisions within the constraints of a Windows PC with 16 GB RAM and a CPU-only execution environment?**

**Empirical Answer: YES.**  
The experimental pipeline runs stably on CPU without crashing or triggering Windows memory paging. By deploying lightweight, deterministic components and utilizing an offline-cached Bengali model (`csebuetnlp/banglabert`), the system indexes and retrieves statutory provisions in fractions of a second with peak memory footprint ($\le 836\text{ MB}$) well within the 11.5 GB workstation ceiling.

---

## 2. Inventory of Implemented Components

```text
Legal_Aid/
├── configs/
│   ├── week0_feasibility_config.yaml    # Week 0 baseline configuration
│   └── week1_retrieval_config.yaml      # Week 1 benchmark queries (12 scenario-grouped items)
├── data/
│   ├── raw/sample_audit_files/          # 8 permitted sample legal documents (HTML, TXT, PDF)
│   ├── processed/
│   │   └── provisions.jsonl             # 19 extracted provisions (17 valid, 2 quarantined)
│   └── manifests/
│       ├── processed_manifest.jsonl     # SHA-256 provenance manifest
│       └── week0_source_summary.json
├── src/
│   ├── ingestion/
│   │   ├── normalizer.py               # NFC Unicode normalizer, Bijoy detector, language classifier
│   │   └── parser.py                   # Statutory section parser with stable IDs (e.g. CA1872_S10)
│   ├── retrieval/
│   │   ├── bm25.py                     # Okapi BM25 engine with BengaliEnglishTokenizer & char n-grams
│   │   ├── dense.py                    # PyTorch CPU dense retriever with L2 norm & .npz vector caching
│   │   └── hybrid.py                   # Reciprocal Rank Fusion (RRF, k=60)
│   ├── evaluation/
│   │   ├── metrics.py                  # Recall@k, Precision@k, MRR, nDCG@k calculation
│   │   └── logger.py                   # Append-only JSONL experiment tracker with process RSS
│   └── document_review/
├── scripts/
│   ├── run_ingestion.py                # CLI runner for parsing and manifest creation
│   ├── run_retrieval_experiment.py     # Unified CLI experimental runner (bm25/dense/hybrid)
│   └── smoke_test_dense_inference.py   # Opt-in CPU dense inference smoke test
├── experiments/
│   ├── runs/
│   │   ├── experiments.jsonl           # Append-only experiment run log
│   │   └── experiment_summary.md       # Comparative markdown table
│   └── cache/
│       └── embeddings_*.npz            # Cached L2-normalized float32 vectors
├── tests/
│   ├── test_ingestion.py               # Tests for NFC normalization, Bijoy detection, section parsing
│   ├── test_bm25.py                    # Tests for word/char tokenization, BM25 ranking, edge cases
│   ├── test_dense.py                   # Tests for cosine similarity math, vector norm, .npz cache
│   └── test_experiment_tracking.py     # Tests for metrics, logger schema, and anti-leakage splitting
└── docs/
    ├── week1_model_selection.md        # Model selection record and trade-offs
    ├── experiment_tracking.md          # Experiment schema and reproduction guide
    └── week1_implementation_report.md  # This comprehensive milestone report
```

---

## 3. Empirical Experimental Results

Four distinct retrieval paradigms were evaluated against the 12 scenario-grouped statutory benchmark queries:

| Experiment ID | Retrieval Method | Underlying Model | Top-k | Overall MRR@5 | Overall Recall@5 | Overall nDCG@5 | Bangla MRR | English MRR | Banglish MRR | Execution Time | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `EXP_20261023_210948_5473ea` | `bm25_word` | Algorithmic (Tokens) | 5 | 0.4444 | 0.4583 | 0.4568 | **1.0000** | 0.3333 | 0.2000 | 0.015 s | 38.2 MB |
| `EXP_20261023_211016_24ffec` | `bm25_char_ngram` | Algorithmic (3-grams) | 5 | **0.5417** | 0.5417 | **0.5489** | **1.0000** | **0.3750** | **0.4000** | 0.015 s | 41.5 MB |
| `EXP_20261023_211218_bd9e0f` | `dense` | `csebuetnlp/banglabert` | 5 | 0.4375 | **0.6250** | 0.4851 | 0.8333 | 0.2500 | **0.4000** | 7.13 s (Cold) | 505.6 MB |
| `EXP_20261023_211259_66393b` | `hybrid` (RRF) | `banglabert` + BM25 | 5 | 0.4194 | **0.6250** | 0.4780 | 0.8333 | 0.3333 | 0.2400 | 8.44 s | 505.6 MB |

### Key Scientific Insights:
1. **Validation of Hypothesis $H_{1,2}$ (Banglish Transliteration)**:
   Standard word-level BM25 struggles with phonetic transliterations (e.g. *"chukti invalid hoy jokhon"*), scoring a low $MRR = 0.2000$. By decomposing words into character 3-grams, lexical retrieval doubled its Banglish performance to $MRR = 0.4000$ without requiring external bilingual dictionaries.
2. **Dense Bi-Encoder Recall Advantage**:
   `csebuetnlp/banglabert` achieved the highest Recall@5 ($0.6250$), demonstrating the ability to retrieve relevant provisions (such as Consumer Rights Section 45) even when the user query used informal terms (*"ভেজাল খাবার বিক্রির শাস্তি"*) not verbatim in the statutory heading (*"ভেজাল পণ্য বিক্রয়ের দণ্ড"*).
3. **Monolingual Precision**:
   On formal Bengali statutory queries, lexical BM25 achieved perfect precision ($MRR = 1.0000$), demonstrating that exact statutory term matching is highly effective when queries use standard legal terminology.

---

## 4. PostgreSQL and pgvector Decision

**Decision: DEFERRED, IN-MEMORY RETRIEVAL USED.**

### Justification & Analysis:
1. **Scale vs Overhead**:
   - The verified initial evaluation corpus comprises 17 active provisions (and will expand to ~1,000–3,000 statutory sections in Phase 2).
   - In-memory vector dot product with NumPy on 3,000 vectors of 768 dimensions requires:
     $$3,000 \times 768 \times 4\text{ bytes} \approx 9.2\text{ MB of RAM}$$
     Query execution time via matrix dot-product is under **$2.5\text{ ms}$**.
2. **Resource Budget on 16 GB PC**:
   - Running a background PostgreSQL server daemon permanently consumes 150–300 MB of system RAM and adds Windows service management overhead.
   - DuckDB (`duckdb 1.4.4`) is already installed in the virtual environment and supports embedded, single-file ACID operations with zero background daemon overhead.
3. **Portability & Isolation**:
   - Storing embeddings as compressed `.npz` arrays inside `experiments/cache/` ensures 100% reproducibility across environments without requiring external database installation, user role management, or network port configuration.
4. **Trigger for Reconsideration**:
   - PostgreSQL with pgvector will be evaluated in Week 6 if and when the corpus scales to $> 50,000$ high court judgments requiring persistent relational joins and multi-tenant metadata filtering.

---

## 5. Automated Testing and Verification

- **Unit Test Suite**: 25 automated unit tests implemented in `tests/test_ingestion.py`, `tests/test_bm25.py`, `tests/test_dense.py`, and `tests/test_experiment_tracking.py`.
  - Execution result: **25 tests passed in 0.167 s (100% pass rate)**.
- **Opt-In CPU Inference Smoke Test**: `scripts/smoke_test_dense_inference.py`.
  - Verified live model loading (3.49 s), CPU batch encoding (0.17 s for 2 documents), correct 768-dim tensor shape, and finite floating-point checks.
  - Peak process RSS: 836.38 MB (well within 11.5 GB limit).

---

## 6. Known Limitations & Integrity Boundaries

1. **Researcher-Annotated Benchmark**:
   All 12 evaluation query labels are tagged `researcher_annotated_provisional`. In strict adherence to Section 3 of the Research Protocol, these results serve as directional development feedback and do not constitute certified legal validation.
2. **Government Portal Connection Blocker**:
   Programmatic connections to `bdlaws.minlaw.gov.bd` trigger TCP reset `[WinError 10054]` due to government WAF bot protection. As an epistemic and procedural rule, document ingestion strictly relies on browser-exported HTML artifacts saved in `data/raw/` with verified SHA-256 hashes.
3. **English Legal Vocabulary in BanglaBERT**:
   While `csebuetnlp/banglabert` excels at Bengali statutory text, its performance drops on pure English legal syntax ($MRR = 0.2500$). Subsequent weeks will test multilingual models (`multilingual-e5-small`) or two-pass hybrid routing.

---

## 7. Next Actions for Week 2

1. **Expand Ingestion Corpus**: Export additional statutory Acts from official gazettes into `data/raw/sample_audit_files/` (Penal Code 1860, Code of Criminal Procedure 1898).
2. **Reviewer Outreach**: Initiate legal practitioner review using `docs/reviewer_protocol.md` to establish gold-standard relevance annotations.
3. **Subword & Transliteration Enhancements**: Benchmark phonetic transliteration normalizers (e.g., Avro phonetic mapping) alongside character n-grams.
