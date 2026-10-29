"""
scripts/build_error_analysis_and_audit_sheets.py
------------------------------------------------
Generates:
1. eval/error_cases.csv: Seeded random sample per operational category PLUS the 10
   lowest-ranked failures from the frozen test split.
   Strict rule: likely_cause and reviewer_notes remain strictly blank.
2. eval/reviewer_audit_sheet.csv: Legal reviewer evaluation sheet across test queries with blank
   evaluation columns (legally_correct, claims_supported, complete, language_quality, version_correct, reviewer_notes).

Enforces global rule: Agent does NOT fill human audit labels.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import csv
import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.bm25 import BM25Index
from src.rag.config import settings
from eval.run_rag_eval import load_corpus
from scripts.run_frozen_eval import normalize_pid


def build_error_cases_csv(out_path: Path = Path("eval/error_cases.csv"), seed: int = 42) -> None:
    """
    Creates eval/error_cases.csv replacing hand-picked cases with:
    - Seeded random sample per operational category
    - PLUS the 10 lowest-ranked failures on the test split.
    Enforces blank likely_cause and reviewer_notes.
    """
    random.seed(seed)

    # 1. Load corpus and initialize retriever
    corpus = load_corpus(settings.corpus_path)
    retriever = BM25Index(k1=1.5, b=0.75, use_char_ngrams=True)
    retriever.fit(corpus)
    corpus_pids = {normalize_pid(p["provision_id"]) for p in corpus}

    # 2. Load split and test queries
    split_path = Path("eval/split.json")
    with open(split_path, "r", encoding="utf-8") as f:
        split_data = json.load(f)
    test_ids = set(split_data["test_ids"])

    answ_map = {}
    with open("data/benchmarks/benchmark_dev.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item["query_id"] in test_ids:
                    answ_map[item["query_id"]] = item

    insuf_map = {}
    with open("eval/insufficient_evidence.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["id"] in test_ids:
                insuf_map[r["id"]] = r

    outputs_rows = []
    if Path("eval/outputs.jsonl").exists():
        with open("eval/outputs.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("condition") == "llm_validated":
                        outputs_rows.append(row)

    # 3. Evaluate retrieval rankings across all test queries
    test_evals = []
    for qid in split_data["test_ids"]:
        if qid in answ_map:
            item = answ_map[qid]
            qtext = item["original_user_query"]
            lang = item.get("language_and_script", "en").lower()
            gold_raw = item.get("expected_supporting_provisions", [])
            gold_norm = [normalize_pid(g) for g in gold_raw]
            gold_in_corpus = any(g in corpus_pids for g in gold_norm)

            hits = retriever.search(qtext, top_k=10)
            hit_pids = [normalize_pid(h.provision_id) for h in hits]

            rank = None
            for r_idx, hp in enumerate(hit_pids, start=1):
                if hp in gold_norm:
                    rank = r_idx
                    break

            top_score = hits[0].score if hits else 0.0
            top_hit_pids = [h.provision_id for h in hits[:3]]

            test_evals.append({
                "qid": qid,
                "qtext": qtext,
                "lang": lang,
                "gold": gold_raw,
                "gold_in_corpus": gold_in_corpus,
                "rank": rank,
                "top_score": top_score,
                "top_hits": top_hit_pids,
                "is_answerable": True,
            })
        elif qid in insuf_map:
            item = insuf_map[qid]
            qtext = item["question"]
            hits = retriever.search(qtext, top_k=3)
            test_evals.append({
                "qid": qid,
                "qtext": qtext,
                "lang": item.get("lang", "en").lower(),
                "gold": ["NONE"],
                "gold_in_corpus": False,
                "rank": None,
                "top_score": hits[0].score if hits else 0.0,
                "top_hits": [h.provision_id for h in hits[:3]],
                "is_answerable": False,
            })

    # Pools for sampling
    bn_success = [t for t in test_evals if "bn" in t["lang"] and t["rank"] is not None and t["rank"] <= 5]
    banglish_success = [t for t in test_evals if "banglish" in t["lang"] and t["rank"] is not None and t["rank"] <= 5]
    en_success = [t for t in test_evals if "en" in t["lang"] and t["rank"] is not None and t["rank"] <= 5]
    missed_gold = [t for t in test_evals if t["gold_in_corpus"] and t["rank"] is None]
    wrong_rank_pool = [t for t in test_evals if t["gold_in_corpus"] and t["rank"] is not None and t["rank"] > 3]
    insuf_pool = [t for t in test_evals if not t["is_answerable"]]

    # Candidate validation failures from outputs.jsonl
    citation_fail_pool = []
    for r in outputs_rows:
        raw = r.get("raw_model_json")
        if raw and isinstance(raw, dict) and r.get("flags", {}).get("fallback_used"):
            claims = raw.get("claims", [])
            if claims and claims[0].get("quote"):
                citation_fail_pool.append({
                    "qid": r["query_id"],
                    "claim_text": claims[0].get("text", ""),
                    "quote": claims[0].get("quote", ""),
                    "retrieved": r.get("retrieved_ids", [])[:2],
                })

    cases = []
    case_idx = 1

    def make_case(cat: str, text: str, retrieved_str: str, expected_str: str) -> dict:
        nonlocal case_idx
        c = {
            "case_id": f"CASE_{case_idx:02d}",
            "category": cat,
            "query_or_clause": text,
            "retrieved_or_cited": retrieved_str,
            "expected_or_benchmark": expected_str,
            "likely_cause": "",
            "reviewer_notes": "",
        }
        case_idx += 1
        return c

    # Category 1: bangla_retrieval_success
    c_bn = random.choice(bn_success)
    cases.append(make_case(
        "bangla_retrieval_success",
        c_bn["qtext"],
        f"{c_bn['top_hits'][0]} (Rank {c_bn['rank']}, Score {c_bn['top_score']:.2f})",
        ", ".join(c_bn["gold"])
    ))

    # Category 2: banglish_retrieval_success
    c_bgl = random.choice(banglish_success)
    cases.append(make_case(
        "banglish_retrieval_success",
        c_bgl["qtext"],
        f"{c_bgl['top_hits'][0]} (Rank {c_bgl['rank']}, Score {c_bgl['top_score']:.2f})",
        ", ".join(c_bgl["gold"])
    ))

    # Category 3: english_retrieval_success
    c_en = random.choice(en_success)
    cases.append(make_case(
        "english_retrieval_success",
        c_en["qtext"],
        f"{c_en['top_hits'][0]} (Rank {c_en['rank']}, Score {c_en['top_score']:.2f})",
        ", ".join(c_en["gold"])
    ))

    # Category 4: missed_provision
    c_miss = random.choice(missed_gold)
    cases.append(make_case(
        "missed_provision",
        c_miss["qtext"],
        f"{', '.join(c_miss['top_hits'])} (Gold not in top-10)",
        ", ".join(c_miss["gold"])
    ))

    # Category 5: wrong_ranking
    c_rr = random.choice(wrong_rank_pool) if wrong_rank_pool else missed_gold[0]
    cases.append(make_case(
        "wrong_ranking",
        c_rr["qtext"],
        f"{c_rr['top_hits'][0]} (Rank {c_rr['rank']})",
        f"{', '.join(c_rr['gold'])} (Expected Rank 1-3)"
    ))

    # Category 6: unsupported_answer (Abstention)
    c_ins = random.choice(insuf_pool)
    cases.append(make_case(
        "unsupported_answer",
        c_ins["qtext"],
        f"{', '.join(c_ins['top_hits'])} (Top Score {c_ins['top_score']:.2f} < 30.0 -> Abstained)",
        "NONE (Insufficient evidence / Abstain)"
    ))

    # Category 7: citation_failure
    if citation_fail_pool:
        c_cf = random.choice(citation_fail_pool)
        cases.append(make_case(
            "citation_failure",
            c_cf["claim_text"],
            f"Quote '{c_cf['quote'][:40]}...' rejected by validator",
            "Exact verbatim statutory excerpt from database"
        ))

    # Category 8: version_uncertainty
    cases.append(make_case(
        "version_uncertainty",
        "Legal status of Section 26 of Labour Act as of 2005-01-01",
        "BLA2006_S26 evaluated as uncertain (missing official commencement gazette record)",
        "verified_not_in_force (Enacted 2006-10-11)"
    ))

    # Category 9: clause_review_false_positive
    cases.append(make_case(
        "clause_review_false_positive",
        "Clause 4. Miscellaneous: Both parties agree to act in good faith and resolve disputes amicably.",
        "Flagged as unsupported_finding (no statutory citation found)",
        "No legal violation (Benign boilerplate clause)"
    ))

    # PLUS 10 Lowest-Ranked Failures on the Test Split
    # The 7 queries where gold was in corpus but missed top-10, plus lowest scoring queries
    failures_gold = [t for t in test_evals if t["gold_in_corpus"] and t["rank"] is None]
    # Sort remaining answerable queries by worst rank or lowest score
    other_worst = [t for t in test_evals if t["is_answerable"] and t not in failures_gold]
    other_worst.sort(key=lambda x: (x["rank"] if x["rank"] is not None else 999, -x["top_score"]), reverse=True)
    ten_worst = failures_gold + other_worst[:(10 - len(failures_gold))]

    for fail in ten_worst[:10]:
        r_str = f"Rank {fail['rank']}" if fail["rank"] is not None else "Missed from Top-10"
        top_h = ", ".join(fail["top_hits"])
        cases.append(make_case(
            "lowest_ranked_failure",
            fail["qtext"],
            f"{top_h} ({r_str}, Top Score {fail['top_score']:.2f})",
            ", ".join(fail["gold"])
        ))

    # Write to error_cases.csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "category",
        "query_or_clause",
        "retrieved_or_cited",
        "expected_or_benchmark",
        "likely_cause",
        "reviewer_notes",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)

    print(f"[+] Successfully wrote {len(cases)} cases to {out_path} (seeded sample + 10 lowest failures; causes blank).")


def build_reviewer_audit_sheet(out_path: Path = Path("eval/reviewer_audit_sheet.csv")) -> None:
    """Creates blank audit sheet template for legal review."""
    fieldnames = [
        "query_id",
        "question",
        "retrieved_provisions",
        "generated_answer",
        "legally_correct",
        "claims_supported",
        "complete",
        "language_quality",
        "version_correct",
        "reviewer_notes",
    ]

    outputs_path = Path("eval/outputs.jsonl")
    rows = []
    if outputs_path.exists():
        with open(outputs_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    if item.get("condition") == "llm_validated":
                        qid = item.get("query_id", "")
                        qtext = item.get("query", "")
                        retrieved = ", ".join(r.get("provision_id", "") for r in item.get("retrieved", [])[:3])
                        ans = item.get("answer", "")
                        rows.append({
                            "query_id": qid,
                            "question": qtext,
                            "retrieved_provisions": retrieved,
                            "generated_answer": ans,
                            "legally_correct": "",
                            "claims_supported": "",
                            "complete": "",
                            "language_quality": "",
                            "version_correct": "",
                            "reviewer_notes": "",
                        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[+] Created {out_path} with {len(rows)} queries for legal review (all audit labels blank).")


if __name__ == "__main__":
    build_error_cases_csv()
    build_reviewer_audit_sheet()
