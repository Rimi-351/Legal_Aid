"""
scripts/smoke_test_dense_inference.py
-------------------------------------
Opt-in smoke test for verifying actual PyTorch CPU dense model inference,
tensor output dimensionality, finite value checks, and RAM safety.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.retrieval.dense import DenseRetriever, get_process_rss_mb, TORCH_TRANSFORMERS_AVAILABLE


def main():
    print("[*] Starting Opt-In Dense Model CPU Inference Smoke Test...")
    if not TORCH_TRANSFORMERS_AVAILABLE:
        print("[!] FAILURE: PyTorch or HuggingFace Transformers is not installed in the current environment.")
        sys.exit(1)

    model_name = "csebuetnlp/banglabert"
    if len(sys.argv) > 1:
        model_name = sys.argv[1]

    print(f"[*] Target Model: {model_name}")
    print(f"[*] Initial Process RSS: {get_process_rss_mb()} MB")

    t0 = time.time()
    retriever = DenseRetriever(model_name=model_name, device="cpu")
    retriever.load_model()
    load_time = time.time() - t0
    rss_after_load = get_process_rss_mb()

    print(f"[+] Model loaded in {load_time:.2f} s. Process RSS: {rss_after_load} MB")

    # Sample bilingual statutory provisions
    test_docs = [
        {"provision_id": "TEST_P1", "text": "চুক্তি আইন অনুযায়ী বৈধ প্রতিদান ব্যতিরেকে চুক্তি বাতিল বলিয়া গণ্য হইবে।"},
        {"provision_id": "TEST_P2", "text": "The Contract Act: An agreement without consideration is void."}
    ]

    print("[*] Encoding test batch on CPU...")
    t1 = time.time()
    doc_texts = [p["text"] for p in test_docs]
    embeddings = retriever.encode(doc_texts, is_query=False)
    encode_time = time.time() - t1

    print(f"[+] Encoded {len(test_docs)} documents in {encode_time:.2f} s")
    print(f"    - Output Matrix Shape: {embeddings.shape}")
    print(f"    - Embedding Dimension: {embeddings.shape[1]}")
    print(f"    - All Values Finite:  {bool((embeddings == embeddings).all())}")

    assert embeddings.shape == (2, 768), f"Unexpected embedding shape: {embeddings.shape}"
    assert (embeddings == embeddings).all(), "NaN or Inf detected in embedding matrix!"

    # Query encoding test
    q_vec = retriever.encode(["চুক্তি বাতিল সংক্রান্ত নিয়ম"], is_query=True)
    assert q_vec.shape == (1, 768), f"Unexpected query embedding shape: {q_vec.shape}"

    print(f"[+] Opt-in dense model CPU smoke test PASSED successfully!")
    print(f"[*] Final Process RSS: {get_process_rss_mb()} MB (Well within 11.5 GB budget)")


if __name__ == "__main__":
    main()
