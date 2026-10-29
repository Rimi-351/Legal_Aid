# Reproducibility Guide & Verification Protocol

**Tested from clean clone: NO (as of 2026-10-29)**
*(Development and integration verification were executed within the primary working repository; a separate isolated clean clone validation run has not yet been executed).*

## 1. Research Question
Can an independent researcher reproduce all retrieval benchmarks, citation validation tests, and multi-tenant security guarantees using exact terminal commands from a clean Git checkout without proprietary software licenses?

## 2. Hypotheses
1. **H1 (Full Determinism)**: Freezing seeds ($seed=42$), model temperatures ($T=0.0$), and cryptographic checksums ensures bitwise reproducible retrieval and evaluation metrics.
2. **H2 (Zero Silent Simulation)**: Eliminating mock simulators guarantees that benchmark failures and successes reflect genuine local execution.

## 3. Baselines
Standard unreproducible scripts relying on unpinned Hugging Face commits, floating random seeds, or live unversioned web scrapers.

## 4. What Was Tested
Complete end-to-end execution of the 8-week pipeline from ingestion to frozen test evaluation on Python 3.13 AMD64.

## 5. Sources Used
Corpus provisions (`data/processed/provisions.jsonl`), manifest digests (`data/manifests/processed_manifest.jsonl`), benchmark splits (`eval/split.json`), and freeze manifest (`eval/freeze_manifest.json`).

---

## 6. Exact Reproduction Commands (From Clean Checkout)

```bash
# 1. Clone repository and verify commit
git clone <repository_url> Legal_Aid
cd Legal_Aid
git checkout 5fee1efeef6bb93ff9c31b6aa5329ceb040c585a

# 2. Set up virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Pull required local LLM weights via Ollama
ollama pull qwen2.5:3b

# 4. Verify cryptographic split and freeze manifest integrity
python -c "import hashlib, pathlib; assert pathlib.Path('eval/split.sha256').read_text().strip().split()[0] == hashlib.sha256(pathlib.Path('eval/split.json').read_bytes()).hexdigest(), 'Split hash mismatch!'"
python scripts/run_frozen_eval.py --manifest eval/freeze_manifest.json

# 5. Run complete test suite (97 tests covering Weeks 1 to 7)
pytest -q

# 6. Run version auditing and generate eval/version_audit.csv
python scripts/audit_versions.py

# 7. Run paired multilingual retrieval consistency evaluation
python scripts/eval_paired_languages.py

# 8. Run unified pipeline query via CLI
python src/pipeline.py "What constitutes a valid contract under Section 10?" --mode extractive

# 9. Launch Streamlit UI on localhost (enforces 127.0.0.1)
streamlit run app/ui.py --server.address 127.0.0.1
```

---

## 7. What Improved
- 100% deterministic test suite execution (97/97 tests pass in ~32s).
- Zero reliance on external paid APIs or proprietary models.

## 8. What Failed
- Running Streamlit with `--server.address 0.0.0.0` is strictly refused by the host security guard unless the insecure environment variable is explicitly supplied.

## 9. Which Claims Are Unverified & Benchmark Publish-ability
> [!IMPORTANT]
> **Publish-ability & Legal Rights Notice**:
> The evaluation benchmark (`eval/split.json`, `eval/paired_language_tests.csv`) and research methodology are designed for academic and open-science dissemination under open-access research terms. However, statutory text reproduction is subject to Bangladesh legislative copyright and government public-domain gazette policies. The authors **do not assert redistribution rights** over government statutory source files. Researchers must acquire primary legal texts directly from the official web portal of the Ministry of Law, Justice and Parliamentary Affairs (Government of the People's Republic of Bangladesh).

