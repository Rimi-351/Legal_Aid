# Legal Corpus & Legislative Provenance Report

**Document Identifier**: `DOC-CORPUS-W8-001`  
**Milestone**: Week 8 Final Freeze & Evaluation  
**Research Pipeline**: Legal Aid BD Multilingual Retrieval & RAG  
**Status**: Official Frozen Corpus Audit  

---

## 1. Executive Research Metadata & Research Question
- **Research Question**: Can an authentic, section-aware statutory corpus for Bangladesh civil and commercial law be constructed such that every retrieved provision can be traced back to verified manifests with cryptographic checksums, deterministic quarantine controls, and auditability?
- **Core Empirical Finding**: The current evaluation corpus consists strictly of **17 active statutory provisions** and **2 quarantined provisions** (19 total records) formatted as standardized sample text fixtures. None of the provisions are live-scraped or official government gazette scans.
- **Corpus Digest**: `870f235476ebb338cf9c829e549fca562ccdf6f0e276aac05f19cb914c8db351` (`data/processed/provisions.jsonl`).
- **Source Manifest Digest**: `60d8db4ed3b72549ac03614ab3bc7ebfe523595476d2b8e798c869ee1987d493` (`data/manifests/processed_manifest.jsonl`).

---

## 2. Ingestion Pipeline & Section-Aware Chunking Architecture

The ingestion pipeline (`scripts/run_ingestion.py`) implements a discrete, section-aware legal parser rather than fixed-length token chunking. Legal statutes depend on defined legislative units; arbitrary token boundaries sever definitions from penal sanctions and operative provisos.

```
Raw Statutory Fixtures (tests/fixtures/)
      │
      ▼
Section-Aware Parser (HTML / Text)
      │
      ├── Extracts: Act Title, Act Number, Publication Date, Section ID, Heading, Body Text
      │
      ▼
Quality & Integrity Quarantine Gate
      ├── Rule 1: Minimum text length (> 50 chars)
      ├── Rule 2: OCR garble & noise filter
      └── Rule 3: Character encoding check (NFC Unicode compliance)
      │
      ├── Pass ──> Active Corpus Index (17 provisions)
      └── Fail ──> Quarantine Log (2 provisions)
```

---

## 3. Detailed Corpus Composition (19 Records)

### 3.1 Distribution Across Legislative Enactments
All 19 records originate directly from `tests/fixtures/sample_*.html` and `tests/fixtures/sample_*.txt` with provenance tagged as `"fixture"`:

| Legislative Instrument | Act Number | Active Provisions | Quarantined | Total Records | Dominant Language |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯** (CRPA 2009) | Act No. XXVI of 2009 | 3 | 0 | 3 | Bengali (`bn`) |
| **The Contract Act, 1872** (CA 1872) | Act No. IX of 1872 | 4 | 0 | 4 | English (`en`) |
| **বাংলাদেশ শ্রম আইন, ২০০৬** (BLA 2006) | Act No. XLII of 2006 | 3 | 0 | 3 | Bengali (`bn`) |
| **বাংলাদেশ শ্রম (সংশোধন) আইন, ২০১৩** (BLAA 2013) | Act No. XXX of 2013 | 2 | 0 | 2 | Bengali (`bn`) |
| **বাড়ি ভাড়া নিয়ন্ত্রণ আইন, ১৯৯১** (PRCA 1991) | Act No. III of 1991 | 3 | 0 | 3 | Bengali (`bn`) |
| **The Transfer of Property Act, 1882** (TPA 1882) | Act No. IV of 1882 | 2 | 0 | 2 | English (`en`) |
| *Scanned Gazette OCR Notice* | Synthetic Test Fixture | 0 | 1 | 1 | Undetermined (Quarantine) |
| *Suspect Legacy Encoding Sample* | Synthetic Test Fixture | 0 | 1 | 1 | Undetermined (Quarantine) |
| **Total Statutory Corpus** | — | **17** | **2** | **19** | 11 `bn`, 6 `en`, 2 `undetermined` |

### 3.2 Granular Provision Inventory

| Provision ID | Act Title | Section Number | Language | Character Length | Source Fixture File |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `CA1872_S2` | The Contract Act, 1872 | 2 | `en` | 1,842 | `sample_contract_act_1872.html` |
| `CA1872_S10` | The Contract Act, 1872 | 10 | `en` | 385 | `sample_contract_act_1872.html` |
| `CA1872_S11` | The Contract Act, 1872 | 11 | `en` | 278 | `sample_contract_act_1872.html` |
| `CA1872_S25` | The Contract Act, 1872 | 25 | `en` | 1,120 | `sample_contract_act_1872.html` |
| `TPA1882_S54` | The Transfer of Property Act, 1882 | 54 | `en` | 1,415 | `sample_transfer_of_property_1882.html` |
| `TPA1882_S106` | The Transfer of Property Act, 1882 | 106 | `en` | 1,680 | `sample_transfer_of_property_1882.html` |
| `PRCA1991_S7` | বাড়ি ভাড়া নিয়ন্ত্রণ আইন, ১৯৯১ | ৭ | `bn` | 642 | `sample_premises_rent_1991.html` |
| `PRCA1991_S13` | বাড়ি ভাড়া নিয়ন্ত্রণ আইন, ১৯৯১ | ১৩ | `bn` | 890 | `sample_premises_rent_1991.html` |
| `PRCA1991_S18` | বাড়ি ভাড়া নিয়ন্ত্রণ আইন, ১৯৯১ | ১৮ | `bn` | 2,150 | `sample_premises_rent_1991.html` |
| `BLA2006_S20` | বাংলাদেশ শ্রম আইন, ২০০৬ | ২০ | `bn` | 1,320 | `sample_labour_act_2006.html` |
| `BLA2006_S26` | বাংলাদেশ শ্রম আইন, ২০০৬ | ২৬ | `bn` | 2,410 | `sample_labour_act_2006.html` |
| `BLA2006_S27` | বাংলাদেশ শ্রম আইন, ২০০৬ | ২৭ | `bn` | 1,560 | `sample_labour_act_2006.html` |
| `BLAA2013_S7` | বাংলাদেশ শ্রম (সংশোধন) আইন, ২০১৩ | ৭ | `bn` | 840 | `sample_labour_amendment_2013.html` |
| `BLAA2013_S10` | বাংলাদেশ শ্রম (সংশোধন) আইন, ২০১৩ | ১০ | `bn` | 620 | `sample_labour_amendment_2013.html` |
| `CRPA2009_S37` | ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯ | ৩৭ | `bn` | 980 | `sample_consumer_rights_2009.html` |
| `CRPA2009_S38` | ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯ | ৩৮ | `bn` | 740 | `sample_consumer_rights_2009.html` |
| `CRPA2009_S45` | ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯ | ৪৫ | `bn` | 1,020 | `sample_consumer_rights_2009.html` |

---

## 4. Quarantine Mechanism & Integrity Controls

Two provisions in `data/processed/provisions.jsonl` are flagged with `quarantine = true` and excluded from the retrieval index:
1. `sample_scanned_gazette_ocr_notice`:
   - **Reason**: Rasterized scanned PDF text artifact with high character error rate (CER > 35%), broken Unicode character representations, and absent section headers.
   - **Action**: Quarantined; logged with `needs_manual_correction = true`.
2. `sample_suspect_bijoy_legacy`:
   - **Reason**: Unconverted legacy ANSI/Bijoy 8-bit encoded text failing NFC Unicode validation.
   - **Action**: Quarantined; prevents corrupted character n-gram indexing.

---

## 5. Legislative Provenance & Version Audit

The statutory version audit conducted via `scripts/audit_versions.py` and output to [`eval/version_audit.csv`](file:///e:/Projects/Legal_Aid/eval/version_audit.csv) evaluated all provisions for amendment status, repeal relations, and official commencement gazette provenance:

### 5.1 Version Audit Summary
- **Total Provisions Audited**: 19 records.
- **Official Commencement Coverage (`effective_date`)**: **0.00% (0/19)**. Zero provisions currently have verified official Gazette commencement dates.
- **Enactment Date Coverage (`enactment_date`)**: **89.47% (17/19)**. Active provisions carry formal enactment dates; 2 quarantined records lack clean dates.
- **Amendment Relations Identified**:
  - `replace`: 2 provisions (e.g., Section 26 of BLA 2006 replaced by BLAA 2013).
  - `amend`: 3 provisions.
  - `none`: 12 provisions.
  - `unknown`: 2 provisions (quarantined).
- **Verified Coverage Status**: **0.00%**. All active provisions are classified as `evidence_type = "unknown", review_status = "pending"`.

---

## 6. What Improved
- **Section Integrity**: Discrete statutory provisions prevent cross-section contamination of legal remedies and penalties.
- **Tamper Evidence**: Cryptographic SHA-256 hashes for raw fixtures, manifests, and processed outputs guarantee complete determinism and auditability across evaluation runs.
- **Automated Quarantine Gate**: Flawed OCR scans and non-Unicode text files are deterministically quarantined before reaching the index.

---

## 7. What Failed & Limitations
- **Corpus Density Ceiling**: 17 provisions represent a constrained development fixture. 15 of 30 benchmark test queries reference valid statutory sections (e.g., *Specific Relief Act 1877*, *Penal Code 1860*, or unindexed sections of *CRPA 2009*) absent from this fixture, imposing an empirical Recall@10 ceiling of **46.7%**.
- **Historical Law Verification**: In the absence of official commencement gazette dates, historical temporal queries cannot be verified and are deterministically flagged `uncertain`.

---

## 8. Epistemic Status & Unverified Claims
- **Comprehensive Consolidation**: Claims asserting that all historical amendments from 1972 through 2026 are fully consolidated into these texts are **unverified**.
- **Official Legal Authority**: These sample fixtures serve evaluation purposes only and cannot be cited as authoritative government gazette publications in a court of law.
