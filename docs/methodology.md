# System Methodology, Architecture & Security Report

**Document Identifier**: `DOC-METH-W8-001`  
**Milestone**: Week 8 Final Freeze & Evaluation  
**Research Pipeline**: Legal Aid BD Multilingual Retrieval & RAG  
**Status**: Official System Methodology  

---

## 1. Research Question & Theoretical Scope
- **Research Question**: Can an end-to-end multilingual legal information retrieval and retrieval-augmented generation (RAG) system for Bangladesh civil and commercial law provide reliable statutory access across script variations (Bengali Unicode, Romanized Banglish transliteration, and English) while mathematically guaranteeing that every cited legal provision is authentic, grounded, and temporally valid?
- **Core Engineering Philosophy**: Absolute epistemic honesty and deterministic guardrails. Never substitute a simulator for model inference; never invent legal dates or ground truth; enforce post-hoc string containment validation to eliminate hallucinated statutory claims.

---

## 2. Retrieval Architecture & Mathematical Formulations

```
User Query (Bengali Unicode / Banglish / English)
                     │
                     ▼
       Language & Script Detection Heuristic
                     │
                     ▼
       NFC Unicode Normalization & Clean Tokenization
                     │
                     ▼
  Phonetic Dictionary Query Expansion (Banglish -> Bengali Roots)
                     │
                     ▼
       Character 3-Gram Subword Extraction
                     │
                     ▼
          Okapi BM25 Scoring Engine (k1=1.5, b=0.75)
                     │
                     ▼
     Top-K Ranked Statutory Provisions (Passage Contexts)
```

### 2.1 Okapi BM25 Retrieval Engine
Given a query $q$ comprising tokens/subwords $t \in q$ and a statutory provision document $D$ with length $|D|$:

$$\text{Score}(D, q) = \sum_{t \in q} \text{IDF}(t) \cdot \frac{f(t, D) \cdot (k_1 + 1)}{f(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

Where:
- $\text{IDF}(t) = \ln \left( \frac{N - n(t) + 0.5}{n(t) + 0.5} + 1 \right)$, with $N=17$ active provisions.
- Hyperparameters: $k_1 = 1.5$ (term frequency saturation) and $b = 0.75$ (document length penalization).
- Tie-breaking: Deterministic alphabetical sort on canonical `provision_id` (`provision_id_asc`).

### 2.2 Character Subword 3-Gram Tokenization
Standard word-level tokenization fails on agglutinative Bengali inflections and non-standardized Romanized Banglish spelling variants (e.g., *chukti*, *cukti*, *chookti* for চুক্তি). 

To ensure vocabulary overlap:
1. Strings are normalized to Unicode Normalization Form C (NFC).
2. Boundary-padded character 3-grams are generated:
   $$\text{Tokens}(w) = \{ c_i c_{i+1} c_{i+2} \mid 0 \le i \le |w|-3 \}$$
3. This guarantees that inflected suffixes (e.g., `-কে`, `-তে`, `-র`, `-গুলো`) share root n-grams with base statutory terminology.

### 2.3 Phonetic Dictionary Query Expansion
For queries identified as Romanized Banglish, phonetic legal synonyms are expanded using a curated 18-term legal dictionary:
- *shromik / sromik* $\rightarrow$ `শ্রমিক` (worker)
- *chukti / chuktipotro* $\rightarrow$ `চুক্তি` (contract / agreement)
- *bhara / vara* $\rightarrow$ `ভাড়া` (rent / tenancy)
- *bhejal / vejal* $\rightarrow$ `ভেজাল` (adulteration)
- *borkhasto / borhasto* $\rightarrow$ `বরখাস্ত` (dismissal / termination)

Expanded terms are injected as weighted subword tokens into the query representation prior to BM25 scoring.

### 2.4 Reciprocal Rank Fusion (RRF) Formulation
When combining lexical and dense candidate lists:

$$\text{RRF\_Score}(d) = \sum_{m \in M} \frac{w_m}{k_{\text{rrf}} + r_m(d)}$$

Where $k_{\text{rrf}} = 60$, $M = \{\text{lexical}, \text{dense}\}$, and $r_m(d)$ is the 1-based rank of document $d$ in system $m$.

---

## 3. Generative RAG & Deterministic Verification Engine

The generative pipeline processes retrieved provisions through a local quantized LLM (`qwen2.5:3b`, Q4_K_M via Ollama) under strict structured JSON output constraints.

```
Retrieved Top-3 Provisions (Capped at 1200 chars each)
                     │
                     ▼
    Abstention Score Gate (S(q) >= 30.0)
          │                      │
       (Below)                (Above)
          │                      │
          ▼                      ▼
  Abstain Output         Prompt Local LLM (qwen2.5:3b)
  ("Insufficient")               │
                                 ▼
                    Structured JSON Response Parser
                                 │
                                 ▼
              Deterministic Citation Verification Gate
                    ├── Check 1: Record ID exists in DB
                    ├── Check 2: Cited Act & Section match DB
                    └── Check 3: Exact substring quote containment
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
            Passes Checks               Fails Any Check
                   │                           │
                   ▼                           ▼
          Emit Validated Claim       Extractive Summary Fallback
                                     (Verbatim Statutory Sentence)
```

### 3.1 Operational Evaluation Conditions
Four parallel conditions are evaluated across all benchmark queries:
1. `extractive`: Pure deterministic assembly of top-ranked statutory sentences (zero hallucination risk).
2. `llm`: Raw unvalidated model generation.
3. `llm_validated_noabstain`: LLM generation with post-hoc citation validation, but with retrieval score thresholding disabled ($T=0.0$).
4. `llm_validated` (Production): Full pipeline with score thresholding ($T=30.0$), post-hoc citation verification, and deterministic extractive fallback upon quote rejection.

### 3.2 Abstention Threshold Formulation
Let $S(q) = \max_{p \in \text{Corpus}} \text{BM25\_Score}(q, p)$.
$$\text{Decision}(q) = \begin{cases} \text{Proceed to LLM Generation}, & \text{if } S(q) \ge T \\ \text{Abstain ("Insufficient Statutory Evidence")}, & \text{if } S(q) < T \end{cases}$$
The operational threshold is fixed at $T=30.0$.

### 3.3 Post-Hoc Citation Verification Algorithm
For every emitted claim $C = \{ \text{text}, \text{record\_id}, \text{quote} \}$:
1. **Database Existence**: Assert $\text{record\_id} \in \text{Database}$.
2. **Metadata Fidelity**: Assert $\text{Act}(C) == \text{Act}(\text{record\_id})$ and $\text{Section}(C) == \text{Section}(\text{record\_id})$.
3. **Exact Substring Groundedness**: Assert $\text{Normalize}(\text{quote}) \subseteq \text{Normalize}(\text{Passage}(\text{record\_id}))$.
4. **Leakage Scrubbing**: Free-text sections (`source_says`, `relation_to_facts`) are scrubbed of ungrounded statutory citations and URL patterns.
5. If any check fails, claim $C$ is rejected and logged with explicit reason codes (`QUOTE_NOT_IN_RECORD`, `RECORD_NOT_IN_DB`). If all claims fail, the query falls back to `extractive` assembly.

---

## 4. Multi-Tenant Document Review & Security Architecture

The single-clause and document analysis pipeline (`src/review/`) provides privacy-preserving compliance auditing for commercial leases and employment contracts.

### 4.1 Tenant Directory Sandboxing & Path Traversal Defense
Every tenant is assigned a cryptographically secure UUID (`owner_id`). Uploaded documents and derived analyses are strictly confined:
```
uploads/
  └── <owner_id>/
        └── <doc_id>/
              ├── original_document.pdf
              ├── parsed_clauses.json
              └── analysis_result.json
```
- Path traversal sequences (`../`, `..\\`) are resolved and rejected via `os.path.realpath()`.
- Access outside the tenant directory raises `PermissionError("Unauthorized tenant access")`.

### 4.2 Cross-Tenant Enforcement & Recursive Purging
- **Cross-Tenant Access**: Attempting to read, modify, or delete Tenant A's documents using Tenant B's credentials raises an explicit `PermissionError`.
- **Complete Deletion**: Deleting a document executes a recursive purge of the `<owner_id>/<doc_id>/` tree, leaving zero residual plain text, clause segments, or intermediate embeddings on disk.

### 4.3 Zero-Leakage Audit Logging
System audit logs record strictly non-sensitive cryptographic and volumetric metadata:
```json
{
  "timestamp": "2026-10-29T23:45:00Z",
  "owner_id": "4a18b2c3-...",
  "doc_id": "8f90e1d2-...",
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "size_bytes": 142850,
  "action": "clause_review_completed"
}
```
**No document text, clause excerpts, or PII are ever written to system audit logs.**

---

## 5. Compute Budget & Latency Profile

Measured on local AMD64 CPU hardware (8 cores, 16 GB physical RAM) without dedicated GPU:
- **Retrieval Phase**: Okapi BM25 executes in **0.06 ms to 0.21 ms**, representing less than 0.001% of total pipeline latency.
- **Generation Phase**: Local CPU inference via Ollama `qwen2.5:3b` (Q4_K_M) consumes **21.6 s to 35.0 s (p50)**, with p95 reaching **131.3 s**.
- **Memory Consumption**: Python runtime consumes **41.5 MB peak RSS**; Ollama runtime occupies **~2.2 GB RAM**.

---

## 6. Validated vs Experimental Features (Strict Classification)

| Feature / Component | Operational Status | Evidence & Validation Basis |
| :--- | :--- | :--- |
| **Okapi BM25 Retrieval** | **Validated** | Validated across 84 benchmark queries ($n=30$ test queries). Sub-millisecond execution. |
| **Deterministic Citation Validator** | **Validated** | 100% precision on emitted claims across 42 test queries. Exact substring verification against corpus. |
| **Extractive Answer Fallback** | **Validated** | Evaluated on 42 test queries; 0 hallucinations. Clean fallback when quotes fail. |
| **Tenant Directory Isolation** | **Validated** | Verified by unit tests (`tests/test_review.py`). Path traversal defense, complete recursive deletion. |
| **Metadata Audit Logging** | **Validated** | Cryptographic hash tracking without PII leakage. |
| **Abstention Gate ($T=30.0$)** | **Experimental** | Threshold inspected on test split scores; clean holdout not claimed. |
| **Multilingual Cross-Script Pipeline** | **Experimental** | Banglish evaluated on only $n=4$ queries; Bengali Unicode cross-script retrieval failure documented. |
| **Prompt Injection Protection** | **Experimental** | Tested exclusively against 3 synthetic fixtures with 5 injection strings; live adversarial red-teaming pending. |
| **Streamlit User Interface** | **Experimental** | Verified via component tests and manual checklist; no human user study. |
| **Single-Clause Extraction** | **Experimental** | Tested only on synthetic text fixtures; noisy multi-page scanned contracts unverified. |
| **Historical Statutory Versioning** | **Experimental** | 0/17 provisions verified against official commencement gazettes; all evaluate to `uncertain`. |

---

## 7. Not-Computable Metrics Summary
Under the project's strict ethical guardrail prohibiting agents from inventing human ground truth:

1. **Abstention Precision, Recall, and F1**: **Not computable** (`eval/insufficient_audit.csv` maintains 0/16 filled human audit labels).
2. **Human Legal Review Metrics** (Legal correctness, claim support, legal completeness, language quality, version correctness): **Not computable** (`eval/reviewer_audit_sheet.csv` and `eval/human_review_sheet.csv` remain blank templates).
3. **Historical-Law Accuracy %**: **Not computable** (`eval/version_audit.csv` maintains 0/17 verified provisions).
4. **Dense Neural Retrieval Superiority**: **Unverified / not computable** on production split (dense models remain unselected feasibility baselines).
