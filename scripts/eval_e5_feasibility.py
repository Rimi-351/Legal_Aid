"""
scripts/eval_e5_feasibility.py
------------------------------
Independent feasibility evaluation of intfloat/multilingual-e5-base for
multilingual Bangladeshi legal retrieval on CPU.

Evaluates:
- Cold and warm model loading latency
- Corpus encoding throughput and resident memory (RSS)
- Vector dimensionality, finiteness, and L2 normalization
- Top-5 retrieval quality across Bangla, English, and Banglish legal queries
"""

import os
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import time
import json
import psutil
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

MODEL_ID = "intfloat/multilingual-e5-base"
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def get_process_rss_mb() -> float:
    """Returns current process resident set size (RSS) in MB."""
    return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)


def mean_pooling(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Computes mean pooling masked by token attention mask."""
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    sum_embeddings = torch.sum(last_hidden_state * input_mask_expanded, 1)
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    return sum_embeddings / sum_mask


class MultilingualE5Evaluator:

    def __init__(self, model_id: str = MODEL_ID, max_length: int = 512):
        self.model_id = model_id
        self.max_length = max_length
        self.initial_rss = get_process_rss_mb()
        
        t0 = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id)
        self.model.eval()
        self.load_time_s = round(time.perf_counter() - t0, 3)
        self.post_load_rss = get_process_rss_mb()
        self.load_delta_rss = round(self.post_load_rss - self.initial_rss, 2)

    def encode(self, texts: List[str], batch_size: int = 4) -> Tuple[np.ndarray, float]:
        """Encodes list of prefixed texts into L2-normalized numpy vectors."""
        t0 = time.perf_counter()
        all_embeddings = []

        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                encoded = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt"
                )
                outputs = self.model(**encoded)
                embeddings = mean_pooling(outputs.last_hidden_state, encoded["attention_mask"])
                embeddings = F.normalize(embeddings, p=2, dim=1)
                all_embeddings.append(embeddings.cpu().numpy())

        total_time = round(time.perf_counter() - t0, 4)
        return np.vstack(all_embeddings), total_time


def load_provisions(provisions_path: Path) -> List[Dict[str, Any]]:
    """Loads active (unquarantined) statutory provisions."""
    provisions = []
    with open(provisions_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                item = json.loads(line)
                if not item.get("is_quarantined", False):
                    provisions.append(item)
    return provisions


def run_evaluation(provisions_path: Path, output_json: Path) -> Dict[str, Any]:
    print("=" * 70)
    print(f"FEASIBILITY EVALUATION: {MODEL_ID}")
    print(f"Hardware: {psutil.cpu_count(logical=False)} Cores / {psutil.cpu_count(logical=True)} Threads CPU | RAM: {round(psutil.virtual_memory().total / (1024**3), 1)} GB")
    print("=" * 70)

    # 1. Load provisions
    provisions = load_provisions(provisions_path)
    print(f"Loaded {len(provisions)} active statutory provisions from {provisions_path.name}")

    # 2. Initialize Model
    evaluator = MultilingualE5Evaluator()
    print(f"Model Load Time: {evaluator.load_time_s} s | Load RAM Delta: {evaluator.load_delta_rss} MB | Post-Load RSS: {evaluator.post_load_rss} MB")

    # 3. Format and encode passages
    passage_texts = [
        f"{PASSAGE_PREFIX}{p.get('act_title', '')} {p.get('section_heading', '')} {p.get('text', '')}"
        for p in provisions
    ]
    doc_vectors, encode_time_s = evaluator.encode(passage_texts, batch_size=4)
    peak_rss = get_process_rss_mb()
    ms_per_doc = round((encode_time_s / len(provisions)) * 1000, 2)

    # Validate vector properties
    is_finite = bool(np.all(np.isfinite(doc_vectors)))
    vector_dim = int(doc_vectors.shape[1])
    norms = np.linalg.norm(doc_vectors, axis=1)
    is_normalized = bool(np.allclose(norms, 1.0, atol=1e-3))

    print(f"Corpus Encoding: {len(provisions)} provisions in {encode_time_s} s ({ms_per_doc} ms/doc)")
    print(f"Embedding Dim: {vector_dim} | Finite: {is_finite} | Unit L2 Norm: {is_normalized} (mean norm: {np.mean(norms):.4f})")
    print(f"Peak Process RSS during inference: {peak_rss} MB")

    # 4. Standard 9-query benchmark (3 Bangla, 3 Banglish, 3 English)
    test_queries = [
        {
            "query_id": "Q01_BN",
            "language": "bn",
            "query": "দোকানদার পণ্যের গায়ে মেয়াদোত্তীর্ণের তারিখ না লিখে বিক্রি করলে কি শাস্তি হবে?",
            "gold_provisions": ["CRPA2009_S৩৭"],
            "legal_concept": "Selling consumer goods without expiration date (Consumer Rights)"
        },
        {
            "query_id": "Q01_BANGLISH",
            "language": "banglish",
            "query": "Dokandar expiry date na likhe ponno sell korle ki shasti hobe consumer rights law te?",
            "gold_provisions": ["CRPA2009_S৩৭"],
            "legal_concept": "Selling consumer goods without expiration date (Banglish)"
        },
        {
            "query_id": "Q01_EN",
            "language": "en",
            "query": "What is the penalty if a seller sells goods without mentioning expiration date on packaging?",
            "gold_provisions": ["CRPA2009_S৩৭"],
            "legal_concept": "Selling consumer goods without expiration date (English)"
        },
        {
            "query_id": "Q02_BN",
            "language": "bn",
            "query": "চাকরির বয়স শেষ না হতেই মালিক নোটিশ ছাড়া বরখাস্ত করলে কত দিনের মজুরি দিতে হবে?",
            "gold_provisions": ["BLA2006_S২৬"],
            "legal_concept": "Termination of employment without notice (Labour Act)"
        },
        {
            "query_id": "Q02_BANGLISH",
            "language": "banglish",
            "query": "Chakri theke notice chara terminate korle koto diner salary pabo labour law onujayi?",
            "gold_provisions": ["BLA2006_S২৬"],
            "legal_concept": "Termination without notice compensation (Banglish)"
        },
        {
            "query_id": "Q02_EN",
            "language": "en",
            "query": "How many days notice or compensation must an employer provide to terminate a permanent worker?",
            "gold_provisions": ["BLA2006_S২৬"],
            "legal_concept": "Termination of permanent worker notice period (English)"
        },
        {
            "query_id": "Q03_BN",
            "language": "bn",
            "query": "বাড়িওয়ালা কি ইচ্ছামত ভাড়া বাড়িয়ে আমাকে বাড়ি থেকে উচ্ছেদ করতে পারবে?",
            "gold_provisions": ["PRCA1991_S১৮", "PRCA1991_S১৩"],
            "legal_concept": "Arbitrary rent escalation and tenant eviction (Rent Control Act)"
        },
        {
            "query_id": "Q03_BANGLISH",
            "language": "banglish",
            "query": "Bariwala iccha moto rent bariye keno evict korte parbe? Rent control law te ki ache?",
            "gold_provisions": ["PRCA1991_S১৮", "PRCA1991_S১৩"],
            "legal_concept": "Tenant eviction and rent hike (Banglish)"
        },
        {
            "query_id": "Q04_EN",
            "language": "en",
            "query": "Can a minor enter into a legally binding business agreement under Bangladesh Contract Act?",
            "gold_provisions": ["CA1872_S11", "CA1872_S10"],
            "legal_concept": "Minor competence to contract (Contract Act)"
        },
    ]

    # 5. Evaluate queries
    query_texts = [f"{QUERY_PREFIX}{q['query']}" for q in test_queries]
    query_vectors, q_encode_time_s = evaluator.encode(query_texts, batch_size=4)
    print(f"Query Encoding: {len(test_queries)} queries in {q_encode_time_s} s ({round((q_encode_time_s/len(test_queries))*1000, 2)} ms/query)")

    results = []
    print("\n" + "=" * 70)
    print("TOP-5 RETRIEVAL RESULTS BY QUERY")
    print("=" * 70)

    pids = [p["provision_id"] for p in provisions]

    for idx, q in enumerate(test_queries):
        q_vec = query_vectors[idx]
        sims = np.dot(doc_vectors, q_vec)
        
        # Rank by score descending, secondary sort by pid for deterministic ties
        ranked_indices = sorted(range(len(pids)), key=lambda i: (-sims[i], pids[i]))
        top5_indices = ranked_indices[:5]
        top5 = [
            {
                "rank": rank + 1,
                "provision_id": pids[i],
                "score": round(float(sims[i]), 4),
                "is_gold": bool(pids[i] in q["gold_provisions"]),
                "heading": provisions[i].get("section_heading", ""),
                "act_title": provisions[i].get("act_title", ""),
            }
            for rank, i in enumerate(top5_indices)
        ]

        # Calculate metrics for this query
        gold_ranks = [t["rank"] for t in top5 if t["is_gold"]]
        rr = round(1.0 / gold_ranks[0], 4) if gold_ranks else 0.0
        hits_in_5 = len(gold_ranks)
        recall_at_5 = round(hits_in_5 / len(q["gold_provisions"]), 4)

        query_result = {
            "query_id": q["query_id"],
            "language": q["language"],
            "query": q["query"],
            "gold_provisions": q["gold_provisions"],
            "legal_concept": q["legal_concept"],
            "reciprocal_rank": rr,
            "recall_at_5": recall_at_5,
            "top5": top5,
        }
        results.append(query_result)

        gold_status = f"HIT (Rank {gold_ranks[0]})" if gold_ranks else "MISS"
        print(f"\n[{q['query_id']} | {q['language'].upper()}] '{q['query'][:60]}...'")
        print(f"Target: {q['gold_provisions']} | Status: {gold_status} | MRR: {rr} | Recall@5: {recall_at_5}")
        for t in top5:
            marker = "--> [GOLD]" if t["is_gold"] else "          "
            print(f"  {marker} Rank {t['rank']}: {t['provision_id']} (score: {t['score']:.4f}) - {t['act_title']} : {t['heading']}")

    # Aggregate Metrics
    overall_mrr = round(float(np.mean([r["reciprocal_rank"] for r in results])), 4)
    overall_recall = round(float(np.mean([r["recall_at_5"] for r in results])), 4)

    lang_mrr = {}
    for lang in ["bn", "banglish", "en"]:
        lang_runs = [r for r in results if r["language"] == lang]
        lang_mrr[lang] = round(float(np.mean([r["reciprocal_rank"] for r in lang_runs])), 4) if lang_runs else 0.0

    print("\n" + "=" * 70)
    print("AGGREGATE BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"Overall MRR@5: {overall_mrr} | Overall Recall@5: {overall_recall}")
    print(f"Bangla MRR: {lang_mrr.get('bn', 0.0)} | Banglish MRR: {lang_mrr.get('banglish', 0.0)} | English MRR: {lang_mrr.get('en', 0.0)}")
    print(f"Peak Process RSS: {peak_rss} MB | Corpus Encoding: {encode_time_s} s ({ms_per_doc} ms/doc)")
    print("=" * 70)

    summary_data = {
        "model_id": MODEL_ID,
        "parameters": "278M",
        "embedding_dim": vector_dim,
        "is_finite": is_finite,
        "is_normalized": is_normalized,
        "model_load_time_s": evaluator.load_time_s,
        "corpus_encode_time_s": encode_time_s,
        "ms_per_doc": ms_per_doc,
        "query_encode_time_s": q_encode_time_s,
        "initial_rss_mb": evaluator.initial_rss,
        "post_load_rss_mb": evaluator.post_load_rss,
        "peak_rss_mb": peak_rss,
        "overall_mrr_at_5": overall_mrr,
        "overall_recall_at_5": overall_recall,
        "language_mrr": lang_mrr,
        "queries": results,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved feasibility report to {output_json}")

    return summary_data


if __name__ == "__main__":
    prov_file = Path("data/processed/provisions.jsonl")
    out_file = Path("experiments/day3_e5_feasibility_results.json")
    run_evaluation(prov_file, out_file)
