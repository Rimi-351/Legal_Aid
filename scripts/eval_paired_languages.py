"""
scripts/eval_paired_languages.py
---------------------------------
Evaluates retrieval and decision consistency across parallel multilingual queries
(Bengali Unicode, Banglish transliteration, and English).

Features & Gates:
1. Compares retrieved results by (act_id, section_id) rather than raw record_id strings,
   ensuring cross-language alignment across numeral and script schemes.
2. Identifies and isolates scenarios where the target provision (act, section) actually
   exists in the active corpus (4 out of 12 scenarios).
3. Primary macro overlap metrics are reported specifically over these grounded scenarios.
4. Decision consistency evaluation displaying per-language top retrieval scores against
   the pipeline abstention threshold (T=30.0).
5. Corpus size annotation printed beside latency and RAM measurements: (N=17 provisions).
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import csv
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.bm25 import BM25Index
from src.rag.config import settings, check_retrieval_abstention
from src.pipeline import get_pipeline_retriever, ask
from src.evaluation.logger import get_process_memory_mb

BENGALI_TO_ASCII_TRANS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def normalize_numeral_string(s: str) -> str:
    """Converts Bengali numerals to ASCII digits and strips whitespace."""
    if not s:
        return ""
    return s.strip().translate(BENGALI_TO_ASCII_TRANS)


def extract_act_section(hit_or_pid: Any) -> Tuple[str, str]:
    """
    Extracts a canonical (act_id, section_id) tuple from a SearchResult, dict, or provision_id string.
    Normalizes all section numerals to ASCII digits and Act codes to uppercase ASCII.
    Examples:
      'BLA2006_S২৬' -> ('BLA2006', '26')
      'bla2006_s26' -> ('BLA2006', '26')
      'PRCA1991_S১৮' -> ('PRCA1991', '18')
      'CA1872_S11'  -> ('CA1872', '11')
    """
    if hasattr(hit_or_pid, "provision_id"):
        raw_pid = hit_or_pid.provision_id
    elif isinstance(hit_or_pid, dict):
        raw_pid = hit_or_pid.get("provision_id") or hit_or_pid.get("record_id", "")
    else:
        raw_pid = str(hit_or_pid)

    norm = raw_pid.strip().translate(BENGALI_TO_ASCII_TRANS).upper()
    if "_S" in norm:
        parts = norm.split("_S", 1)
        return (parts[0].strip(), parts[1].strip())
    elif "_SECTION" in norm:
        parts = norm.split("_SECTION", 1)
        return (parts[0].strip(), parts[1].strip())
    return (norm, "")


def compute_jaccard_act_section(
    set_a: Set[Tuple[str, str]],
    set_b: Set[Tuple[str, str]]
) -> float:
    """Computes Jaccard similarity between two sets of (act_id, section_id) tuples."""
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return round(intersection / union, 4) if union > 0 else 0.0


def identify_grounded_scenarios(
    csv_path: Path = Path("eval/paired_language_tests.csv"),
    provisions_path: Path = Path("data/processed/provisions.jsonl")
) -> Dict[str, Dict[str, Any]]:
    """
    Identifies paired scenarios whose target (act_id, section_id) exists in the active corpus.
    Returns dict mapping scenario_id -> {expected_act_section, present_in_corpus, row_data}.
    """
    # 1. Load active corpus (act, section) tuples
    active_corpus_act_sections: Set[Tuple[str, str]] = set()
    if provisions_path.exists():
        with open(provisions_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    if not p.get("is_quarantined", False):
                        active_corpus_act_sections.add(extract_act_section(p.get("provision_id", "")))

    # 2. Inspect scenarios in CSV
    grounded: Dict[str, Dict[str, Any]] = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["scenario_id"]
                exp = row.get("expected_provisions", "").strip()
                if not exp or exp.upper() == "NONE":
                    continue
                target_pair = extract_act_section(exp)
                is_present = target_pair in active_corpus_act_sections
                if is_present and sid not in grounded:
                    grounded[sid] = {
                        "scenario_id": sid,
                        "expected_provision": exp,
                        "target_act_section": target_pair,
                        "domain": row.get("domain", ""),
                    }
    return grounded


def eval_paired_languages(
    csv_path: Path = Path("eval/paired_language_tests.csv"),
    provisions_path: Path = Path("data/processed/provisions.jsonl"),
    run_llm: bool = False,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Runs evaluation over paired multilingual test scenarios with canonical (act, section) overlap."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Test file not found: {csv_path}")

    # Load active corpus to determine corpus size and target existence
    corpus_act_sections: Set[Tuple[str, str]] = set()
    corpus_size = 0
    if provisions_path.exists():
        with open(provisions_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    if not p.get("is_quarantined", False):
                        corpus_size += 1
                        corpus_act_sections.add(extract_act_section(p.get("provision_id", "")))

    grounded_scenarios_map = identify_grounded_scenarios(csv_path, provisions_path)
    n_grounded = len(grounded_scenarios_map)

    # Read and group scenarios
    scenarios: Dict[str, Dict[str, Dict[str, Any]]] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["scenario_id"]
            lang = row["language"].strip().lower()
            if sid not in scenarios:
                scenarios[sid] = {}
            scenarios[sid][lang] = row

    retriever, _ = get_pipeline_retriever()
    abstain_threshold = settings.abstain_threshold  # Default T = 30.0

    all_results: List[Dict[str, Any]] = []
    grounded_results: List[Dict[str, Any]] = []

    total_scenarios = len(scenarios)
    consistent_decisions_count = 0

    print("\n" + "=" * 115)
    print("  Multilingual Paired Retrieval Consistency by (Act ID, Section ID)")
    print(f"  Target in corpus: {n_grounded}/{total_scenarios} scenarios ({n_grounded/total_scenarios*100:.1f}%) | Corpus Size: (N={corpus_size} provisions)")
    print(f"  Decision threshold: T={abstain_threshold:.1f}")
    print("=" * 115)
    print(f"{'Scenario ID':<13} | {'In Corpus':<9} | {'BN-EN':<7} | {'BN-BG':<7} | {'BG-EN':<7} | {'Mean':<6} | {'Top Scores (BN / BG / EN)':<30} | {'Decision Consistent'}")
    print("-" * 115)

    for sid, lang_dict in scenarios.items():
        retrieved_act_sections: Dict[str, Set[Tuple[str, str]]] = {}
        top_scores: Dict[str, float] = {}
        abstain_decisions: Dict[str, bool] = {}

        # Expected target provision check
        sample_row = next(iter(lang_dict.values()))
        exp_target_raw = sample_row.get("expected_provisions", "").strip()
        exp_target_pair = extract_act_section(exp_target_raw) if exp_target_raw and exp_target_raw.upper() != "NONE" else ("", "")
        target_in_corpus = (exp_target_pair in corpus_act_sections) and (exp_target_pair != ("", ""))

        for lang in ("bn", "banglish", "en"):
            item = lang_dict.get(lang)
            if not item:
                retrieved_act_sections[lang] = set()
                top_scores[lang] = 0.0
                abstain_decisions[lang] = True
                continue

            query = item["query_text"]

            if run_llm:
                res = ask(query, lang_override=lang, mode="llm_validated")
                hits = res.retrieved[:top_k]
                pairs = {extract_act_section(r["provision_id"]) for r in hits}
                retrieved_act_sections[lang] = pairs
                top_scores[lang] = float(hits[0].get("score", 0.0)) if hits else 0.0
                abstain_decisions[lang] = res.abstained
            else:
                hits = retriever.search(query, top_k=top_k)
                pairs = {extract_act_section(h) for h in hits}
                retrieved_act_sections[lang] = pairs
                top_score = float(hits[0].score) if hits else 0.0
                top_scores[lang] = round(top_score, 2)

                # Format evidence for abstention check
                ev = [
                    {
                        "record_id": h.provision_id,
                        "provision_id": h.provision_id,
                        "act_title": h.act_title,
                        "section_id": h.section_number,
                        "section_number": h.section_number,
                        "score": h.score,
                    }
                    for h in hits
                ]
                should_abstain, _ = check_retrieval_abstention(query, ev, threshold=abstain_threshold)
                abstain_decisions[lang] = should_abstain

        # Overlap across language pairs by (act_id, section_id)
        set_bn = retrieved_act_sections.get("bn", set())
        set_bg = retrieved_act_sections.get("banglish", set())
        set_en = retrieved_act_sections.get("en", set())

        j_bn_en = compute_jaccard_act_section(set_bn, set_en)
        j_bn_bg = compute_jaccard_act_section(set_bn, set_bg)
        j_bg_en = compute_jaccard_act_section(set_bg, set_en)
        mean_jaccard = round((j_bn_en + j_bn_bg + j_bg_en) / 3.0, 4)

        # Decision consistency check
        dec_bn = abstain_decisions.get("bn")
        dec_bg = abstain_decisions.get("banglish")
        dec_en = abstain_decisions.get("en")
        is_consistent = (dec_bn == dec_bg == dec_en)
        if is_consistent:
            consistent_decisions_count += 1

        s_bn = top_scores.get("bn", 0.0)
        s_bg = top_scores.get("banglish", 0.0)
        s_en = top_scores.get("en", 0.0)
        score_str = f"BN:{s_bn:.1f} / BG:{s_bg:.1f} / EN:{s_en:.1f}"

        status_str = f"YES (Abstain={dec_en})" if is_consistent else f"NO (BN:{dec_bn}, BG:{dec_bg}, EN:{dec_en})"
        in_corpus_str = "YES" if target_in_corpus else "NO"

        print(f"{sid:<13} | {in_corpus_str:<9} | {j_bn_en:<7.2f} | {j_bn_bg:<7.2f} | {j_bg_en:<7.2f} | {mean_jaccard:<6.2f} | {score_str:<30} | {status_str}")

        scenario_record = {
            "scenario_id": sid,
            "target_in_corpus": target_in_corpus,
            "expected_provision": exp_target_raw,
            "target_act_section": list(exp_target_pair),
            "jaccard_bn_en": j_bn_en,
            "jaccard_bn_banglish": j_bn_bg,
            "jaccard_banglish_en": j_bg_en,
            "mean_jaccard": mean_jaccard,
            "top_scores": {"bn": s_bn, "banglish": s_bg, "en": s_en},
            "decision_consistent": is_consistent,
            "abstain_decisions": abstain_decisions,
        }
        all_results.append(scenario_record)
        if target_in_corpus:
            grounded_results.append(scenario_record)

    # Compute Macro metrics over Grounded Scenarios (4 scenarios)
    if n_grounded > 0:
        gr_bn_en = round(sum(s["jaccard_bn_en"] for s in grounded_results) / n_grounded, 4)
        gr_bn_bg = round(sum(s["jaccard_bn_banglish"] for s in grounded_results) / n_grounded, 4)
        gr_bg_en = round(sum(s["jaccard_banglish_en"] for s in grounded_results) / n_grounded, 4)
        gr_overall = round((gr_bn_en + gr_bn_bg + gr_bg_en) / 3.0, 4)
        gr_consistent = sum(1 for s in grounded_results if s["decision_consistent"])
        gr_consistency_rate = round((gr_consistent / n_grounded) * 100.0, 2)
    else:
        gr_bn_en = gr_bn_bg = gr_bg_en = gr_overall = gr_consistency_rate = 0.0
        gr_consistent = 0

    # Compute Macro metrics over All Scenarios (12 scenarios)
    all_bn_en = round(sum(s["jaccard_bn_en"] for s in all_results) / total_scenarios, 4) if total_scenarios > 0 else 0.0
    all_bn_bg = round(sum(s["jaccard_bn_banglish"] for s in all_results) / total_scenarios, 4) if total_scenarios > 0 else 0.0
    all_bg_en = round(sum(s["jaccard_banglish_en"] for s in all_results) / total_scenarios, 4) if total_scenarios > 0 else 0.0
    all_overall = round((all_bn_en + all_bn_bg + all_bg_en) / 3.0, 4)
    all_consistency_rate = round((consistent_decisions_count / total_scenarios) * 100.0, 2) if total_scenarios > 0 else 0.0

    peak_rss = get_process_memory_mb()

    print("-" * 115)
    print(f"Summary Over Grounded Scenarios (Target Exists in Corpus, n={n_grounded} of {total_scenarios}):")
    print(f"  - Grounded Scenarios         : {list(grounded_scenarios_map.keys())}")
    print(f"  - Grounded Mean BN-EN Overlap: {gr_bn_en:.4f}")
    print(f"  - Grounded Mean BN-BG Overlap: {gr_bn_bg:.4f}")
    print(f"  - Grounded Mean BG-EN Overlap: {gr_bg_en:.4f}")
    print(f"  - Grounded Macro Overlap     : {gr_overall:.4f}")
    print(f"  - Decision Consistency Rate  : {gr_consistency_rate:.2f}% ({gr_consistent}/{n_grounded}) (Threshold T={abstain_threshold:.1f})")
    print(f"  - Process Memory Footprint   : {peak_rss:.1f} MB (N={corpus_size} provisions)")
    print("-" * 115)
    print(f"Supplementary: Full Unfiltered Set (n={total_scenarios}):")
    print(f"  - Full Mean BN-EN Overlap    : {all_bn_en:.4f}")
    print(f"  - Full Mean BN-BG Overlap    : {all_bn_bg:.4f}")
    print(f"  - Full Mean BG-EN Overlap    : {all_bg_en:.4f}")
    print(f"  - Full Overall Macro Overlap : {all_overall:.4f}")
    print(f"  - Full Decision Consistency  : {all_consistency_rate:.2f}% ({consistent_decisions_count}/{total_scenarios})")
    print("=" * 115 + "\n")

    return {
        "metadata": {
            "corpus_size": corpus_size,
            "corpus_size_annotation": f"(N={corpus_size} provisions)",
            "total_scenarios": total_scenarios,
            "grounded_scenarios_count": n_grounded,
            "grounded_scenario_ids": list(grounded_scenarios_map.keys()),
            "abstain_threshold": abstain_threshold,
            "peak_rss_mb": peak_rss,
        },
        "grounded_metrics": {
            "count": n_grounded,
            "mean_bn_en_overlap": gr_bn_en,
            "mean_bn_banglish_overlap": gr_bn_bg,
            "mean_banglish_en_overlap": gr_bg_en,
            "overall_macro_overlap": gr_overall,
            "decision_consistency_rate_pct": gr_consistency_rate,
            "consistent_count": gr_consistent,
        },
        "all_metrics": {
            "count": total_scenarios,
            "mean_bn_en_overlap": all_bn_en,
            "mean_bn_banglish_overlap": all_bn_bg,
            "mean_banglish_en_overlap": all_bg_en,
            "overall_macro_overlap": all_overall,
            "decision_consistency_rate_pct": all_consistency_rate,
            "consistent_count": consistent_decisions_count,
        },
        "scenarios": all_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate paired multilingual retrieval consistency by (Act, Section).")
    parser.add_argument("--csv", type=Path, default=Path("eval/paired_language_tests.csv"), help="Path to paired tests CSV")
    parser.add_argument("--provisions", type=Path, default=Path("data/processed/provisions.jsonl"), help="Path to provisions JSONL")
    parser.add_argument("--run-llm", action="store_true", help="Run full LLM generation instead of retrieval only")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved provisions to evaluate")
    args = parser.parse_args()

    eval_paired_languages(csv_path=args.csv, provisions_path=args.provisions, run_llm=args.run_llm, top_k=args.top_k)


if __name__ == "__main__":
    main()
