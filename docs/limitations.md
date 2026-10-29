# System Limitations & Methodological Disclosures

## 1. Research Question & Purpose
What are the empirical constraints, data boundaries, and methodological limitations of the Legal Aid BD retrieval-augmented legal research system?

---

## 2. Corpus Size & Scope Limitations
- **Corpus Dimension**: The active statutory corpus contains exactly **17 provisions** across five Bangladesh statutes (*Contract Act 1872*, *Transfer of Property Act 1882*, *Premises Rent Control Act 1991*, *Bangladesh Labour Act 2006*, and *Consumer Rights Protection Act 2009*).
- **Nature of Corpus**: The corpus consists of formatted text fixtures rather than an exhaustive or officially gazetted legal database.
- **Recall Ceiling**: Of the 30 answerable test queries in the benchmark, only 15 queries have their gold reference provisions present in the 17-provision corpus. The remaining 15 queries reference provisions not included in this development fixture. As a result, the maximum achievable Recall@10 across all 30 answerable test queries is **46.7%**.

---

## 3. Absence of a Clean Blind Holdout (Threshold Contamination)
> [!WARNING]
> **Threshold Selection Was Contaminated by Test Split Inspection**:
> The candidate abstention score thresholds ($T=5.0$, $T=10.5$, and $T=30.0$) were evaluated after observing retrieval score distributions across both development and test splits. Therefore, the test split cannot be represented as a pristine, untouched holdout. Reported performance metrics may reflect modest parameter tuning to known benchmark queries.

---

## 4. Local CPU Latency Bottleneck
- **LLM Generation Overhead**: Running quantized `qwen2.5:3b` (Q4_K_M) on AMD64 CPU without dedicated GPU acceleration yields median per-call latencies of **21,637 ms to 34,982 ms** (21.6 s to 35.0 s), with p95 tail latency reaching **131,348 ms** (131.3 s).
- **Retrieval vs Generation Ratio**: Lexical Okapi BM25 retrieval completes in **0.06 ms to 0.21 ms**, representing less than 0.001% of total query latency. Local CPU LLM generation is the single dominating bottleneck for production latency.

---

## 5. Blank Human Ground-Truth Sheets & Not-Computable Metrics
In compliance with strict project rules against inventing human annotations or legal reviews:
1. **Abstention Metrics**:
   - `eval/insufficient_audit.csv` contains **0/16 filled ground truth labels**.
   - Abstention Precision, Recall, and F1 are **not computable**.
2. **Legal Quality & Correctness**:
   - `eval/reviewer_audit_sheet.csv` and `eval/human_review_sheet.csv` remain **blank templates**.
   - Legal correctness, claim support, legal completeness, and language quality are **not computable** without certified advocate annotations.
3. **Historical Statute Accuracy**:
   - `eval/version_audit.csv` maintains **0/17 verified provisions** (all 17 classified as `evidence_type=unknown, review_status=pending`).
   - Historical-law accuracy is **not computable**.

---

## 6. Subgroup Statistical Caveats
- **Banglish Subgroup Small Sample Size ($n=4$)**:
  - The frozen test benchmark includes only 4 Banglish queries.
  - While Banglish phonetic expansion showed an empirical improvement on this sample, bootstrap 95% Confidence Intervals are wide ($[0.0000, 1.0000]$). No generalized statistical claim regarding Banglish retrieval superiority can be made from $n=4$ queries.
- **Statistical Significance Under Holm-Bonferroni Correction**:
  - Across the 3 pairwise retrieval comparisons (`Char vs Word`, `Banglish vs Word`, `Banglish vs Char`), only `Banglish vs Word` on Recall@10 achieved Holm-adjusted significance ($p_{adj}=0.0291$).
  - The production `Char_Ngram` model did not achieve statistically significant superiority over standard `Word_Baseline` on any metric once corrected for multiple comparisons.

---

## 7. Cross-Script Retrieval & Document Format Limitations
- **Bengali-to-English Script Barrier**:
  - Bengali Unicode queries achieve low recall against English statutory provisions ($0.0909$ Recall@10).
  - Pure lexical matching (word or character n-gram) cannot bridge vocabulary across languages without machine translation or dense semantic cross-lingual embeddings.
- **Scanned Document Ingestion**:
  - Contract and tenancy document analysis is limited to digital text layers.
  - Scanned PDFs containing raster images require external OCR pipelines, which are currently outside the core pipeline scope.

---

## 8. Classification of Validated vs Experimental Features

| Component / Feature | Classification | Basis & Empirical Limitation |
| :--- | :--- | :--- |
| **Okapi BM25 Retrieval** | **Validated** | Validated across 84 frozen benchmark queries ($n=30$ test queries). |
| **Deterministic Citation Validation** | **Validated** | 100% pass on emitted claims across 42 test queries; exact substring containment. |
| **Extractive Answer Fallback** | **Validated** | Deterministic fallback pipeline validated across 42 test queries with 0 hallucinations. |
| **Tenant File Isolation** | **Validated** | Sandboxed directory structures verified by regression test suite. |
| **Metadata Audit Logging** | **Validated** | Deterministic SHA-256 verification and clean metadata capture without PII. |
| **Abstention Gate ($T=30.0$)** | **Experimental** | Score threshold inspected on test split; no clean holdout. |
| **Multilingual Pipeline** | **Experimental** | Evaluated on only $n=4$ Banglish queries; Bengali-to-English lexical failure. |
| **Prompt Injection Defense** | **Experimental** | Tested exclusively against synthetic fixtures; live adversarial red-teaming pending. |
| **Streamlit User Interface** | **Experimental** | Verified via synthetic pipeline fidelity tests and manual checklist; no human usability study. |
| **Single-Clause Extraction** | **Experimental** | Tested only against synthetic text fixtures; multi-page legal agreements unverified. |
| **Historical Statutory Versioning** | **Experimental** | 0/17 provisions verified against official commencement gazettes. |

---

## 9. Regulatory & Ethical Disclaimer
> [!CAUTION]
> This system is an academic research prototype. It does NOT provide certified legal advice, cannot substitute for qualified legal counsel, and must NOT be used for legal representation in court proceedings.
