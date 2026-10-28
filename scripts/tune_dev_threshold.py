#!/usr/bin/env python3
"""
scripts/tune_dev_threshold.py
------------------------------
Tunes ABSTAIN_THRESHOLD strictly on the development split (no test data accessed).
Logs the full threshold sweep (threshold, precision, recall, F1) to eval/threshold_sweep.csv.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.config import check_retrieval_abstention
from src.retrieval.bm25 import BM25Index


def tune_dev_threshold(
    split_path: Path = Path("eval/split.json"),
    corpus_path: Path = Path("data/processed/provisions.jsonl"),
    benchmark_dev_path: Path = Path("data/benchmarks/benchmark_dev.jsonl"),
    insufficient_csv_path: Path = Path("eval/insufficient_evidence.csv"),
    output_sweep_csv: Path = Path("eval/threshold_sweep.csv")
) -> Tuple[float, float, float, float]:
    # 1. Load dev IDs strictly
    with open(split_path, "r", encoding="utf-8") as f:
        split_data = json.load(f)
    dev_ids = set(split_data["dev_ids"])

    # 2. Load dev queries
    dev_queries = []
    with open(benchmark_dev_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                if q["query_id"] in dev_ids and q.get("corpus_has_sufficient_evidence"):
                    dev_queries.append({
                        "id": q["query_id"],
                        "query": q["original_user_query"],
                        "is_insuf": False
                    })

    with open(insufficient_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["id"] in dev_ids:
                dev_queries.append({
                    "id": r["id"],
                    "query": r["question"],
                    "is_insuf": True
                })

    # 3. Fit BM25 retriever
    records = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                if not p.get("is_quarantined", False):
                    records.append(p)

    retriever = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    retriever.fit(records)

    # 4. Freeze dev retrieval
    cached_dev = []
    for item in dev_queries:
        hits = retriever.search(item["query"], top_k=5)
        ev = [
            {
                "record_id": h.provision_id,
                "section_id": h.section_number,
                "act_title": h.act_title,
                "score": h.score
            }
            for h in hits
        ]
        cached_dev.append({
            "id": item["id"],
            "query": item["query"],
            "evidence": ev,
            "is_insuf": item["is_insuf"]
        })

    # 5. Sweep threshold from 0.0 to 50.0 in increments of 0.5
    sweep_rows = []
    best_t = 0.0
    best_f1 = -1.0
    best_p = 0.0
    best_r = 0.0

    for step in range(0, 101):
        t = round(step * 0.5, 2)
        tp = fp = fn = tn = 0

        for q in cached_dev:
            pred_abstain, _ = check_retrieval_abstention(q["query"], q["evidence"], threshold=t)
            is_insuf = q["is_insuf"]

            if pred_abstain and is_insuf:
                tp += 1
            elif pred_abstain and not is_insuf:
                fp += 1
            elif not pred_abstain and is_insuf:
                fn += 1
            else:
                tn += 1

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

        sweep_rows.append({
            "threshold": t,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn
        })

        if f1 > best_f1 or (f1 == best_f1 and t < best_t):
            best_f1 = f1
            best_t = t
            best_p = p
            best_r = r

    # 6. Save sweep log to eval/threshold_sweep.csv
    output_sweep_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_sweep_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["threshold", "precision", "recall", "f1", "tp", "fp", "fn", "tn"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sweep_rows:
            writer.writerow(row)

    print(f"[*] Tuned ABSTAIN_THRESHOLD on dev split only ({len(dev_queries)} queries):")
    print(f"    Threshold={best_t:.1f}, F1={best_f1:.4f}, Precision={best_p:.4f}, Recall={best_r:.4f}")
    print(f"[+] Saved threshold sweep log to: {output_sweep_csv}")

    return best_t, best_f1, best_p, best_r


if __name__ == "__main__":
    tune_dev_threshold()

