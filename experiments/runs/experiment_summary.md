# Legal Aid BD — Retrieval Experiment Tracking Summary

| Experiment ID | Timestamp (UTC) | Method | Model | Queries | Duration | Peak RSS | Reciprocal Rank | Status |
|---|---|---|---|---|---|---|---|---|
| `EXP_20261023_210948_5473ea` | 2026-10-23T15:09:48Z | `bm25` | `bm25_word_tokens` | 12 | 0.01 s | 376.3 MB | 0.4444 | Completed |
| `EXP_20261023_211016_24ffec` | 2026-10-23T15:10:16Z | `bm25_ngram` | `bm25_char_3gram` | 12 | 0.01 s | 376.4 MB | 0.5417 | Completed |
| `EXP_20261023_211218_bd9e0f` | 2026-10-23T15:12:18Z | `dense` | `csebuetnlp/banglabert` | 12 | 8.74 s | 879.2 MB | 0.4375 | Completed |
| `EXP_20261023_211259_66393b` | 2026-10-23T15:12:59Z | `hybrid` | `hybrid_rrf_bm25_csebuetnlp/banglabert` | 12 | 8.44 s | 838.0 MB | 0.4194 | Completed |
