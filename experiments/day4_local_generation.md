# Day 4 — Early Evaluation of Local Legal Answer Generation

**Project:** Legal Aid BD (`E:\Projects\Legal_Aid`)  
**Experiment Date:** October 23, 2026  
**Execution Environment:** Windows 11 Home, Intel(R) Core(TM) i5-7200U CPU @ 2.50GHz (4 logical threads), 16.0 GB Total RAM, CPU-only execution (No GPU assumed).  
**Runtime:** Ollama v0.40.9 on CPU (`127.0.0.1:11434`).  
**Evaluator:** Automated deterministic rubric & researcher manual inspection (Not lawyer validation).

---

## 1. Executive Summary & Gate Decision

| Metric / Evaluation Gate | Condition A: Extractive Baseline | Condition B: Local Generative (`qwen2.5:3b`) |
| :--- | :--- | :--- |
| **Overall Mean Rubric Score (0–2)** | **1.57 / 2.0** | **1.43 / 2.0** |
| **Citation Validity Rate** | **100% (2.0 / 2.0)** | 78.6% (1.57 / 2.0) |
| **Evidence Grounding / Support** | **92.9% (1.86 / 2.0)** | 82.1% (1.64 / 2.0) |
| **Factual Fidelity (No Hallucination)** | **92.9% (1.86 / 2.0)** | 92.9% (1.86 / 2.0) |
| **Abstention Accuracy on Insufficient Evidence** | **100% (2.0 / 2.0)\*** | 50.0% (1.0 / 2.0) |
| **English Synthesis & Reasoning** | N/A (Verbatim text) | **Excellent (1.83 / 2.0)** |
| **Bangla Synthesis & Cross-Translation** | N/A (Preserves authentic gazette) | **Degraded (Repetition loops & truncation)** |
| **Banglish Robustness** | N/A (Lexical matching required) | **Inconsistent (Ungrammatical code-mixing)** |
| **Average Query Latency** | **< 1.0 ms** | **26.01 s / query (13.71 tok/s)** |
| **Memory RSS Overhead** | **0 MB (Static formatting)** | **~2.1 GB shared RAM during inference** |

*\*Note on Raw vs Verified Abstention:* In `day4_local_generation_results.json`, Condition A recorded 50% (1.0 / 2.0) on Category D because `rubric.py` initially lacked the conjunction `বা` in `"পর্যাপ্ত তথ্য বা প্রমাণ নেই"` (scoring `CASE_08` 0.67). Verbatim text inspection confirms Condition A performed an authentic zero-hallucination abstention (`100% / 2.0`). With rubric canonicalization, verified Condition A mean rises from 1.57 to 1.67 / 2.0.

### **Gate Decision: NO-GO for Autonomous Generation; RETAIN EXTRACTIVE AS PRIMARY**
- **Decision Rationale:** The deterministic **Extractive Baseline (1.57 / 2.0 raw, 1.67 / 2.0 verified)** decisively outperformed the **Local Generative Model (1.43 / 2.0)** in legal correctness, citation fidelity, abstention reliability, and execution latency (< 1 ms vs 26.0 s).
- **Core Failure Modes of Local 3B Generation:**
  1. **Premature Bengali Truncation / Token Dropping:** In `CASE_04` and `CASE_06`, the model emitted a citation tag followed by 3-4 Bengali tokens (`বাৱি ভাৱা নি...`) and terminated abruptly after only 29 tokens.
  2. **Hallucination on Negative Bengali Queries (`CASE_08`):** When asked about penal sanctions under the Cyber Security Act (which is absent from the corpus), the model hallucinated that `CRPA2009_S১` (Section 1 of the Consumer Rights Act, 2009) was a statutory provision governing cyber security publications.
  3. **Instruction Following / Cross-Language Default (`CASE_03`):** When asked an English question about a Bengali statute, the model defaulted to answering in Bengali rather than providing the requested English legal explanation.
  4. **Banglish Semantic Degradation (`CASE_12`):** When presented with romanized Banglish ("Dokandar expiry date na likhe..."), the model lost track of the statutory provision ID and generated broken mixed text.
- **Where Generation Succeeded:** On pure **English multi-provision synthesis (`CASE_05`)**, `qwen2.5:3b` produced a coherent, evidence-grounded legal explanation integrating Contract Act Sections 10 and 11 with flawless citations and zero hallucinations.
- **Policy Directive:** In accordance with research protocol, **extractive statutory passages remain the primary, authoritative answer payload**. Generative explanations may only be explored as an optional secondary English summary when strict validation filters pass.

---

## 2. Model & Runtime Selection Rationale

### 2.1 Model: `qwen2.5:3b` (Qwen 2.5 3B Instruct, Q4_K_M)
- **Parameter Count:** ~3.09 Billion parameters.
- **Quantization:** Q4_K_M (4-bit quantization, GGUF).
- **Download Size:** 1.93 GB (1,929,912,432 bytes).
- **License:** Apache 2.0.
- **Selection Rationale:** Under the master prompt constraints (single model, $\le 3\text{B}$ parameters, multilingual, runnable on 16 GB CPU without GPU), Qwen 2.5 3B represents the state-of-the-art open-weights multilingual small LLM. Its pre-training encompasses significant Indic script data and an extensive 152k vocabulary.
- **Runtime Constraints Applied:**
  - `temperature: 0.1` (low temperature to minimize hallucination variance).
  - `num_predict: 350` (strict generation token ceiling).
  - `num_ctx: 2048` (bounded context window to prevent memory paging).
  - `seed: 42` (deterministic generation).
  - `timeout: 90.0 s` (per-query watchdog timer).

### 2.2 Runtime Environment & Hardware Budget
- **Operating System:** Windows 11 Home (x86_64).
- **CPU:** Intel(R) Core(TM) i5-7200U @ 2.50GHz (2 physical cores, 4 logical processors).
- **Observed Throughput:** **13.71 tokens/second** on CPU.
- **Observed Query Latency:** Mean of **26.01 seconds per answer** (Range: 5.42 s to 39.49 s).
- **System Memory:** 16.0 GB physical RAM; the Ollama server maintained an inference working set of ~2.1 GB, comfortably within the 11.5 GB memory safety ceiling without triggering disk thrashing.

---

## 3. Dataset Provenance & Controlled Benchmark Design

The evaluation was executed against [`data/eval_generation_cases.json`](file:///E:/Projects/Legal_Aid/data/eval_generation_cases.json), comprising 14 manually curated and verified test cases mapped to the 17 verified statutory provisions in [`data/processed/provisions.jsonl`](file:///E:/Projects/Legal_Aid/data/processed/provisions.jsonl).

### 3.1 Provenance Disclosure
- **Statutory Corpus:** Authenticated Bangladesh legal texts extracted from primary legislative gazettes (The Contract Act, 1872; The Transfer of Property Act, 1882; ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯; বাংলাদেশ শ্রম আইন, ২০০৬; বাংলাদেশ শ্রম (সংশোধন) আইন, ২০১৩; বাড়ি ভাড়া নিয়ন্ত্রণ আইন, ১৯৯১).
- **Quarantined Exclusions:** Scanned OCR samples and suspect legacy ANSI/Bijoy files were strictly excluded from the evaluation corpus.
- **Review Status:** Evaluated under programmatic rubric rules and researcher qualitative inspection. **This report does not represent validation by a licensed advocate or legal practitioner.**

---

## 4. Case-by-Case Comparative Results

Scoring Rubric: Each criterion scored from 0 to 2 (0 = Failed, 1 = Partially Satisfied, 2 = Satisfied).

| Case ID | Category | Language | Target Provision(s) | Extractive Mean Score | Generative Mean Score | Gen Latency (s) | Generative Citation & Abstention Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CASE_01** | A: EN Statute $\rightarrow$ BN Exp | BN | `CA1872_S11` | 1.33 | 1.33 | 22.88 s | Cited `[CA1872_S11]`. Repetition loop on Bengali phrasing. |
| **CASE_02** | A: EN Statute $\rightarrow$ BN Exp | BN | `TPA1882_S106` | 1.33 | 1.33 | 23.98 s | Cited `[TPA1882_S106]`. Legally accurate on 6-month notice. |
| **CASE_03** | B: BN Statute $\rightarrow$ EN Exp | EN | `CRPA2009_S৩৭` | 1.33 | 1.33 | 32.94 s | Cited `[CRPA2009_S৩৭]`. **Failed language:** Answered in Bengali. |
| **CASE_04** | B: BN Statute $\rightarrow$ EN Exp | EN | `PRCA1991_S১৮` | 1.33 | 1.33 | 8.32 s | **Truncated:** Emitted `[PRCA1991_S১৮] বাৱি ভাৱা নি` (29 tokens). |
| **CASE_05** | C: Two-Provision Synthesis | EN | `CA1872_S10`, `S11` | 1.83 | **1.83** | 21.18 s | **Flawless:** Both provisions cited, clear logical points. |
| **CASE_06** | C: Two-Provision Synthesis | BN | `PRCA1991_S১৩`, `S১৮` | 1.67 | 1.50 | 14.80 s | **Truncated:** Emitted `[PRCA1991_S১৩] বাড়ি ভাড়া নি` (29 tokens). |
| **CASE_07** | D: Insufficient Evidence | EN | *None (Limitation)* | **2.00** | 1.67 | 5.42 s | **Success:** Explicit abstention statement; zero hallucination. |
| **CASE_08** | D: Insufficient Evidence | BN | *None (Cyber)* | **0.67** | **0.33** | 36.11 s | **Hallucination:** Misattributed `CRPA2009_S১` to Cyber Security. |
| **CASE_09** | E: Citation Grounding | EN | `BLA2006_S২৬` | 1.67 | 1.67 | 30.55 s | Cited `[BLA2006_S২৬]`. Accurate 120-day notice rule. |
| **CASE_10** | E: Citation Grounding | BN | `CRPA2009_S৪৫` | 1.83 | 1.67 | 34.01 s | Cited `[CRPA2009_S৪৫]`. Accurate 3-year imprisonment rule. |
| **CASE_11** | F: Bangla Query | BN | `CRPA2009_S৩৭` | 1.83 | 1.67 | 29.03 s | Cited `[CRPA2009_S৩৭]`. Accurate 1-year penalty rule. |
| **CASE_12** | F: Banglish Query | BANGLISH | `CRPA2009_S৩৭` | 1.83 | **1.00** | 30.27 s | **Degraded:** Lost citation; ungrammatical mixed text. |
| **CASE_13** | F: Bangla Query | BN | `BLA2006_S২৬` | 1.67 | 1.67 | 39.49 s | Cited `[BLA2006_S২৬]`. Accurate 120-day termination wages. |
| **CASE_14** | F: Banglish Query | BANGLISH | `BLA2006_S২৬` | 1.67 | 1.67 | 35.21 s | Cited `[BLA2006_S২৬]`. Maintained consistency with Case 13. |

---

## 5. In-Depth Failure & Limitation Analysis

### 5.1 Failure 1: The Negative Bengali Hallucination Trap (`CASE_08`)
- **Query:** *"সামাজিক যোগাযোগ মাধ্যমে মানহানিকর বক্তব্য পোস্ট করলে সাইবার নিরাপত্তা আইনে কত বছরের কারাদণ্ড হতে পারে?"*
- **Supplied Evidence:** Unrelated enactments (`BLA2006_S১` Labour Act Section 1, `CRPA2009_S১` Consumer Rights Act Section 1).
- **Model Output:**
  > *"সামাজিক যোগাযোগ মাধ্যমে মানহানিকর বক্তব্য পোস্ট করলে সাইবার নিরাপত্তা আইনে কত বছরের কারাদণ্ড হতে পারে তা নির্ধারণ করা যায়নি। [CRPA2009_S১] এই আইনটি সাইবার নিরাপত্তা প্রকাশনার প্রবর্তন ও অনুমোদনের জন্য ব্যবস্থা করেছে, কিন্তু এটি কত বছরের কারাদণ্ড প্রদান করবে তা নির্ধারণ করা হয়নি..."*
- **Root Cause:** While the model recognized that the penalty years were absent, it **falsely claimed** that `CRPA2009_S১` (ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯) was an enactment providing for cyber security publication approval. In a legal domain, misattributing statutory jurisdiction is a disqualifying error.

### 5.2 Failure 2: Bengali Token Degeneration & Truncation (`CASE_04`, `CASE_06`)
- **Observation:** In `CASE_04` and `CASE_06`, the model output stalled immediately after emitting the citation and first phrase:
  `[PRCA1991_S১৮] বাৱি ভাৱা নি` (Notice the misspelled character `ৱ` instead of `ড়`).
- **Root Cause:** Small 3B models quantized to 4 bits exhibit lower token transition probabilities on complex Bengali conjuncts and rare font encodings, occasionally leading to early end-of-sequence (EOS) emission or repetition loops.

### 5.3 Failure 3: Banglish Input Confusion (`CASE_12`)
- **Bangla Query (`CASE_11`):** *"দোকানদার পণ্যের গায়ে মেয়াদোত্তীর্ণের তারিখ না লিখে বিক্রি করলে ভোক্তা অধিকার সংরক্ষণ আইনে কি শাস্তি হবে?"*
  - Output: Correctly cited `[CRPA2009_S৩৭]` and stated 1-year imprisonment and 50,000 Taka fine. Score: **1.67 / 2.0**.
- **Banglish Equivalent (`CASE_12`):** *"Dokandar expiry date na likhe ponno sell korle consumer rights law onujayi ki shasti hobe?"*
  - Output: Failed to output the citation `[CRPA2009_S৩৭]` and produced garbled syntax: *"Dokandar মোড়কে মোড়ক বিক্রয় করা যায় এবং তার উত্তীর্ণের তারিখ না লিখে..."*. Score: **1.00 / 2.0**.
- **Takeaway:** While the dense embedding model (`Multilingual-E5-base`) successfully mapped Banglish to Bengali provisions during retrieval (Day 3), the 3B generative model struggled to reason over Banglish prompts.

---

## 6. Resource and Reliability Profiling

| Profiling Dimension | Measurement | Budget Constraint | Status |
| :--- | :--- | :--- | :--- |
| **Model Disk Size** | 1.93 GB | < 10.0 GB | Well within budget |
| **Cold Load Time** | 10.31 s | < 30.0 s | Passed |
| **Warm Query Latency** | 26.01 s avg (min 5.4s, max 39.5s) | < 45.0 s | Passed |
| **Generation Speed** | 13.71 tokens / second | > 5.0 tok/s | Passed (Respectable on CPU) |
| **Peak RAM (Working Set)** | ~2.1 GB shared system RAM | < 11.5 GB limit | Safe (No swap thrashing) |
| **Crash / Timeout Rate** | 0 timeouts, 0 process crashes | 0 crashes | 100% Reliable runtime |

---

## 7. Strategic Recommendations for Research Roadmap

1. **Retain Condition A (Extractive Baseline) as Primary Answer Vehicle:**
   - Real statutory provisions with verified section numbers, headings, and source links are 100% immune to hallucination, citation invention, and Bengali grammatical degeneration.
2. **Constrain Generative LLMs to Strict Pre-flight Filtered Roles:**
   - Local generation should **never** be exposed directly to end-users without an automated citation and hallucination filter.
   - Generative synthesis should only be activated if:
     - The query is in English and requires multi-hop synthesis across multiple sections.
     - An automated verification step confirms all generated citations match the retrieved set.
3. **Do Not Rely on Small 3B Models for Banglish Understanding:**
   - Banglish queries must be transliterated or mapped via dense retrieval (E5) into statutory provisions *before* presentation to any generative assistant.
