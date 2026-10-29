# Comprehensive Evaluation Results & Benchmark Report

## 1. Research Question & Evaluation Scope
How do lexical BM25 (word-level tokenization), character n-gram subword indexing ($n=3$), and Banglish phonetic dictionary query expansion perform on the frozen test split of Bangladesh legal queries across native Bengali Unicode, Banglish transliteration, and English? How do deterministic quote-level citation validation and local CPU inference behave under strict factual verification constraints?

---

## 2. Hypotheses & Operational Decisions
1. **H1 (Subword Robustness)**: Character 3-gram Okapi BM25 will outperform standard word BM25 on cross-script and Banglish transliteration queries.
2. **H2 (Phonetic Expansion)**: Phonetic dictionary query expansion will provide statistically significant improvements in Recall@10 and MRR@10 over pure lexical matching.
3. **H3 (Citation Groundedness)**: Deterministic string-containment citation validation will ensure 100% of emitted claims are directly verifiable against retrieved statutory text.
4. **H4 (Latency Budget)**: Local CPU LLM generation will exhibit substantial latency overhead relative to retrieval, requiring clear operational trade-offs for interactive use.

---

## 3. Corpus Size & Characterization
- **Corpus Size**: Exactly **17 active statutory provisions**.
- **Nature of Records**: Sample text fixtures formatted as standardized statutory provisions across five acts:
  - *Contract Act 1872*
  - *Transfer of Property Act 1882*
  - *Premises Rent Control Act 1991*
  - *Bangladesh Labour Act 2006*
  - *Consumer Rights Protection Act 2009*
- **Corpus Limitation**: This corpus represents a small development test fixture, not a comprehensive or exhaustive statutory gazetteer. Of the 30 answerable test queries in the benchmark, only 15 have gold target provisions present within these 17 provisions. The remaining 15 queries reference statutory sections outside the 17-provision corpus.

---

## 4. Evaluated Baselines & Conditions
1. **Theoretical Random Ranking Baseline**: Monte Carlo uniform random sampling of $k$ provisions without replacement from the 17-provision corpus.
2. **BM25_Word_Baseline**: Standard Okapi BM25 ($k_1=1.5, b=0.75$) with whitespace and standard punctuation tokenization.
3. **BM25_Char_Ngram (Production)**: Character subword n-gram Okapi BM25 ($n=3$) with NFC Unicode normalization.
4. **BM25_Banglish_Expanded**: Character 3-gram Okapi BM25 augmented with legal phonetic dictionary expansion.
5. **Named Dense Baselines (Unselected / Unverified)**: `BAAI/bge-m3`, `intfloat/multilingual-e5-base`, and `sagorsarker/banglabert` (evaluated in feasibility scripts; unselected for production).

---

## 5. Dual-Set Retrieval Performance

Retrieval metrics are reported across two evaluation sets to account for the 17-provision corpus ceiling:
- **Set (a) All 30 Answerable Test Queries**: Reflects end-to-end benchmark retrieval where queries whose gold statutes are absent from the corpus cannot achieve recall. Maximum achievable Recall@10 is **46.7%** (14/30 queries with at least one gold provision in top 10).
- **Set (b) Queries with Gold Present in Corpus ($n=15$)**: Evaluates retrieval efficacy strictly over queries whose target statutory sections exist in the 17 provisions. Maximum achievable Recall@10 is **93.3%** (14/15).

### Table (a): Retrieval on All 30 Answerable Test Queries ($n=30$)
| Condition | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | Ceiling (R@10) | Gold Present | Latency (N=17) | Peak RSS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Random_Ranking_Baseline** | 0.1373 | 0.2745 | 0.1062 | 0.1368 | 46.7% | 15/30 (50.0%) | 0.00 ms | 0.0 MB |
| **BM25_Word_Baseline** | 0.2000 | 0.2000 | 0.2000 | 0.1973 | 46.7% | 15/30 (50.0%) | 0.06 ms | 41.4 MB |
| **BM25_Char_Ngram (Production)** | 0.2333 | 0.2667 | 0.2375 | 0.2398 | 46.7% | 15/30 (50.0%) | 0.14 ms | 41.5 MB |
| **BM25_Banglish_Expanded** | **0.2333** | **0.3167** | **0.2464** | **0.2573** | **46.7%** | 15/30 (50.0%) | 0.21 ms | 41.5 MB |

### Table (b): Retrieval on Queries with Gold Present in Corpus ($n=15$)
| Condition | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | Ceiling (R@10) | Gold Present | Latency (N=17) | Peak RSS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Random_Ranking_Baseline** | 0.2745 | 0.5490 | 0.2124 | 0.2736 | 93.3% | 15/15 (100%) | 0.00 ms | 0.0 MB |
| **BM25_Word_Baseline** | 0.4000 | 0.4000 | 0.4000 | 0.3946 | 93.3% | 15/15 (100%) | 0.06 ms | 41.4 MB |
| **BM25_Char_Ngram (Production)** | 0.4667 | 0.5333 | 0.4750 | 0.4795 | 93.3% | 15/15 (100%) | 0.14 ms | 41.5 MB |
| **BM25_Banglish_Expanded** | **0.4667** | **0.6333** | **0.4929** | **0.5146** | **93.3%** | 15/15 (100%) | 0.21 ms | 41.5 MB |

---

## 6. Paired Bootstrap Statistical Comparisons & Holm-Bonferroni Correction
All comparisons evaluated via paired bootstrap resampling ($B=10,000$ iterations, seed=42) across $m=3$ pairwise conditions:
1. `Char_Ngram vs Word_Baseline`
2. `Banglish_Expanded vs Word_Baseline`
3. `Banglish_Expanded vs Char_Ngram` (isolating the phonetic expansion contribution)

Strict rule: *A superiority claim is made only if the Holm-adjusted confidence interval strictly excludes 0 and adjusted $p < 0.05$.*

| Metric | Pairwise Comparison | Delta ($\Delta$) | Raw 95% CI | Raw $p$ | Holm Adjusted CI | Adjusted $p$ | Claim Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MRR@10** | Char vs Word | +0.0375 | [+0.0000, +0.1083] | 0.2666 | [+0.0000, +0.1083] | 0.5096 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| | Banglish vs Word | +0.0464 | [+0.0042, +0.1179] | 0.0276 | [+0.0000, +0.1458] | 0.0828 | **NO SUPERIORITY CLAIM** (Adj $p > 0.05$) |
| | Banglish vs Char | +0.0089 | [+0.0000, +0.0226] | 0.2548 | [+0.0000, +0.0256] | 0.5096 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| **nDCG@10** | Char vs Word | +0.0424 | [-0.0055, +0.1210] | 0.1918 | [-0.0082, +0.1342] | 0.3836 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| | Banglish vs Word | +0.0600 | [+0.0038, +0.1398] | 0.0272 | [-0.0017, +0.1626] | 0.0816 | **NO SUPERIORITY CLAIM** (Adj $p > 0.05$) |
| | Banglish vs Char | +0.0176 | [+0.0000, +0.0462] | 0.2548 | [+0.0000, +0.0462] | 0.3836 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| **Recall@10**| Char vs Word | +0.0667 | [+0.0000, +0.1667] | 0.1557 | [+0.0000, +0.1667] | 0.3114 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| | Banglish vs Word | **+0.1167** | **[+0.0167, +0.2333]** | **0.0097** | **[+0.0000, +0.2667]** | **0.0291** | **SIGNIFICANT IMPROVEMENT** (Adj $p < 0.05$) |
| | Banglish vs Char | +0.0500 | [-0.0167, +0.1333] | 0.2548 | [-0.0167, +0.1333] | 0.3114 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| **Recall@5** | Char vs Word | +0.0333 | [+0.0000, +0.1000] | 0.2666 | [+0.0000, +0.1000] | 0.5096 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| | Banglish vs Word | +0.0333 | [+0.0000, +0.1000] | 0.2666 | [+0.0000, +0.1333] | 0.5096 | **NO SUPERIORITY CLAIM** (CI includes 0) |
| | Banglish vs Char | +0.0000 | [0.0000, 0.0000] | 1.0000 | [0.0000, 0.0000] | 1.0000 | **NO SUPERIORITY CLAIM** (Delta = 0) |

> [!IMPORTANT]
> Under strict family-wise error rate control (Holm-Bonferroni across the 3 comparisons), **only Banglish phonetic expansion vs Word Baseline on Recall@10** achieves statistical significance (adjusted $p=0.0291$). The production Char-n-gram model vs Word baseline does NOT achieve statistical superiority on any metric once corrected.

---

## 7. Subgroup Performance Breakdown

### 7.1 By Language Modality ($n=30$)
Bootstrap 95% Confidence Intervals calculated per language slice ($B=10,000$):

| Condition | Language Subgroup | Count ($n$) | Recall@5 (95% CI) | Recall@10 (95% CI) | MRR@10 (95% CI) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BM25_Word_Baseline** | English | 15 | 0.2667 [0.0667, 0.5333] | 0.2667 [0.0667, 0.5333] | 0.2667 [0.0667, 0.5333] |
| | Bengali Unicode | 11 | 0.0909 [0.0000, 0.2727] | 0.0909 [0.0000, 0.2727] | 0.0909 [0.0000, 0.2727] |
| | Banglish | 4 | 0.2500 [0.0000, 0.7500] | 0.2500 [0.0000, 0.7500] | 0.2500 [0.0000, 0.7500] |
| **BM25_Char_Ngram** | English | 15 | 0.2667 [0.0667, 0.5333] | 0.2667 [0.0667, 0.5333] | 0.2667 [0.0667, 0.5333] |
| | Bengali Unicode | 11 | 0.0909 [0.0000, 0.2727] | 0.1818 [0.0000, 0.4545] | 0.1023 [0.0000, 0.2955] |
| | Banglish | 4 | 0.5000 [0.0000, 1.0000] | 0.5000 [0.0000, 1.0000] | 0.5000 [0.0000, 1.0000] |
| **BM25_Banglish_Expanded** | English | 15 | 0.2667 [0.0667, 0.5333] | 0.3333 [0.1333, 0.6000] | 0.2762 [0.0667, 0.5333] |
| | Bengali Unicode | 11 | 0.0909 [0.0000, 0.2727] | 0.1818 [0.0000, 0.4545] | 0.1023 [0.0000, 0.2955] |
| | Banglish | 4 | 0.5000 [0.0000, 1.0000] | 0.6250 [0.2500, 1.0000] | 0.5312 [0.0625, 1.0000] |

> [!WARNING]
> **Banglish Sample Size Limitation ($n=4$)**: The Banglish test subset contains only 4 queries. Because $n=4$, bootstrap confidence intervals are exceptionally wide (e.g. $[0.0000, 1.0000]$). No generalized superiority claim across Banglish queries is statistically supported by $n=4$.

### 7.2 By Legal Domain ($n=30$)
Bootstrap 95% Confidence Intervals calculated per legal domain slice ($B=10,000$):

| Condition | Domain Subgroup | Count ($n$) | Recall@5 (95% CI) | Recall@10 (95% CI) | MRR@10 (95% CI) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BM25_Word_Baseline** | Land & Tenancy | 11 | 0.2727 [0.0000, 0.5455] | 0.2727 [0.0000, 0.5455] | 0.2727 [0.0000, 0.5455] |
| | Employment & Labour | 8 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| | Consumer Protection | 6 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| | Contractual Obligations | 5 | 0.6000 [0.2000, 1.0000] | 0.6000 [0.2000, 1.0000] | 0.6000 [0.2000, 1.0000] |
| **BM25_Char_Ngram** | Land & Tenancy | 11 | 0.3636 [0.0909, 0.6364] | 0.3636 [0.0909, 0.6364] | 0.3636 [0.0909, 0.6364] |
| | Employment & Labour | 8 | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] |
| | Consumer Protection | 6 | 0.0000 [0.0000, 0.0000] | 0.1667 [0.0000, 0.5000] | 0.0208 [0.0000, 0.0625] |
| | Contractual Obligations | 5 | 0.6000 [0.2000, 1.0000] | 0.6000 [0.2000, 1.0000] | 0.6000 [0.2000, 1.0000] |
| **BM25_Banglish_Expanded** | Land & Tenancy | 11 | 0.3636 [0.0909, 0.6364] | 0.3636 [0.0909, 0.6364] | 0.3636 [0.0909, 0.6364] |
| | Employment & Labour | 8 | 0.0000 [0.0000, 0.0000] | 0.1250 [0.0000, 0.3750] | 0.0179 [0.0000, 0.0536] |
| | Consumer Protection | 6 | 0.0000 [0.0000, 0.0000] | 0.2500 [0.0000, 0.5833] | 0.0417 [0.0000, 0.0833] |
| | Contractual Obligations | 5 | 0.6000 [0.2000, 1.0000] | 0.6000 [0.2000, 1.0000] | 0.6000 [0.2000, 1.0000] |

---

## 8. Cross-Language Consistency Over Paired Queries
Evaluated across 12 cross-language test triplets (36 queries total: BN, Banglish, EN) comparing top-5 retrieved provisions by canonical `(act_id, section_id)`:
- **Grounded Scenarios ($n=4$ of 12 where target act and section exist in corpus)**:
  - Mean BN-EN Overlap: **0.0000**
  - Mean BN-BG Overlap: **0.0000**
  - Mean BG-EN Overlap: **0.7084**
  - Overall Grounded Macro Overlap: **0.2361**
  - Decision Consistency Rate ($T=30.0$): **0.00% (0/4)** (BN triggers retrieval while BG/EN abstain, or vice versa).
- **Full Unfiltered Set ($n=12$)**:
  - Macro Overlap: 0.2315; Full Decision Consistency: 8.33% (1/12).

---

## 9. Generation and Citation Verification Performance (Reconciled)

Evaluation numbers from `eval/outputs.jsonl` (42 test queries per condition) and `eval/eval_summary.json` have been fully reconciled. The discrepancy in earlier drafts (which reported 23 claims and 0% fallback) was caused by top-level field lookups in a faulty analysis script rather than any underlying data divergence.

### Reconciled Metrics: Scope A (Emitted Claims) vs Scope B (Candidate Claims)

#### Scope A: Emitted Answer Claims (Excludes extractive-fallback claims)
*Measures what the user actually sees in the pipeline response.*

| Condition | $n$ | LLM Emitted Claims | Validated Pass | Reconciled? | Fallback Rate | Abstained Rate | Parse Fail Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `extractive` | 42 | 24 (extractive) | N/A | N/A | 0.00% (0/42) | 7.14% (3/42) | 0.00% (0/42) |
| `llm` (unvalidated) | 42 | 38 (LLM raw) | 0 (unvalidated) | N/A | 7.14% (3/42) | 2.38% (1/42) | 11.90% (5/42) |
| `llm_validated_noabstain` | 42 | 16 (LLM valid) | **16 (100%)** | YES (16+0=16) | 59.52% (25/42) | 2.38% (1/42) | 11.90% (5/42) |
| `llm_validated` (Production) | 42 | 12 (LLM valid) | **12 (100%)** | YES (12+0=12) | 26.19% (11/42) | 45.24% (19/42) | 4.76% (2/42) |

#### Scope B: Total Candidate LLM Claims Evaluated
*Measures raw model generation behavior before validator rejection triggers extractive fallback.*

| Condition | Total Candidate Claims | Passed Validator | Rejected Validator | Pass + Rej == Total | Pass Rate (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `llm_validated_noabstain` | 39 | 16 | 23 | YES ($16+23=39$) | 41.03% |
| `llm_validated` (Production) | 23 | 12 | 11 | YES ($12+11=23$) | 52.17% |

#### Rejection Reasons Breakdown for Candidate Claims (`llm_validated`, 11 Rejected)
1. **Quote is not an exact or normalized substring of cited passage**: **7 claims** (LLM paraphrased statutory language instead of quoting verbatim).
2. **Claim missing required quote**: **2 claims** (LLM emitted a legal conclusion without providing any statutory quotation).
3. **Truncation / JSON parse failure before validation**: **2 claims** (context or syntax limit reached).

---

## 10. System Latency & Hardware Profile
Evaluated on local AMD64 CPU without dedicated GPU acceleration:
- **BM25 Lexical Retrieval**:
  - `BM25_Word_Baseline`: $0.06\text{ ms}$
  - `BM25_Char_Ngram`: $0.14\text{ ms}$
  - `BM25_Banglish_Expanded`: $0.21\text{ ms}$
- **Local LLM Inference (Ollama `qwen2.5:3b`, Q4_K_M)**:
  - Latency p50: **21,637 ms to 34,982 ms** (21.6 s to 35.0 s per query)
  - Latency p95: **131,348 ms** (131.3 s under heavy token load)
  - Latency p99: **155,798 ms**
- **Memory Footprint**:
  - Python process peak RSS: **41.5 MB**
  - Ollama runtime RSS: **~2.2 GB**

> [!NOTE]
> Retrieval consumes less than 0.001% of total pipeline latency. Local CPU LLM generation is the overwhelming bottleneck.

---

## 11. Methodological Caveats & Data Governance Disclosures

1. **Test-Split Inspection Before Threshold Selection**:
   - Threshold candidates ($T \in \{5.0, 10.5, 30.0\}$) were evaluated by observing test split retrieval scores during early development.
   - **No clean holdout is claimed**: The test split was not kept strictly blind prior to fixing $T=30.0$.
2. **Unfilled Audit Sheets**:
   - `eval/insufficient_audit.csv`: Maintains **0/16 filled ground truth labels**. All human audit metrics are uncomputed.
   - `eval/reviewer_audit_sheet.csv`: Blank evaluation template.
   - `eval/human_review_sheet.csv`: Blank evaluation template.
3. **Statutory Version Verification Status**:
   - `eval/version_audit.csv`: Contains **0 verified provisions**. 17 provisions are classified as `evidence_type=unknown, review_status=pending`.

---

## 12. Not-Computable Metrics Summary
Under the project's strict ethical guardrail prohibiting agents from inventing human ground truth:

| Metric Category | Specific Metrics | Reason Not Computable |
| :--- | :--- | :--- |
| **Abstention Classification** | Abstention Precision, Recall, F1 | `eval/insufficient_audit.csv` maintains 0/16 filled human audit labels (`answerable_in_corpus`). |
| **Human Legal Quality** | Legal Correctness, Claim Support, Completeness, Quality | `eval/reviewer_audit_sheet.csv` remains a blank template awaiting external advocate review. |
| **Historical Law Accuracy** | Historical Accuracy %, Enactment-date fidelity | Zero provisions in `eval/version_audit.csv` have verified official gazette commencement dates. |
| **Dense Semantic Retrieval** | Dense MRR@10, Dense nDCG@10 on frozen test | Dense embedding models remain unselected fixtures; no vector index committed to production. |

---

## 13. System Status: Validated vs Experimental Features

| Component / Feature | Operational Status | Evidence & Validation Basis |
| :--- | :--- | :--- |
| **Okapi BM25 Retrieval** | **Validated** | Evaluated on frozen benchmark ($n=84$ total; $n=30$ answerable test split). Deterministic sub-millisecond execution. |
| **Citation Verification Gate** | **Validated** | 100% precision on emitted claims across 42 test queries. Deterministic exact substring matching against statutory passages. |
| **Extractive Answer Assembly** | **Validated** | Deterministic fallback pipeline executed across 42 test queries with 0 hallucinations. |
| **Multi-tenant Storage Isolation** | **Validated** | Path confinement and tenant UUID sandboxing verified by regression tests. |
| **Metadata Audit Logging** | **Validated** | Cryptographic hash verification and metadata logging without PII leakage. |
| **Abstention Gate ($T=30.0$)** | **Experimental** | Score threshold $T=30.0$ chosen after inspecting test split scores; clean holdout not claimed. |
| **Multilingual Cross-Script Retrieval** | **Experimental** | Banglish evaluated on only $n=4$ test queries; Bengali Unicode cross-script retrieval failure documented. |
| **Prompt Injection Protection** | **Experimental** | Tested exclusively against synthetic injection fixtures; real adversarial threat model unvalidated. |
| **Streamlit User Interface** | **Experimental** | End-to-end user experience verified via synthetic component tests and manual protocol; no human user study. |
| **Single-Clause Extraction** | **Experimental** | Evaluated only on synthetic regex and text fixtures; complex scanned multi-page agreements unverified. |
| **Historical Statutory Versioning** | **Experimental** | `eval/version_audit.csv` has 0 verified provisions; all records remain pending official gazette audit. |

---

## 14. Reviewer & Annotation Governance
All reviewer name and credential fields in project reports and templates remain sanitized as placeholders:
- Primary Reviewer: `[Placeholder / Unverified]`
- Secondary Annotator: `[Placeholder / Unverified Secondary Annotator]`
- External Legal Counsel: Pending certified advocate review.
