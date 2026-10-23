"""
scripts/eval_local_generation.py
--------------------------------
Evaluation script for Day 4: Local Legal Answer Generation vs Extractive Baseline.
Runs across 14 controlled benchmark cases evaluating:
- English statute -> Bangla explanation
- Bangla statute -> English explanation
- Two-provision synthesis
- Insufficient evidence abstention
- Citation grounding
- Bangla / Banglish consistency

Measures:
- Latency (sec)
- Generation throughput (tokens/sec)
- Process RAM (RSS)
- Rubric scores across 6 criteria (0-2 scale)
"""

import os
import sys
import time
import json
import psutil
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure UTF-8 stdout encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.generation.prompts import build_user_prompt, LEGAL_SYSTEM_PROMPT
from src.generation.extractive import ExtractiveBaselineGenerator
from src.generation.client import OllamaGenerationClient
from src.generation.rubric import GenerationRubricEvaluator


def load_provisions_map(jsonl_path: Path) -> Dict[str, Dict[str, Any]]:
    """Loads all non-quarantined provisions into a lookup map by provision_id."""
    prov_map = {}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if not item.get("is_quarantined", False):
                prov_map[item["provision_id"]] = item
    return prov_map


def get_evidence_for_case(
    case: Dict[str, Any], prov_map: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Returns the evidence passages to supply for a given case.
    For unanswerable cases (Category D), returns adjacent unrelated provisions
    to verify that the model correctly abstains rather than inventing law.
    """
    target_pids = case.get("target_provision_ids", [])
    if not target_pids:
        # For unanswerable queries, supply a realistic retrieval result of 2 unrelated provisions
        # e.g., Contract Act or Labour Act, so the model sees text but must recognize it's irrelevant
        if "contract" in case.get("query", "").lower() or "limitation" in case.get("query", "").lower():
            return [prov_map["CA1872_S1"], prov_map["CA1872_S10"]]
        else:
            return [prov_map["BLA2006_S১"], prov_map["CRPA2009_S১"]]

    evidence = []
    for pid in target_pids:
        if pid in prov_map:
            evidence.append(prov_map[pid])

    return evidence


def run_day4_evaluation(
    benchmark_path: Path,
    provisions_path: Path,
    output_json: Path,
    model_name: str = "qwen2.5:3b",
) -> Dict[str, Any]:
    print("=" * 80)
    print("LEGAL AID BD — DAY 4 LOCAL ANSWER GENERATION EVALUATION")
    print(f"Model: {model_name} on CPU | Benchmark: {benchmark_path}")
    print("=" * 80)

    prov_map = load_provisions_map(provisions_path)
    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    cases = benchmark_data["cases"]
    extractive_gen = ExtractiveBaselineGenerator()
    ollama_client = OllamaGenerationClient(model_name=model_name)
    rubric = GenerationRubricEvaluator(valid_corpus_pids=set(prov_map.keys()))

    server_alive = ollama_client.is_server_alive()
    print(f"Ollama Server Status: {'ONLINE' if server_alive else 'OFFLINE (Will skip generative run)'}")

    case_results = []
    t_start = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        cid = case["case_id"]
        category = case["category"]
        query = case["query"]
        lang = case["query_language"]
        is_answerable = case["is_answerable"]

        evidence_provisions = get_evidence_for_case(case, prov_map)
        evidence_pids = [p["provision_id"] for p in evidence_provisions]

        print(f"\n[{idx}/{len(cases)}] Case: {cid} ({category}) | Lang: {lang.upper()}")
        print(f"Query: '{query[:75]}...'")
        print(f"Supplied Evidence: {evidence_pids} | Answerable: {is_answerable}")

        # -------------------------------------------------------------
        # Condition A: Extractive Baseline
        # -------------------------------------------------------------
        # If unanswerable, we pass empty evidence to extractive generator to simulate retriever abstention
        extractive_input = [] if not is_answerable else evidence_provisions
        res_extractive = extractive_gen.generate(
            query=query,
            provisions=extractive_input,
            query_language=lang,
        )
        eval_extractive = rubric.evaluate(
            case=case,
            answer_text=res_extractive["answer"],
            condition="extractive",
            supplied_pids=evidence_pids,
        )

        # -------------------------------------------------------------
        # Condition B: Local Generative Model
        # -------------------------------------------------------------
        if server_alive:
            user_prompt = build_user_prompt(query, evidence_provisions)
            res_generative = ollama_client.generate(user_prompt)
            eval_generative = rubric.evaluate(
                case=case,
                answer_text=res_generative["answer"],
                condition="generative",
                supplied_pids=evidence_pids,
            )
        else:
            res_generative = {
                "answer": "OLLAMA_SERVER_OFFLINE",
                "total_latency_s": 0.0,
                "eval_count": 0,
                "eval_duration_s": 0.0,
                "tokens_per_sec": 0.0,
                "process_rss_mb": 0.0,
                "error": "Server offline",
            }
            eval_generative = {
                "scores": {k: 0 for k in eval_extractive["scores"]},
                "mean_rubric_score": 0.0,
                "extracted_citations": [],
                "is_abstention": False,
                "hallucination_detected": False,
            }

        # Print quick summary
        print(f"  [Condition A - Extractive] Score: {eval_extractive['mean_rubric_score']}/2.0 | Abstain: {eval_extractive['is_abstention']}")
        print(f"  [Condition B - Generative] Score: {eval_generative['mean_rubric_score']}/2.0 | Latency: {res_generative.get('total_latency_s', 0)}s | Tok/s: {res_generative.get('tokens_per_sec', 0)}")
        if res_generative.get("answer"):
            snippet = res_generative["answer"].replace("\n", " ")[:120]
            print(f"  [Gen Answer Snippet]: '{snippet}...'")

        case_record = {
            "case_id": cid,
            "category": category,
            "query": query,
            "query_language": lang,
            "is_answerable": is_answerable,
            "supplied_provisions": evidence_pids,
            "condition_a_extractive": {
                "answer": res_extractive["answer"],
                "is_abstention": res_extractive["is_abstention"],
                "cited_provision_ids": res_extractive["cited_provision_ids"],
                "eval": eval_extractive,
            },
            "condition_b_generative": {
                "answer": res_generative.get("answer", ""),
                "total_latency_s": res_generative.get("total_latency_s", 0.0),
                "tokens_per_sec": res_generative.get("tokens_per_sec", 0.0),
                "eval_count": res_generative.get("eval_count", 0),
                "process_rss_mb": res_generative.get("process_rss_mb", 0.0),
                "error": res_generative.get("error"),
                "eval": eval_generative,
            },
        }
        case_results.append(case_record)

    total_eval_time = round(time.perf_counter() - t_start, 2)

    # Compute aggregate metrics
    extractive_mean = round(float(sum(c["condition_a_extractive"]["eval"]["mean_rubric_score"] for c in case_results) / len(case_results)), 2)
    generative_mean = round(float(sum(c["condition_b_generative"]["eval"]["mean_rubric_score"] for c in case_results) / len(case_results)), 2)
    avg_gen_latency = round(float(sum(c["condition_b_generative"]["total_latency_s"] for c in case_results) / len(case_results)), 2)
    avg_tokens_per_sec = round(float(sum(c["condition_b_generative"]["tokens_per_sec"] for c in case_results) / len(case_results)), 2)
    peak_process_rss = max(c["condition_b_generative"]["process_rss_mb"] for c in case_results)

    summary_report = {
        "model_name": model_name,
        "runtime": "Ollama (CPU-only, Q4_K_M)",
        "total_cases": len(case_results),
        "total_eval_time_s": total_eval_time,
        "average_generation_latency_s": avg_gen_latency,
        "average_tokens_per_sec": avg_tokens_per_sec,
        "peak_process_rss_mb": peak_process_rss,
        "extractive_mean_rubric_score": extractive_mean,
        "generative_mean_rubric_score": generative_mean,
        "cases": case_results,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print(f"Condition A (Extractive) Mean Rubric Score: {extractive_mean} / 2.0")
    print(f"Condition B (Generative) Mean Rubric Score: {generative_mean} / 2.0")
    print(f"Avg Query Latency: {avg_gen_latency} s | Speed: {avg_tokens_per_sec} tok/s | Peak RAM: {peak_process_rss} MB")
    print(f"Results saved to: {output_json}")
    print("=" * 80)

    return summary_report


if __name__ == "__main__":
    b_path = Path("data/eval_generation_cases.json")
    p_path = Path("data/processed/provisions.jsonl")
    o_path = Path("experiments/day4_local_generation_results.json")
    run_day4_evaluation(b_path, p_path, o_path)
