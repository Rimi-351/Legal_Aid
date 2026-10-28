#!/usr/bin/env python3
"""
eval/score_review.py
---------------------
Computes human review metrics and inter-annotator agreement:
- Reads eval/human_review_sheet.csv and eval/review_key.csv
- Calculates claim support rate and contradiction rate per condition (including extractive)
- Computes Cohen's kappa for inter-annotator agreement across labels
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import csv
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple


def cohens_kappa(labels1: List[str], labels2: List[str]) -> float:
    """Computes Cohen's kappa inter-annotator agreement score."""
    if not labels1 or not labels2 or len(labels1) != len(labels2):
        return 0.0

    categories = sorted(list(set(labels1) | set(labels2)))
    if not categories:
        return 0.0
    if len(categories) == 1:
        return 1.0

    n = len(labels1)
    # Observed agreement
    agree = sum(1 for a, b in zip(labels1, labels2) if a == b)
    p_o = agree / n

    # Expected agreement by chance
    p_e = 0.0
    for cat in categories:
        p1 = sum(1 for a in labels1 if a == cat) / n
        p2 = sum(1 for b in labels2 if b == cat) / n
        p_e += p1 * p2

    if abs(1.0 - p_e) < 1e-9:
        return 1.0
    return round((p_o - p_e) / (1.0 - p_e), 4)


def score_human_review(sheet_path: Path, key_path: Path) -> Dict[str, Any]:
    if not sheet_path.exists():
        raise FileNotFoundError(f"Review sheet not found: {sheet_path}")
    if not key_path.exists():
        raise FileNotFoundError(f"Review key not found: {key_path}")

    # Load private key mapping sample_id -> condition
    key_map = {}
    with open(key_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            key_map[r["sample_id"]] = r

    # Load review sheet
    rows = []
    with open(sheet_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # Check if annotator columns have been filled
    has_a1 = any(r.get("supported_annotator_1", "").strip() for r in rows)
    has_a2 = any(r.get("supported_annotator_2", "").strip() for r in rows)

    if not has_a1 and not has_a2:
        print("[!] Human review sheet has no completed annotations yet (blank template).")
        return {"status": "unlabeled", "total_samples": len(rows)}

    # Group by condition
    by_condition: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        sid = r["sample_id"]
        meta = key_map.get(sid, {})
        cond = meta.get("condition", "unknown")
        by_condition.setdefault(cond, []).append(r)

    results: Dict[str, Any] = {"conditions": {}}

    for cond, cond_rows in sorted(by_condition.items()):
        total = len(cond_rows)
        supported_cnt = 0
        contradicts_cnt = 0

        for r in cond_rows:
            # Prefer annotator 1 or majority
            s_val = (r.get("supported_annotator_1") or r.get("supported_annotator_2") or "").strip().upper()
            c_val = (r.get("contradicts_annotator_1") or r.get("contradicts_annotator_2") or "").strip().upper()
            if s_val in ("Y", "YES", "PARTIAL", "P"):
                supported_cnt += 1
            if c_val in ("Y", "YES"):
                contradicts_cnt += 1

        results["conditions"][cond] = {
            "total_samples": total,
            "claim_support_rate": round(supported_cnt / total, 4) if total > 0 else 0.0,
            "contradiction_rate": round(contradicts_cnt / total, 4) if total > 0 else 0.0,
        }

    # Inter-annotator agreement if both annotators present
    if has_a1 and has_a2:
        kappa_supported = cohens_kappa(
            [r.get("supported_annotator_1", "").strip() for r in rows],
            [r.get("supported_annotator_2", "").strip() for r in rows]
        )
        kappa_contradicts = cohens_kappa(
            [r.get("contradicts_annotator_1", "").strip() for r in rows],
            [r.get("contradicts_annotator_2", "").strip() for r in rows]
        )
        results["agreement"] = {
            "cohens_kappa_supported": kappa_supported,
            "cohens_kappa_contradicts": kappa_contradicts
        }

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score blinded human review sheet")
    parser.add_argument("--sheet", type=Path, default=Path("eval/human_review_sheet.csv"))
    parser.add_argument("--key", type=Path, default=Path("eval/review_key.csv"))
    args = parser.parse_args()

    res = score_human_review(args.sheet, args.key)
    print(json.dumps(res, indent=2, ensure_ascii=False))

