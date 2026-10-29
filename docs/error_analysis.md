# Comprehensive Error Analysis, Taxonomy & Failure Case Studies

**Document Identifier**: `DOC-ERR-W8-001`  
**Milestone**: Week 8 Final Freeze & Evaluation  
**Research Pipeline**: Legal Aid BD Multilingual Retrieval & RAG  
**Status**: Official Error Analysis Report  

---

## 1. Research Question & Diagnostic Scope
- **Research Question**: What are the empirical failure modes in multilingual legal information retrieval and generative RAG when processing native Bengali, Banglish transliteration, and English inquiries under strict factual grounding constraints?
- **Diagnostic Method**: Seeded random sampling ($seed=42$) across 9 required operational categories PLUS the 10 lowest-ranked test split failures from [`eval/outputs.jsonl`](file:///e:/Projects/Legal_Aid/eval/outputs.jsonl), cataloged in [`eval/error_cases.csv`](file:///e:/Projects/Legal_Aid/eval/error_cases.csv).
- **Epistemic Ethics**: Columns `likely_cause` and `reviewer_notes` in `eval/error_cases.csv` are deliberately kept **strictly blank** pending independent human legal audit.

---

## 2. Systematic Error Case Taxonomy (19 Cases)

| Case ID | Operational Category | Query / Clause Text | Observed System Output | Expected Ground Truth |
| :--- | :--- | :--- | :--- | :--- |
| **CASE_01** | `bangla_retrieval_success` | বাড়িওয়ালা কি ইচ্ছামত ভাড়া বাড়িয়ে আমাকে বাড়ি থেকে উচ্ছেদ করতে পারবে? | PRCA1991_S১৮ (Rank 1, Score 62.96) | PRCA1991_S18, PRCA1991_S13 |
| **CASE_02** | `banglish_retrieval_success` | Minor ba 18 bochorer kom boyosher keu business contract sign korle oita ki valid? | CA1872_S11 (Rank 1, Score 19.71) | CA1872_S11 |
| **CASE_03** | `english_retrieval_success` | Is registration of a deed mandatory to transfer ownership of immovable property? | TPA1882_S54 (Rank 1, Score 95.00) | TPA1882_S54 |
| **CASE_04** | `missed_provision` | Packet e price na likhe overprice e sell korle double offense e ki shasti hoy? | TPA1882_S54, TPA1882_S106 (Gold absent) | CRPA2009_S৩৭, CRPA2009_S৩৯ |
| **CASE_05** | `wrong_ranking` | পণ্যের আকর্ষণীয় কিন্তু মিথ্যা বিজ্ঞাপন দিলে আইনের দৃষ্টিতে উহা কী ধরনের অপরাধ? | CRPA2009_S৩৭ (Rank 8, Score 34.76) | CRPA2009_S৪৫ (Expected Rank 1–3) |
| **CASE_06** | `unsupported_answer` | ভারতে বাড়ি ভাড়ার ক্ষেত্রে কি মডেল টেন্যান্সি অ্যাক্ট অনুযায়ী নোটিশ কার্যকর হয়? | PRCA1991_S১৮ (Top Score 37.49 < 30.0 -> Abstained) | NONE (Insufficient evidence / Abstain) |
| **CASE_07** | `citation_failure` | কোন ব্যক্তি কোন আইন বা বিধির অধীন নির্ধারিত বাধ্যবাধকতা অমান্য করিয়া... | Validator rejected quote (paraphrase) | Exact verbatim statutory excerpt |
| **CASE_08** | `version_uncertainty` | Legal status of Section 26 of Labour Act as of 2005-01-01 | BLA2006_S26 evaluated as `uncertain` | verified_not_in_force (Enacted 2006) |
| **CASE_09** | `clause_review_false_positive`| Clause 4. Both parties agree to act in good faith and resolve disputes amicably. | Flagged as unsupported finding | No legal violation (benign clause) |
| **CASE_10** | `lowest_ranked_failure` | Is publishing false or misleading advertisements to deceive consumers a punishable offense? | TPA1882_S54, CA1872_S2 (Score 34.76) | CRPA2009_S৪৫ |
| **CASE_11** | `lowest_ranked_failure` | Packet e price na likhe overprice e sell korle double offense e ki shasti hoy? | TPA1882_S54, TPA1882_S106 (Score 18.76) | CRPA2009_S৩৭, CRPA2009_S৩৯ |
| **CASE_12** | `lowest_ranked_failure` | Combined penalty for not marking retail price and charging above fixed rate? | CA1872_S2, TPA1882_S54 (Score 34.49) | CRPA2009_S৩৭, CRPA2009_S৩৯ |
| **CASE_13** | `lowest_ranked_failure` | ১৮ বছরের কম বয়সী ব্যক্তির সহিত কোনো লিখিত চুক্তিপত্র সম্পাদিত হইলে উহা কেন বাতিল বলিয়া গণ্য হয়? | CRPA2009_S৩৭, BLA2006_S২৬ (Score 22.78) | CA1872_S10, CA1872_S11 |
| **CASE_14** | `lowest_ranked_failure` | How many days notice or compensation must an employer provide to terminate a permanent worker? | TPA1882_S106, CA1872_S2 (Score 39.35) | BLA2006_S২৬ |
| **CASE_15** | `lowest_ranked_failure` | Simple termination ar misconduct dismissal er moddhe compensation difference ki? | CA1872_S2, TPA1882_S106 (Score 27.37) | BLA2006_S২৬, BLAA2013_S৭ |
| **CASE_16** | `lowest_ranked_failure` | Difference in terminal benefits between simple termination and dismissal for misconduct? | TPA1882_S106, CA1872_S2 (Score 39.48) | BLA2006_S২৬, BLAA2013_S৭ |
| **CASE_17** | `lowest_ranked_failure` | বিনিময় বা প্রতিদান ছাড়া সম্পাদিত চুক্তি কি আইনের দৃষ্টিতে বাতিল বলিয়া গণ্য হইবে? | BLAA2013_S৭, PRCA1991_S১৮ (Score 24.12) | CA1872_S25 |
| **CASE_18** | `lowest_ranked_failure` | সম্পত্তি বিক্রয়ের চুক্তি অনুসারে দখল পাইলে ক্রেতাকে কি বিক্রেতা বেদখল করিতে পারে? | CRPA2009_S৩৭, PRCA1991_S১৩ (Score 27.32) | TPA1882_S53A |
| **CASE_19** | `lowest_ranked_failure` | পাঁচ বছর চাকরির পর শ্রমিক স্বেচ্ছায় পদত্যাগ করিলে কি কোনো ক্ষতিপূরণ পাইবেন? | BLA2006_S২৬, BLA2006_S২০ (Score 28.05) | BLA2006_S২৭ |

---

## 3. Deep-Dive Case Studies Across Representative Categories

### 3.1 Bangla Retrieval Success (`CASE_01`)
- **Query**: `"বাড়িওয়ালা কি ইচ্ছামত ভাড়া বাড়িয়ে আমাকে বাড়ি থেকে উচ্ছেদ করতে পারবে?"` (Can a landlord arbitrarily increase rent and evict me from the house?)
- **System Behavior**: Okapi BM25 with character 3-grams scored Section 18 of the Premises Rent Control Act 1991 (`PRCA1991_S18`) at **62.96**, ranking it #1.
- **Why It Succeeded**: Both query and statute are in native Bengali script; root character trigrams (`বাড়ি`, `ভাড়`, `উচ্ছ`) strongly aligned with statutory phrases protecting tenants against arbitrary eviction.

### 3.2 Banglish Retrieval Success (`CASE_02`)
- **Query**: `"Minor ba 18 bochorer kom boyosher keu business contract sign korle oita ki valid?"`
- **System Behavior**: Retrieved Section 11 of the Contract Act 1872 (`CA1872_S11`) at Rank 1 (Score 19.71).
- **Why It Succeeded**: Character 3-gram subwords (`con`, `ont`, `tra`, `act`) matched the English text of Section 11 ("Who are competent to contract... age of majority"). Standard word BM25 scored this lower due to morphological noise, but character subwords successfully isolated the legal tokens.

### 3.3 English Retrieval Success (`CASE_03`)
- **Query**: `"Is registration of a deed mandatory to transfer ownership of immovable property?"`
- **System Behavior**: Retrieved Section 54 of the Transfer of Property Act 1882 (`TPA1882_S54`) at Rank 1 with an exceptional score of **95.00**.
- **Why It Succeeded**: Near-verbatim vocabulary match with statutory text defining sale and registration requirements for tangible immovable property of value one hundred taka and upwards.

### 3.4 Missed Provision & Fixture Ceiling (`CASE_04` & `CASE_11`)
- **Query**: `"Packet e price na likhe overprice e sell korle double offense e ki shasti hoy?"`
- **System Behavior**: Retrieved unrelated property provisions (`TPA1882_S54`, `TPA1882_S106`). Target provisions (`CRPA2009_S37` and `CRPA2009_S39`) were absent from the top 10.
- **Underlying Cause**: Section 39 of CRPA 2009 (charging above fixed price) was not included in the 17-provision fixture corpus. The query requires multi-provision synthesis; missing half the statutory context caused complete retrieval degradation.

### 3.5 Generative Citation Failure & Substring Rejection (`CASE_07`)
- **Prompted Statutory Evidence**: Passage from Section 37 of Consumer Rights Protection Act 2009.
- **Model Output**: Emitted claim concluding that failing to label expiry dates is punishable by up to 1 year imprisonment or 50,000 taka fine.
- **Validator Action**: **REJECTED**. The model paraphrased the statutory clause rather than quoting verbatim (`"দোকানদার পণ্যের মোড়কে..."` instead of `"কোন ব্যক্তি কোন আইন বা বিধির অধীন..."`).
- **Pipeline Recovery**: Because the claim failed the exact substring containment check, the pipeline safely fell back to `extractive` assembly, emitting the verbatim statutory text and preventing an unverified paraphrased citation from reaching the user.

### 3.6 Temporal Version Uncertainty (`CASE_08`)
- **Query**: Temporal in-force inquiry regarding Section 26 of Labour Act as of `2005-01-01`.
- **System Behavior**: Returns `version_status = "uncertain"` and appends an explicit warning to the response.
- **Why It Occurred**: The active corpus metadata contains no official gazette commencement record for BLA 2006. In the absence of an authenticated commencement gazette date, the temporal retrieval gate conservatively refuses to assert in-force or repealed status.

---

## 4. Categorized Failure Causes Across the Pipeline

```
                              Pipeline Failure Modes
                                        │
     ┌──────────────────┬───────────────┴───────────────┬──────────────────┐
     ▼                  ▼                               ▼                  ▼
1. Source Quality  2. Annotation Ambiguity      3. Tokenization Gap  4. Cross-Script Gap
(17 Provision      (Multi-section dependencies   (Word BM25 fails    (Bengali query to
 Fixture Ceiling)   diluting top-1 ranks)         on Banglish)        English statute)
```

1. **Source Quality & Constrained Fixture Size**:
   - The primary limiting factor of the benchmark is that 15 of 30 answerable test queries reference statutory sections not indexed in the 17-provision fixture corpus.
2. **Annotation Ambiguity & Multi-Section Dependencies**:
   - Queries spanning definitions (e.g. CA 1872 Section 2) and operative rules (CA 1872 Section 10) frequently elevate one section while missing the second, degrading composite Recall@10.
3. **Tokenization Mismatch**:
   - Standard word-level Okapi BM25 fails when users provide non-standard Romanized spelling variants. While character 3-grams mitigate this, they introduce spurious subword collisions across unrelated acts.
4. **Cross-Script Translation Gap**:
   - Lexical retrieval engines cannot cross the Unicode Bengali to Latin English script barrier without semantic bi-encoders or automated translation. Bengali queries against English statutes yield $0.0000$ Jaccard token overlap.
5. **Legislative Version Uncertainty**:
   - Due to the complete absence of verified gazette commencement dates ($0/17$ active provisions), temporal filtering cannot definitively validate historical law.

---

## 5. Epistemic Ethics & Blank Reviewer Columns
In accordance with the project's strict research guidelines:
- The columns `likely_cause` and `reviewer_notes` in `eval/error_cases.csv` are deliberately preserved as empty strings.
- System developers and AI agents are prohibited from guessing or auto-attributing legal blame.
- Final causal attribution and legal adequacy ratings will be populated only after independent review by an enrolled Advocate of the Supreme Court of Bangladesh.
