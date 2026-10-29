# Legal Aid BD — Multilingual Legal Retrieval Annotation Guidelines

**Document Identifier**: `DOC-GUIDE-W3-001`  
**Milestone**: Week 3 Evaluation Benchmark & Week 8 Freeze  
**Research Pipeline**: Cross-Script and Multilingual Legal Retrieval for Bangladesh  
**Status**: Official Guideline  

---

## Executive Research Metadata
- **Research Question**: How should multilingual legal retrieval queries and evidence links be annotated when users write in native Bengali script, Banglish phonetic transliteration, English, or Code-mixed variations?
- **Hypotheses**: Distinguishing direct legal evidence (Grade 2) from topical overlap (Grade 0/1) will prevent hallucinated legal reasoning and ground retrieval benchmarks in verifiable statutory authority.
- **Baselines**: Topical keyword overlap matching and single-provision greedy lookup.
- **What Was Tested**: 120 multi-script legal queries evaluated across 4 civil domains, including single-provision, multi-provision dependencies, and unanswerable/negative controls.
- **Sources Used**: Statutory texts of Contract Act 1872, Transfer of Property Act 1882, Premises Rent Control Act 1991, Bangladesh Labour Act 2006, Consumer Rights Protection Act 2009.
- **What Improved**: Strict separation of topicality vs legal evidence; clear inter-annotator agreement guidelines with explicit Banglish transliteration protocols.
- **What Failed**: Cross-lingual semantic alignment remains imperfect when annotators evaluate Banglish idioms against formal Bengali legislative prose.
- **Which Claims Are Unverified**: Full legal validity of annotations remains provisional until finalized by an enrolled Advocate (`annotation_status: "researcher_annotated_provisional"`).

---

## 1. Objective & Scope

This document defines the formal taxonomy and decision procedure for annotating query-provision pairs in the **Legal Aid BD** multilingual benchmark. The benchmark evaluates statutory retrieval across four linguistic modalities:
- **Bangla Unicode (`bn_unicode`)**: Native Bengali script.
- **Banglish (`banglish`)**: Phonetic Romanized transliteration of Bengali.
- **English (`en`)**: Formal or colloquial English legal queries.
- **Code-Mixed (`code_mixed`)**: Bengali syntactic framing with embedded English legal and commercial loanwords.

---

## 2. Fundamental Epistemic Distinction: Topicality vs. Legal Evidence

Annotators must strictly separate **topical relevance** from **legal evidence sufficiency**:

```
[Query]
"দোকানদার পণ্যের গায়ে মেয়াদোত্তীর্ণের তারিখ না লিখে বিক্রি করলে কি শাস্তি হবে?"
(What is the penalty if a shopkeeper sells goods without an expiry date on the packaging?)

[Candidate Passage A — Topically Related, Non-Evidential]
Section 38, Consumer Rights Protection Act 2009:
"দোকানে পণ্যের মূল্য তালিকা প্রদর্শন না করিবার দণ্ড..."
(Penalty for failing to display the price list in a shop...)
-> RATING: Irrelevant / Topically Related Only (Grade 0).
-> REASONING: It mentions shopkeepers and product compliance, but does NOT answer the legal question regarding expiry dates or the specific statutory penalty.

[Candidate Passage B — Direct Legal Evidence]
Section 37, Consumer Rights Protection Act 2009:
"পণ্যের মোড়কে পণ্যের খুচরা বিক্রয় মূল্য, ওজন বা মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ড, বা অনধিক পঞ্চাশ হাজার টাকা অর্থদণ্ড, বা উভয় দণ্ডে দণ্ডনীয় হইবেন।"
(If expiry date is not stated on packaging, punishable by up to 1 year imprisonment or up to 50,000 taka fine or both.)
-> RATING: Direct Legal Evidence (Grade 2).
-> REASONING: Provides the exact statutory provision containing the operative legal prohibition and the quantified penal consequences.
```

---

## 3. Four-Tier Relevance Grading Rubric

Every candidate provision evaluated against a user query is assigned one of four categorical grades:

| Grade | Label | Operational Definition | Legal Retrieval Criteria |
|:---:|:---|:---|:---|
| **0** | **Irrelevant** | Completely unrelated or tangentially related without legal overlap. | The passage does not discuss the subject matter or mentions common legal words without situational overlap. |
| **1** | **Topically Related (Contextual)** | Discusses the same general statute, administrative agency, or legal domain, but does *not* contain the rule or consequence sought. | Helps provide background context (e.g., definitions, jurisdiction of court) but does not supply the legal rule to answer the query. |
| **2** | **Supporting Evidence (Secondary / Multi-part)** | Contains an essential component of the answer (e.g., an exception, cross-referenced definition, or procedural timeline) when the answer requires combining multiple sections. | Must be retrieved alongside the primary provision to formulate a legally complete and sound answer. |
| **3** | **Direct Legal Evidence (Primary)** | Contains the primary operative statutory rule, prohibition, entitlement, or penal sanction that directly resolves the user's scenario. | A lawyer citing this provision alone can directly answer the core factual inquiry. |

> [!IMPORTANT]
> For standard Information Retrieval metrics (Recall@K, MRR@K), **Grades 2 and 3** are mapped to binary relevant ($rel = 1$). Grade 0 and Grade 1 are treated as non-relevant ($rel = 0$). For graded metrics (nDCG@K), the 4-tier scale is used directly.

---

## 4. Benchmark Case Schema Specification

Every benchmark case in `data/benchmarks/*.jsonl` must strictly conform to the following JSON schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LegalAidBenchmarkCase",
  "type": "object",
  "required": [
    "query_id",
    "scenario_id",
    "split",
    "original_user_query",
    "language_and_script",
    "legal_domain",
    "expected_supporting_provisions",
    "single_or_multi_provision",
    "corpus_has_sufficient_evidence",
    "expected_answer_criteria",
    "annotation_confidence",
    "annotation_status",
    "reviewer_notes"
  ],
  "properties": {
    "query_id": {
      "type": "string",
      "pattern": "^BNCH_[A-Z0-9_]+$"
    },
    "scenario_id": {
      "type": "string",
      "pattern": "^SCENARIO_[A-Z0-9_]+$"
    },
    "split": {
      "type": "string",
      "enum": ["dev", "test"]
    },
    "original_user_query": {
      "type": "string",
      "minLength": 5
    },
    "language_and_script": {
      "type": "string",
      "enum": ["bn_unicode", "banglish", "en", "code_mixed"]
    },
    "legal_domain": {
      "type": "string",
      "enum": [
        "land_tenancy",
        "consumer_protection",
        "employment_labour",
        "contractual_obligations"
      ]
    },
    "expected_supporting_provisions": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 0
    },
    "single_or_multi_provision": {
      "type": "string",
      "enum": ["single", "multi", "none"]
    },
    "corpus_has_sufficient_evidence": {
      "type": "boolean"
    },
    "expected_answer_criteria": {
      "type": "string"
    },
    "annotation_confidence": {
      "type": "string",
      "enum": ["High", "Medium", "Low"]
    },
    "annotation_status": {
      "type": "string",
      "enum": [
        "lawyer_reviewed_gold",
        "researcher_annotated_provisional",
        "unreviewed"
      ]
    },
    "reviewer_notes": {
      "type": "string"
    }
  }
}
```

---

## 5. Multi-Provision & Unanswerable Query Protocol

### 5.1 Multi-Provision Dependencies
Where an answer depends on more than one section (e.g., Section 10 of Contract Act defines contract validity, while Section 11 specifies age of majority; or Section 13 of Premises Rent Control Act establishes standard rent while Section 18 limits eviction grounds):
- Set `single_or_multi_provision: "multi"`.
- List all co-requisite provision IDs in `expected_supporting_provisions`.
- Scoring: In strict evaluation, Recall@K awards full credit only when **all** co-requisite provisions appear in the top $K$.

### 5.2 Unanswerable / Out-of-Scope Test Cases
To evaluate model hallucination and abstention:
- Approximately 5–10% of benchmark queries describe scenarios whose legal answer is **not** present in the statutory corpus (e.g., matrimonial dowry offences under Women and Children Repression Prevention Act, or criminal murder under Penal Code 1860).
- Set `corpus_has_sufficient_evidence: false`.
- Set `expected_supporting_provisions: []`.
- Set `single_or_multi_provision: "none"`.
- A retrieval system should ideally assign low confidence scores to all indexed provisions for these queries.

---

## 6. Provisional Annotation Governance

In accordance with the Week 0 Reviewer Protocol (`docs/reviewer_protocol.md`):
- All cases annotated prior to formal validation by an enrolled Advocate of the Supreme Court of Bangladesh or District Bar must be labeled:
  ```json
  "annotation_status": "researcher_annotated_provisional"
  ```
- Retrieval benchmark metrics must be documented with this provisional status banner until the lawyer verification milestone is executed.

