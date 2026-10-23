# Day 4 — Implementation Plan: Early Evaluation of Local Legal Answer Generation

**Project:** Legal Aid BD (`E:\Projects\Legal_Aid`)  
**Phase:** Day 4 — Local Legal Answer Generation vs Extractive Baseline  
**Target Environment:** Windows 11, 16 GB Physical RAM, Intel 4 CPU cores, CPU-only (No GPU).

---

## 1. Objective & Hypothesis
**Objective:** Evaluate whether a small, local multilingual instruct model (`qwen2.5:3b`, Q4_K_M quantized via Ollama on CPU) can produce reliable, evidence-grounded legal explanations that are demonstrably superior to a deterministic extractive baseline.

**Core Research Question:**
Does generative synthesis improve accessibility and cross-lingual interpretation without introducing legal hallucinations, corrupted citations, or over-confident answers on unanswerable queries?

---

## 2. Model & Runtime Architecture

| Parameter | Specification |
| :--- | :--- |
| **Model** | `qwen2.5:3b` (Qwen 2.5 3B Instruct) |
| **Quantization** | Q4_K_M (4-bit GGUF via Ollama) |
| **Parameter Count** | ~3.09 Billion parameters |
| **Disk Footprint** | ~1.9 GB download size |
| **RAM Budget** | ~2.2 – 2.5 GB peak RSS (well under 11.5 GB safety limit) |
| **Inference Hardware** | Intel CPU only (`num_threads=4`) |
| **Runtime** | Ollama 0.40.9 (`ollama serve` HTTP API on `localhost:11434`) |
| **Generation Settings** | `temperature: 0.1`, `max_tokens: 350`, `num_ctx: 2048`, `seed: 42`, timeout: 90s |

---

## 3. Evaluation Dataset Design (14 Controlled Cases)

We evaluate across 6 core legal task categories utilizing the 17 verified statutory provisions from `data/processed/provisions.jsonl`:

1. **Category A: English Statute → Bangla Explanation (2 cases)**
   - Tests cross-script translation and preservation of conditions from English laws (Contract Act Section 11, Transfer of Property Act Section 106) into Bangla.
2. **Category B: Bangla Statute → English Explanation (2 cases)**
   - Tests extraction and penalty translation from Bangla enactments (Consumer Rights 2009 Section 37, Rent Control 1991 Section 18) into English.
3. **Category C: Two-Provision Multi-hop Synthesis (2 cases)**
   - Requires integrating two distinct provisions (e.g. Contract Act Sections 10 & 11; Rent Control Sections 13 & 18) and citing both independently.
4. **Category D: Insufficient Evidence & Abstention (2 cases)**
   - Queries on statutes outside the pilot corpus (Limitation period, Cyber Security Act penalties). Tests whether the model explicitly abstains or hallucinates plausible fake law.
5. **Category E: Citation Formatting & Strict Grounding (2 cases)**
   - Verifies whether claims are anchored strictly to real schema provision IDs (`BLA2006_S২৬`, `CRPA2009_S৪৫`).
6. **Category F: Bangla / Banglish Semantic Consistency (4 cases / 2 pairs)**
   - Tests whether romanized Banglish queries produce substantive legal consistency compared to native Bengali script queries.

---

## 4. Experimental Conditions

- **Condition A (Extractive Baseline):**
  - Returns retrieved provisions verbatim with full provenance (`act_title`, `section_number`, `section_heading`, `source_file`, `provision_id`).
  - No generated inferences or summaries.
  - Returns explicit abstention message if evidence is empty or inadequate.

- **Condition B (Local Generative Model):**
  - Prompted with strict evidence-only instructions.
  - Prohibits external legal knowledge and hallucinated citations.
  - Cites provision IDs in brackets for every substantive legal claim.

---

## 5. Scoring Rubric (0 – 2 per Criterion)

Each output is evaluated across 6 criteria:
- **Citation Validity:** Are cited provisions real IDs present in the supplied passages? (2 = all valid and supplied, 1 = partial/loose, 0 = hallucinated/missing).
- **Evidence Support:** Does the cited provision actually substantiate the claim? (2 = full support, 1 = partial, 0 = ungrounded).
- **Factual Fidelity:** Are penalties, deadlines, and conditions free of hallucination? (2 = strict fidelity, 0 = hallucinated external rules).
- **Cross-Language Preservation:** Did the core legal concepts survive language translation? (2 = full fidelity, 1 = partial, 0 = distorted).
- **Completeness:** Did the response address all parts of the question? (2 = complete, 1 = partial, 0 = missed).
- **Abstention Correctness:** Did the model refuse to answer unanswerable queries? (2 = proper abstention, 0 = answered using hallucinated law).

---

## 6. Execution & Verification Steps

1. Verify Ollama service and pull `qwen2.5:3b`.
2. Run focused unit tests in `tests/test_local_generation.py`.
3. Execute `scripts/eval_local_generation.py` across all 14 cases.
4. Generate `experiments/day4_local_generation_results.json`.
5. Author comprehensive analytical report in `experiments/day4_local_generation.md`.
6. Run full project test suite (`python -m unittest discover -s tests -p "test_*.py"`).
