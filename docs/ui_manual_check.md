# Streamlit UI Manual Verification Checklist

> [!IMPORTANT]
> **DISCLAIMER**: The Legal Aid BD web interface (`app/ui.py`) is **NOT** claimed to be automatically validated. While unit tests verify that the UI consumes `src.pipeline.ask()` outputs without field mutation or dropped attributes, interactive rendering, visual formatting, and frontend user flows require human verification. Follow this checklist to manually validate the application.

---

## 1. Environment & Host Binding Security Verification

- [ ] **Default Safe Local Binding**:
  - Run: `streamlit run app/ui.py`
  - Verify console output shows network address bound strictly to `http://localhost:8501` or `http://127.0.0.1:8501`.
  - Confirm UI is inaccessible from remote network interfaces.
- [ ] **Wildcard Binding Refusal Gate**:
  - Run: `streamlit run app/ui.py --server.address 0.0.0.0`
  - Verify that the application halts with a critical security error and refuses to start unless `ALLOW_INSECURE_ALL_INTERFACES=1` is explicitly set.

---

## 2. Tab 1: Statutory Inquiry (RAG) Verification

### 2.1 Input Controls & Language Handling
- [ ] **Language Selection**:
  - Select `auto` mode; submit a Bengali query (e.g., `শ্রমিককে বরখাস্তের নিয়ম কী?`). Confirm "Detected Language" displays `bn (Override: False)`.
  - Select `auto` mode; submit an English query (e.g., `What is the notice period for permanent worker resignation?`). Confirm detected language is `en`.
  - Select `auto` mode; submit a Banglish query (e.g., `shromik ke chakri theke borkhasto korle ki khotipuron pabe?`). Confirm detected language is `banglish`.
  - Manually select `en` for a Bengali query. Confirm "Detected Language" reflects `en (Override: True)`.
- [ ] **Query Normalization**:
  - Verify that both original user query and Unicode normalized query are displayed when whitespace or NFC differences exist.
- [ ] **Operational Mode Selector**:
  - Test dropdown for all 4 operational modes: `llm_validated`, `extractive`, `llm`, `llm_validated_noabstain`.

### 2.2 Operational State Badges
Verify that the 5 status badges transition accurately across query types:

1. **Retrieved State**:
   - `State: RETRIEVED` (Green) when statutory hits exist.
   - `State: NOT RETRIEVED` (Gray/Red) if corpus returns 0 hits.
2. **Citation Verification State**:
   - `State: VERIFIED AGAINST CORPUS` (Green) when at least one cited claim passes exact substring validation.
   - `State: UNVERIFIED CITATIONS` (Blue/Yellow) when claims fail or no claims are emitted.
3. **Legal Status State**:
   - `State: LEGAL STATUS VERIFIED` (Green) when all retrieved provisions have verified in-force metadata.
   - `State: LEGAL STATUS UNCERTAIN` (Yellow/Warning) when provisions have unverified effective dates or missing manifest verification dates.
4. **Evidence Sufficiency State**:
   - `State: SUFFICIENT EVIDENCE` (Green) when top retrieval score $\ge 30.0$.
   - `State: INSUFFICIENT EVIDENCE` (Red) when top retrieval score $< 30.0$ and pipeline abstains.
5. **Model / Fallback State**:
   - `State: PRIMARY MODEL` (Green) when LLM claims validate successfully.
   - `State: FALLBACK USED` (Yellow) when extractive fallback is deployed.

### 2.3 Answer & Citation Integrity Display
- [ ] **Generated Answer Panel**:
  - Verify answer text is displayed with language tag.
  - If abstained, verify standard insufficiency notice is shown.
- [ ] **Validation Log (Un-obscured Failure Audit)**:
  - Check that validator rejections are visibly displayed with full failure reasons (e.g., `Quote is not an exact or normalized substring`, `Forbidden leakage pattern detected`).
  - Confirm failed claims are never hidden or silently dropped.
- [ ] **Retrieved Statutory Evidence Panel**:
  - Expand retrieved provisions.
  - Verify Rank, BM25 score, Act Title, Section Number, Version Status, and full provision text are displayed.
  - Test "Export Provision Metadata" download button and verify downloaded text file contents.

---

## 3. Tab 2: Document Clause Review Verification

### 3.1 Document Upload & Format Checks
- [ ] **Allowed Formats**:
  - Upload `tests/fixtures/synthetic_employment_agreement.docx`. Confirm upload succeeds and clauses are extracted.
  - Upload `tests/fixtures/synthetic_commercial_lease.pdf`. Confirm upload succeeds.
  - Attempt upload of an unsupported file format (e.g., `.txt`, `.exe`). Confirm error banner prevents processing.
- [ ] **File Size Enforcement**:
  - Attempt upload exceeding configured max limit (25 MB). Confirm size warning is displayed and file is rejected.

### 3.2 Clause Extraction & Scanned Document Gate
- [ ] **Scanned / Garbled Document Gate**:
  - Upload `tests/fixtures/synthetic_scanned_contract_garbled.pdf`.
  - Confirm the UI indicates `needs_manual_correction = True` and displays an explicit notice that no automated legal findings are generated for unverified scanned/garbled text.
- [ ] **Clause Selection**:
  - For `synthetic_employment_agreement.docx`, use the clause selector dropdown to navigate across clauses (e.g., `clause_1`, `clause_2`, `clause_3`).
  - Confirm character start and end spans match original document text.

### 3.3 Clause Findings & Security Flags
- [ ] **Finding Classification**:
  - Verify findings display one of three strict labels:
    - `drafting_concern`
    - `possible_legal_issue`
    - `unsupported_finding`
  - Verify: If no validated citation exists, finding is strictly `unsupported_finding`.
- [ ] **Security Flags**:
  - Confirm that security flags (such as `PROMPT_INJECTION_DETECTED_IN_CLAUSE` or `SYSTEM_CHANGE_INSTRUCTIONS_REJECTED`) are visibly reported in the findings banner if injection strings are detected.

