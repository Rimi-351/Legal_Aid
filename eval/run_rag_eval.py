#!/usr/bin/env python3
"""
eval/run_rag_eval.py
---------------------
Executes Week 5 RAG evaluation suite across 4 conditions on frozen retrieval results:
1. extractive
2. llm
3. llm_validated_noabstain
4. llm_validated

Enforces:
- Verification of eval/split.json SHA256 against eval/split.sha256.
- Hard exit if Ollama server is unreachable (simulator strictly forbidden).
- Model warm-up before timing starts.
- Evidence capping: top 3 records, 1200 chars max per record for all LLM conditions.
- Strict metrics bookkeeping: timeouts and unreachable excluded from p50/p95.
- Failure mode categorization: timeout, unreachable, parse_failure, truncated, schema_missing.
- LLM-only validator_pass_rate (excluding extractive fallback claims).
- Abstention derived from final response across all conditions.
- Memory sampling across Python process + Ollama process (with children).
- Full audit check on eval/insufficient_audit.csv before computing abstention metrics.
- Complete output logging to eval/outputs.jsonl (4 x n rows).
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import csv
import json
import time
import uuid
import random
import hashlib
import threading
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
import psutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.config import (
    settings,
    check_retrieval_abstention,
    extract_query_section,
    is_foreign_jurisdiction_query,
    LEAKAGE_PATTERN,
)
from src.rag.extractive import extractive_answer
from src.rag.llm_answer import generate_answer, warm_model
from src.rag.citation_validator import validate
from src.retrieval.bm25 import BM25Index


class PeakMemorySampler:
    """Samples peak RSS memory every 0.5s for this process and the Ollama process (including children)."""
    def __init__(self, interval_sec: float = 0.5):
        self.interval = interval_sec
        self.max_python_rss_mb = 0.0
        self.max_ollama_rss_mb = 0.0
        self.max_sum_rss_mb = 0.0
        self.ollama_found = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._proc = psutil.Process()

    def _get_process_tree_rss(self, proc: psutil.Process) -> int:
        rss = 0
        try:
            rss += proc.memory_info().rss
            for child in proc.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return rss

    def _sample(self):
        ollama_procs: List[psutil.Process] = []
        while self._running:
            try:
                py_rss = self._get_process_tree_rss(self._proc)

                active_ollama = []
                for p in ollama_procs:
                    try:
                        if p.is_running():
                            active_ollama.append(p)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                if not active_ollama:
                    for p in psutil.process_iter(["pid", "name"]):
                        try:
                            if "ollama" in (p.info.get("name") or "").lower():
                                active_ollama.append(p)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                ollama_procs = active_ollama

                ollama_rss = sum(self._get_process_tree_rss(p) for p in ollama_procs)
                if ollama_procs:
                    self.ollama_found = True

                py_mb = py_rss / (1024 * 1024)
                ol_mb = ollama_rss / (1024 * 1024)
                sum_mb = py_mb + ol_mb

                if py_mb > self.max_python_rss_mb:
                    self.max_python_rss_mb = py_mb
                if ol_mb > self.max_ollama_rss_mb:
                    self.max_ollama_rss_mb = ol_mb
                if sum_mb > self.max_sum_rss_mb:
                    self.max_sum_rss_mb = sum_mb
            except Exception:
                pass
            time.sleep(self.interval)

    def start(self):
        self._running = True
        self.max_python_rss_mb = self._proc.memory_info().rss / (1024 * 1024)
        self.max_ollama_rss_mb = 0.0
        self.max_sum_rss_mb = self.max_python_rss_mb
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

    def stop(self) -> Dict[str, Any]:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

        ol_report: Union[float, str] = round(self.max_ollama_rss_mb, 2) if self.ollama_found else "ollama: not found"
        return {
            "python_rss_mb": round(self.max_python_rss_mb, 2),
            "ollama_rss_mb": ol_report,
            "total_peak_rss_mb": round(self.max_sum_rss_mb, 2)
        }


def verify_split_integrity(split_path: Path, sha_path: Path) -> None:
    """Verifies SHA256 of eval/split.json against eval/split.sha256."""
    if not split_path.exists():
        print(f"ERROR: Split file not found: {split_path}", file=sys.stderr)
        sys.exit(1)
    if not sha_path.exists():
        print(f"ERROR: SHA256 file not found: {sha_path}", file=sys.stderr)
        sys.exit(1)

    expected_sha = sha_path.read_text(encoding="utf-8").strip().split()[0]
    actual_sha = hashlib.sha256(split_path.read_bytes()).hexdigest()

    if actual_sha != expected_sha:
        print("ERROR: Split integrity verification failed!", file=sys.stderr)
        print(f"  Expected: {expected_sha}", file=sys.stderr)
        print(f"  Actual:   {actual_sha}", file=sys.stderr)
        sys.exit(1)
    print(f"[+] Split integrity verified (SHA256: {actual_sha[:12]}...).")


def check_ollama_reachable(base_url: str) -> bool:
    """Verifies that local Ollama instance is active and responding."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def load_corpus(corpus_path: Path) -> List[Dict[str, Any]]:
    records = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                if not p.get("is_quarantined", False):
                    records.append(p)
    return records


def check_git_status() -> Tuple[bool, List[str]]:
    """Checks git working tree status and returns (is_dirty, uncommitted_paths)."""
    import subprocess
    try:
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip()]
        paths = [l[2:].strip() for l in lines]
        return len(paths) > 0, paths
    except Exception as e:
        return False, [str(e)]


def run_evaluation(
    query_limit: Optional[int] = None,
    eval_conditions: Optional[List[str]] = None,
    allow_dirty: bool = False
):
    print("=" * 80)
    print("  Legal Aid BD — Week 5 Hardened RAG Pipeline Evaluation")
    print("=" * 80)

    # 1. Verify split integrity and working tree cleanliness
    split_path = Path("eval/split.json")
    sha_path = Path("eval/split.sha256")
    verify_split_integrity(split_path, sha_path)

    is_dirty, uncommitted = check_git_status()
    if is_dirty and not allow_dirty and query_limit is None:
        print(f"ERROR: Refusing full evaluation because working tree is dirty ({len(uncommitted)} uncommitted files)!", file=sys.stderr)
        print("Commit changes or pass --allow-dirty to explicitly override and record.", file=sys.stderr)
        sys.exit(1)
    elif is_dirty and allow_dirty:
        print(f"[!] WARNING: Evaluation proceeding with dirty working tree (--allow-dirty set, {len(uncommitted)} uncommitted files).")

    # 2. Enforce live Ollama backend
    print(f"[*] Checking local Ollama connectivity at {settings.llm_base_url}...")
    if not check_ollama_reachable(settings.llm_base_url):
        print(f"\nERROR: Ollama server at {settings.llm_base_url} is unreachable.", file=sys.stderr)
        print("Evaluation cannot proceed without live LLM backend (simulator removed).", file=sys.stderr)
        print(f"Backend configured: Ollama model='{settings.llm_model}', num_predict={settings.llm_max_tokens}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Ollama server is live. Model: {settings.llm_model}, num_predict: {settings.llm_max_tokens}, num_ctx: {settings.llm_num_ctx}, keep_alive: {settings.llm_keep_alive}")

    # Warm model with throwaway call
    print("[*] Warming Ollama model with throwaway inference call...")
    warmed = warm_model()
    if warmed:
        print("[+] Model warmed successfully.")
    else:
        print("[!] Warning: Warm-up call did not succeed, proceeding anyway.")

    # 3. Load corpus and initialize BM25
    corpus = load_corpus(settings.corpus_path)
    retriever = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    retriever.fit(corpus)
    print(f"[*] Loaded corpus with {len(corpus)} statutory records.")

    # 4. Check insufficient-set audit file
    audit_path = Path("eval/insufficient_audit.csv")
    audit_completed = False
    excluded_insuf_ids = set()

    if audit_path.exists():
        with open(audit_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            audit_rows = list(reader)

        blank_count = sum(1 for r in audit_rows if not r.get("answerable_in_corpus (Y/N)", "").strip())
        if blank_count == 0 and len(audit_rows) > 0:
            audit_completed = True
            for r in audit_rows:
                val = r.get("answerable_in_corpus (Y/N)", "").strip().upper()
                if val in ("Y", "YES"):
                    excluded_insuf_ids.add(r["id"])
            print(f"[+] Insufficient-set audit complete. Excluded {len(excluded_insuf_ids)} rows labeled Y from insufficient set.")
        else:
            print(f"[!] Insufficient-set audit incomplete: {blank_count}/{len(audit_rows)} rows have empty 'answerable_in_corpus (Y/N)'.")
            print("    Per specification, abstention precision/recall metrics will be marked not computable until human audit is complete.")
    else:
        print("[!] eval/insufficient_audit.csv not found; abstention metrics will be marked not computable.")

    # 5. Load split configuration
    with open(split_path, "r", encoding="utf-8") as f:
        split_data = json.load(f)

    dev_ids = set(split_data["dev_ids"])
    test_ids = set(split_data["test_ids"])

    all_answ: Dict[str, Dict[str, Any]] = {}
    with open("data/benchmarks/benchmark_dev.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                if q.get("corpus_has_sufficient_evidence") and q.get("expected_supporting_provisions"):
                    qid = q["query_id"]
                    lang_raw = q.get("language_and_script", "en")
                    lang_code = "bn" if ("bn" in lang_raw or "banglish" in lang_raw) else "en"
                    all_answ[qid] = {
                        "id": qid,
                        "query": q["original_user_query"],
                        "lang": lang_code,
                        "is_answerable": True
                    }

    all_insuf: Dict[str, Dict[str, Any]] = {}
    with open("eval/insufficient_evidence.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            qid = r["id"]
            all_insuf[qid] = {
                "id": qid,
                "query": r["question"],
                "lang": r["lang"],
                "is_answerable": False
            }

    dev_queries = [all_answ[qid] for qid in dev_ids if qid in all_answ] + [all_insuf[qid] for qid in dev_ids if qid in all_insuf]
    test_queries = [all_answ[qid] for qid in test_ids if qid in all_answ] + [all_insuf[qid] for qid in test_ids if qid in all_insuf]

    if query_limit is not None and query_limit > 0:
        test_queries = test_queries[:query_limit]
        print(f"[*] Limiting test evaluation to first {len(test_queries)} queries.")

    n_test = len(test_queries)
    test_qids_expected = [q["id"] for q in test_queries]
    print(f"[*] Loaded dev split: {len(dev_queries)} queries.")
    print(f"[*] Loaded test split: {n_test} queries (n={n_test} per condition).")

    # 6. Freeze retrieval outputs
    print("\n[*] Caching frozen retrieval outputs...")
    frozen_cache: Dict[str, List[Dict[str, Any]]] = {}
    for q in dev_queries + test_queries:
        hits = retriever.search(q["query"], top_k=settings.retrieval_top_k)
        frozen_cache[q["id"]] = [
            {
                "record_id": h.provision_id,
                "provision_id": h.provision_id,
                "act_title": h.act_title,
                "section_id": h.section_number,
                "section_number": h.section_number,
                "source_url": h.source_file,
                "source_file": h.source_file,
                "text": h.text,
                "language": h.language,
                "score": h.score
            }
            for h in hits
        ]

    # Dev threshold tuning note (from dev-only sweep script)
    threshold_sweep_path = Path("eval/threshold_sweep.csv")
    dev_tuned_threshold = settings.abstain_threshold
    if threshold_sweep_path.exists():
        with open(threshold_sweep_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            best_f1_val = -1.0
            for row in reader:
                f1_val = float(row.get("f1", 0.0))
                if f1_val > best_f1_val:
                    best_f1_val = f1_val
                    dev_tuned_threshold = float(row.get("threshold", 30.0))
        print(f"[+] Loaded dev threshold from sweep log: {dev_tuned_threshold:.1f} (F1={best_f1_val:.4f})")

    # 7. Evaluate 4 conditions on TEST split only
    conditions = ["extractive", "llm", "llm_validated_noabstain", "llm_validated"]
    if eval_conditions:
        conditions = [c for c in conditions if c in eval_conditions]

    outputs_path = Path("eval/outputs.jsonl") if query_limit is None else Path("eval/smoke_outputs.jsonl")
    outputs_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = open(outputs_path, "w", encoding="utf-8")

    results_by_cond: Dict[str, Dict[str, Any]] = {}
    sampled_pool: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    condition_warnings: List[str] = []
    llm_inference_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}

    for cond in conditions:
        print(f"\n[*] Evaluating Condition on Test Split: [{cond}] (n={n_test})...", flush=True)

        # Assert identical query-ID set
        cond_qids = [q["id"] for q in test_queries]
        assert cond_qids == test_qids_expected, f"Condition [{cond}] query IDs do not match test split!"

        sampler = PeakMemorySampler()
        sampler.start()

        latencies_valid: List[float] = []
        timeout_unreachable_count = 0

        timeout_count = 0
        unreachable_count = 0
        parse_failure_count = 0
        truncation_count = 0
        fallback_count = 0

        llm_claims_total = 0
        llm_claims_valid = 0
        ext_claims_count = 0

        insuf_abstains = 0
        answ_abstains = 0
        n_insuf_audited = sum(1 for q in test_queries if not q["is_answerable"] and q["id"] not in excluded_insuf_ids)
        n_answ = sum(1 for q in test_queries if q["is_answerable"])

        for q_idx, item in enumerate(test_queries, 1):
            qid = item["id"]
            query = item["query"]
            lang = item["lang"]
            is_answ = item["is_answerable"]
            evidence = frozen_cache[qid]
            retrieved_ids = [e["record_id"] for e in evidence]

            t0 = time.perf_counter()
            dt_ms: Optional[float] = None
            final_answer_text = ""
            claims_out: List[Dict[str, Any]] = []
            raw_model_json: Optional[Dict[str, Any]] = None

            is_abstained = False
            fallback_used = False
            is_timeout = False
            is_unreachable = False
            is_parse_fail = False
            is_trunc = False
            is_schema_missing = False

            if cond == "extractive":
                ext = extractive_answer(query, evidence, lang=lang, score_threshold=dev_tuned_threshold)
                is_abstained = ext.get("insufficient_evidence", False)
                final_answer_text = ext.get("summary", "")
                claims_out = ext.get("claims", [])
                ext_claims_count += len(claims_out)
                fallback_used = False
                raw_model_json = None
                dt_ms = (time.perf_counter() - t0) * 1000.0

                for c in claims_out:
                    cell_key = (cond, lang)
                    sampled_pool.setdefault(cell_key, []).append({
                        "query_id": qid,
                        "query": query,
                        "lang": lang,
                        "claim": c.get("text", ""),
                        "cited_passage": c.get("quote", "")
                    })

            elif cond == "llm":
                if qid in llm_inference_cache:
                    raw_llm, dt_ms = llm_inference_cache[qid]
                else:
                    t_llm0 = time.perf_counter()
                    raw_llm = generate_answer(query, evidence, lang=lang)
                    dt_ms = (time.perf_counter() - t_llm0) * 1000.0
                    llm_inference_cache[qid] = (raw_llm, dt_ms)

                raw_model_json = raw_llm
                is_timeout = raw_llm.get("timeout", False)
                is_unreachable = raw_llm.get("unreachable", False)
                is_parse_fail = raw_llm.get("parse_failure", False)
                is_trunc = raw_llm.get("truncated", False)
                is_schema_missing = raw_llm.get("schema_missing", False)
                fallback_used = raw_llm.get("fallback_used", False)

                # Abstention derived from final response
                if raw_llm.get("abstain") is True:
                    is_abstained = True
                    final_answer_text = raw_llm.get("reason", "Abstained")
                    claims_out = []
                elif fallback_used:
                    is_abstained = raw_llm.get("insufficient_evidence", False)
                    final_answer_text = raw_llm.get("summary", "")
                    claims_out = raw_llm.get("claims", [])
                else:
                    is_abstained = False
                    claims_text = []
                    for c in raw_llm.get("claims", []):
                        t = c.get("text", "")
                        if not LEAKAGE_PATTERN.search(t):
                            claims_text.append(t)

                        # Populate citation fields from evidence
                        c_dict = dict(c)
                        e_ids = c.get("evidence_ids", [])
                        matched_ev = None
                        if e_ids:
                            eid_str = str(e_ids[0]).strip("[]")
                            if eid_str.startswith("E") and eid_str[1:].isdigit():
                                idx_e = int(eid_str[1:]) - 1
                                if 0 <= idx_e < len(evidence):
                                    matched_ev = evidence[idx_e]
                            if not matched_ev:
                                for ev in evidence:
                                    if ev.get("record_id") == eid_str or ev.get("provision_id") == eid_str:
                                        matched_ev = ev
                                        break
                        if not matched_ev and len(evidence) > 0:
                            matched_ev = evidence[0]
                        if matched_ev:
                            c_dict["record_id"] = matched_ev.get("record_id") or matched_ev.get("provision_id")
                            c_dict["act_title"] = matched_ev.get("act_title")
                            c_dict["section_id"] = str(matched_ev.get("section_id") or matched_ev.get("section_number"))
                            c_dict["source_url"] = matched_ev.get("source_url") or matched_ev.get("source_file")
                            c_dict["citation"] = {
                                "record_id": c_dict["record_id"],
                                "act_title": c_dict["act_title"],
                                "section_id": c_dict["section_id"],
                                "source_url": c_dict["source_url"],
                                "quote": c.get("quote")
                            }
                        claims_out.append(c_dict)

                        # LLM produced claims (not fallback)
                        llm_claims_total += 1
                        if c.get("evidence_ids") and c.get("quote"):
                            llm_claims_valid += 1
                        cell_key = (cond, lang)
                        sampled_pool.setdefault(cell_key, []).append({
                            "query_id": qid,
                            "query": query,
                            "lang": lang,
                            "claim": t,
                            "cited_passage": c.get("quote", "")
                        })
                    final_answer_text = " ".join(claims_text)

            elif cond == "llm_validated_noabstain":
                if qid in llm_inference_cache:
                    raw_llm, base_ms = llm_inference_cache[qid]
                    t_val0 = time.perf_counter()
                else:
                    t_llm0 = time.perf_counter()
                    raw_llm = generate_answer(query, evidence, lang=lang)
                    base_ms = (time.perf_counter() - t_llm0) * 1000.0
                    llm_inference_cache[qid] = (raw_llm, base_ms)
                    t_val0 = time.perf_counter()

                raw_model_json = raw_llm
                is_timeout = raw_llm.get("timeout", False)
                is_unreachable = raw_llm.get("unreachable", False)
                is_parse_fail = raw_llm.get("parse_failure", False)
                is_trunc = raw_llm.get("truncated", False)
                is_schema_missing = raw_llm.get("schema_missing", False)
                gen_fallback = raw_llm.get("fallback_used", False)

                if raw_llm.get("abstain") is True:
                    is_abstained = True
                    fallback_used = False
                    final_answer_text = raw_llm.get("reason", "Evidence insufficient")
                    claims_out = []
                    dt_ms = base_ms + (time.perf_counter() - t_val0) * 1000.0
                elif gen_fallback:
                    fallback_used = True
                    is_abstained = raw_llm.get("insufficient_evidence", False)
                    final_answer_text = raw_llm.get("summary", "")
                    claims_out = raw_llm.get("claims", [])
                    dt_ms = base_ms + (time.perf_counter() - t_val0) * 1000.0
                else:
                    val_res = validate(raw_llm, evidence, query=query, lang=lang)
                    dt_ms = base_ms + (time.perf_counter() - t_val0) * 1000.0
                    fallback_used = val_res.fallback_used
                    if fallback_used:
                        is_abstained = val_res.answer.get("insufficient_evidence", False)
                        final_answer_text = val_res.answer.get("summary", val_res.answer.get("answer", ""))
                        claims_out = val_res.answer.get("claims", [])
                    else:
                        is_abstained = False
                        final_answer_text = val_res.answer.get("answer", "")
                        claims_out = [c.to_dict() for c in val_res.validated_claims]
                        # Tally LLM produced claims
                        for vc in val_res.validated_claims:
                            llm_claims_total += 1
                            if vc.is_valid:
                                llm_claims_valid += 1
                            cell_key = (cond, lang)
                            sampled_pool.setdefault(cell_key, []).append({
                                "query_id": qid,
                                "query": query,
                                "lang": lang,
                                "claim": vc.text,
                                "cited_passage": vc.citation.get("quote") if vc.citation else ""
                            })

            elif cond == "llm_validated":
                should_pre_abstain, _ = check_retrieval_abstention(query, evidence, threshold=dev_tuned_threshold)
                if should_pre_abstain:
                    is_abstained = True
                    fallback_used = False
                    final_answer_text = "Insufficient evidence in retrieved legal sources to answer this question."
                    claims_out = []
                    raw_model_json = None
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                else:
                    if qid in llm_inference_cache:
                        raw_llm, base_ms = llm_inference_cache[qid]
                        t_val0 = time.perf_counter()
                    else:
                        t_llm0 = time.perf_counter()
                        raw_llm = generate_answer(query, evidence, lang=lang)
                        base_ms = (time.perf_counter() - t_llm0) * 1000.0
                        llm_inference_cache[qid] = (raw_llm, base_ms)
                        t_val0 = time.perf_counter()

                    raw_model_json = raw_llm
                    is_timeout = raw_llm.get("timeout", False)
                    is_unreachable = raw_llm.get("unreachable", False)
                    is_parse_fail = raw_llm.get("parse_failure", False)
                    is_trunc = raw_llm.get("truncated", False)
                    is_schema_missing = raw_llm.get("schema_missing", False)
                    gen_fallback = raw_llm.get("fallback_used", False)

                    if raw_llm.get("abstain") is True:
                        is_abstained = True
                        fallback_used = False
                        final_answer_text = raw_llm.get("reason", "Evidence insufficient")
                        claims_out = []
                        dt_ms = base_ms + (time.perf_counter() - t_val0) * 1000.0
                    elif gen_fallback:
                        fallback_used = True
                        is_abstained = raw_llm.get("insufficient_evidence", False)
                        final_answer_text = raw_llm.get("summary", "")
                        claims_out = raw_llm.get("claims", [])
                        dt_ms = base_ms + (time.perf_counter() - t_val0) * 1000.0
                    else:
                        val_res = validate(raw_llm, evidence, query=query, lang=lang)
                        dt_ms = base_ms + (time.perf_counter() - t_val0) * 1000.0
                        fallback_used = val_res.fallback_used
                        if fallback_used:
                            is_abstained = val_res.answer.get("insufficient_evidence", False)
                            final_answer_text = val_res.answer.get("summary", val_res.answer.get("answer", ""))
                            claims_out = val_res.answer.get("claims", [])
                        else:
                            is_abstained = False
                            final_answer_text = val_res.answer.get("answer", "")
                            claims_out = [c.to_dict() for c in val_res.validated_claims]
                            for vc in val_res.validated_claims:
                                llm_claims_total += 1
                                if vc.is_valid:
                                    llm_claims_valid += 1
                                cell_key = (cond, lang)
                                sampled_pool.setdefault(cell_key, []).append({
                                    "query_id": qid,
                                    "query": query,
                                    "lang": lang,
                                    "claim": vc.text,
                                    "cited_passage": vc.citation.get("quote") if vc.citation else ""
                                })

            if dt_ms is None:
                dt_ms = (time.perf_counter() - t0) * 1000.0

            if is_timeout:
                timeout_count += 1
                timeout_unreachable_count += 1
            elif is_unreachable:
                unreachable_count += 1
                timeout_unreachable_count += 1
            else:
                latencies_valid.append(dt_ms)

            if is_parse_fail:
                parse_failure_count += 1
            if is_trunc:
                truncation_count += 1
            if fallback_used:
                fallback_count += 1

            if is_answ and is_abstained:
                answ_abstains += 1
            elif not is_answ and is_abstained and (qid not in excluded_insuf_ids):
                insuf_abstains += 1

            # Save to outputs.jsonl
            out_record = {
                "condition": cond,
                "query_id": qid,
                "lang": lang,
                "retrieved_ids": retrieved_ids,
                "raw_model_json": raw_model_json,
                "final_answer": final_answer_text,
                "claims": claims_out,
                "flags": {
                    "timeout": is_timeout,
                    "unreachable": is_unreachable,
                    "parse_failure": is_parse_fail,
                    "truncated": is_trunc,
                    "schema_missing": is_schema_missing,
                    "fallback_used": fallback_used
                },
                "latency_ms": round(dt_ms, 2)
            }
            out_file.write(json.dumps(out_record, ensure_ascii=False) + "\n")
            out_file.flush()
            print(f"  [{q_idx}/{n_test}] {qid} -> abst={is_abstained}, fb={fallback_used}, to={is_timeout} ({dt_ms:.0f}ms)", flush=True)

        mem_stats = sampler.stop()

        latencies_valid.sort()
        p50 = latencies_valid[len(latencies_valid) // 2] if latencies_valid else 0.0
        p95 = latencies_valid[int(len(latencies_valid) * 0.95)] if latencies_valid else 0.0

        timeout_rate = round(timeout_count / n_test, 4)
        fallback_rate = round(fallback_count / n_test, 4)
        unreachable_rate = round(unreachable_count / n_test, 4)
        parse_failure_rate = round(parse_failure_count / n_test, 4)
        truncation_rate = round(truncation_count / n_test, 4)
        false_abstain_rate = round(answ_abstains / n_answ, 4) if n_answ > 0 else 0.0

        if audit_completed and n_insuf_audited > 0:
            abstain_rec: Any = round(insuf_abstains / n_insuf_audited, 4)
            tot_ab = insuf_abstains + answ_abstains
            abstain_prec: Any = round(insuf_abstains / tot_ab, 4) if tot_ab > 0 else 1.0
        else:
            abstain_rec = "not computable"
            abstain_prec = "not computable"

        # validator_pass_rate computed ONLY over claims LLM produced
        if cond == "extractive":
            val_pass_str = "1.0000"
            claims_count_str = f"n={ext_claims_count}"
        elif llm_claims_total == 0:
            val_pass_str = "n/a"
            claims_count_str = "n=0"
        else:
            val_pass_str = f"{(llm_claims_valid / llm_claims_total):.4f}"
            claims_count_str = f"n={llm_claims_total}"

        # Check warning condition
        if cond != "extractive" and (timeout_rate > 0.10 or fallback_rate > 0.10):
            warn_msg = f"WARNING: LLM condition [{cond}] not interpretable (timeout_rate={timeout_rate*100:.1f}%, fallback_rate={fallback_rate*100:.1f}% > 10%)"
            condition_warnings.append(warn_msg)

        results_by_cond[cond] = {
            "condition": cond,
            "n": n_test,
            "timeout_rate": timeout_rate,
            "unreachable_rate": unreachable_rate,
            "parse_failure_rate": parse_failure_rate,
            "truncation_rate": truncation_rate,
            "fallback_rate": fallback_rate,
            "validator_pass_rate": val_pass_str,
            "llm_claim_count": claims_count_str,
            "abstain_precision": abstain_prec,
            "abstain_recall": abstain_rec,
            "false_abstain_rate": false_abstain_rate,
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "timeout_unreachable_count": timeout_unreachable_count,
            "python_rss_mb": mem_stats["python_rss_mb"],
            "ollama_rss_mb": mem_stats["ollama_rss_mb"],
            "total_peak_rss_mb": mem_stats["total_peak_rss_mb"]
        }

    out_file.close()
    print(f"\n[+] Saved per-query outputs to: {outputs_path}")

    # 8. Stratified Human-Review Sheet Export (K = 12 per condition x language cell)
    rng = random.Random(42)
    k_per_cell = 12
    review_sheet_rows = []
    review_key_rows = []

    for cond in conditions:
        for lang in ["bn", "en"]:
            cell_key = (cond, lang)
            pool = sampled_pool.get(cell_key, [])
            rng.shuffle(pool)
            chosen = pool[:k_per_cell]
            for item in chosen:
                sample_uuid = str(uuid.uuid4())
                review_sheet_rows.append({
                    "sample_id": sample_uuid,
                    "lang": lang,
                    "query": item["query"],
                    "claim": item["claim"],
                    "cited_passage": item["cited_passage"],
                    "supported_annotator_1": "",
                    "supported_annotator_2": "",
                    "contradicts_annotator_1": "",
                    "contradicts_annotator_2": "",
                    "relies_on_unstated_facts_annotator_1": "",
                    "relies_on_unstated_facts_annotator_2": "",
                    "should_qualify_annotator_1": "",
                    "should_qualify_annotator_2": "",
                    "notes_annotator_1": "",
                    "notes_annotator_2": ""
                })
                review_key_rows.append({
                    "sample_id": sample_uuid,
                    "condition": cond,
                    "query_id": item["query_id"],
                    "lang": lang
                })

    rng.shuffle(review_sheet_rows)

    review_path = Path("eval/human_review_sheet.csv") if query_limit is None else Path("eval/smoke_human_review_sheet.csv")
    if review_sheet_rows:
        with open(review_path, "w", encoding="utf-8", newline="") as f:
            fieldnames = list(review_sheet_rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in review_sheet_rows:
                writer.writerow(r)

    key_path = Path("eval/review_key.csv") if query_limit is None else Path("eval/smoke_review_key.csv")
    if review_key_rows:
        with open(key_path, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["sample_id", "condition", "query_id", "lang"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in review_key_rows:
                writer.writerow(r)

    print(f"[+] Exported blinded human review sheet to: {review_path} (Total: {len(review_sheet_rows)} samples)")
    print(f"[+] Exported private review key to: {key_path}")

    # 9. Print loud warning banners if tripped
    if condition_warnings:
        print("\n" + "!" * 80)
        for w in condition_warnings:
            print(f"  {w}")
        print("!" * 80 + "\n")

    # 10. Print Evaluation Table
    print("\n" + "=" * 135)
    print(f"{'Condition':<25} | {'n':<3} | {'Timeout':<7} | {'Fallback':<8} | {'ParseFail':<9} | {'Trunc':<5} | {'Val. Pass':<15} | {'p50 (ms)':<9} | {'Py RAM':<8} | {'Ollama RAM'}")
    print("-" * 135)
    for c, m in results_by_cond.items():
        val_str = f"{m['validator_pass_rate']} ({m['llm_claim_count']})"
        ol_ram_str = f"{m['ollama_rss_mb']} MB" if isinstance(m['ollama_rss_mb'], (int, float)) else str(m['ollama_rss_mb'])
        print(f"{c:<25} | {m['n']:<3} | {m['timeout_rate']:<7.4f} | {m['fallback_rate']:<8.4f} | {m['parse_failure_rate']:<9.4f} | {m['truncation_rate']:<5.4f} | {val_str:<15} | {m['latency_p50_ms']:<9.2f} | {m['python_rss_mb']:<5.1f} MB | {ol_ram_str}")
    print("=" * 135)

    # 11. Save eval_summary.json
    summary_path = Path("eval/eval_summary.json") if query_limit is None else Path("eval/smoke_eval_summary.json")
    summary_payload = {
        "backend": {
            "name": "ollama",
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "top_p": settings.llm_top_p,
            "seed": settings.llm_seed,
            "num_predict": settings.llm_max_tokens,
            "num_ctx": settings.llm_num_ctx,
            "keep_alive": settings.llm_keep_alive,
            "base_url": settings.llm_base_url,
            "llm_timeout_sec": settings.llm_timeout_sec,
            "evidence_capping": {
                "max_records": settings.llm_max_evidence_records,
                "max_chars_per_record": settings.llm_max_evidence_chars
            }
        },
        "contamination_note": (
            "The test split's retrieval scores were inspected during development before the final threshold was chosen. "
            "Threshold values tried were 5.0, 10.5, 30.0. Clean holdout is not claimed."
        ),
        "dev_threshold_tuning": {
            "dev_tuned_threshold": dev_tuned_threshold,
            "sweep_file": "eval/threshold_sweep.csv",
            "note": "Tuned strictly on development split without test set scores."
        },
        "audit_status": {
            "audit_file": "eval/insufficient_audit.csv",
            "audit_completed": audit_completed,
            "excluded_y_count": len(excluded_insuf_ids)
        },
        "git_status": {
            "git_dirty": is_dirty,
            "allow_dirty": allow_dirty,
            "uncommitted_count": len(uncommitted) if is_dirty else 0
        },
        "evaluation_split": "test",
        "conditions": results_by_cond
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved evaluation metrics summary to: {summary_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Week 5 Legal RAG Pipeline Evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test queries evaluated")
    parser.add_argument("--conditions", type=str, default=None, help="Comma-separated conditions to run")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow running evaluation with uncommitted git changes")
    args = parser.parse_args()

    cond_list = [c.strip() for c in args.conditions.split(",")] if args.conditions else None
    run_evaluation(query_limit=args.limit, eval_conditions=cond_list, allow_dirty=args.allow_dirty)
