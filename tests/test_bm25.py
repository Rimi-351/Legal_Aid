"""
tests/test_bm25.py
------------------
Unit tests for the Okapi BM25 retrieval engine, BengaliEnglishTokenizer,
character n-grams, edge case queries, and provenance preservation.
"""

import unittest
from src.retrieval.bm25 import BM25Retriever, BengaliEnglishTokenizer, SearchResult


class TestBengaliEnglishTokenizer(unittest.TestCase):

    def setUp(self):
        self.word_tokenizer = BengaliEnglishTokenizer(use_char_ngrams=False)
        self.ngram_tokenizer = BengaliEnglishTokenizer(use_char_ngrams=True, ngram_n=3)

    def test_word_tokenization_bengali_and_english(self):
        """Verify standard word tokenization for mixed legal text."""
        text = "ধারা ২৫: Agreement without consideration is void."
        tokens = self.word_tokenizer.tokenize(text)
        self.assertIn("ধারা", tokens)
        self.assertIn("২৫", tokens)
        self.assertIn("agreement", tokens)
        self.assertIn("consideration", tokens)
        self.assertIn("void", tokens)

    def test_character_ngrams_generation(self):
        """Verify character 3-grams are produced to bridge Banglish variations."""
        text = "biman chukti"
        tokens = self.ngram_tokenizer.tokenize(text)
        # Should include words plus character 3-grams
        self.assertIn("biman", tokens)
        self.assertIn("bim", tokens)
        self.assertIn("ima", tokens)
        self.assertIn("man", tokens)

    def test_empty_and_whitespace_tokenization(self):
        """Verify empty strings return empty token lists."""
        self.assertEqual(self.word_tokenizer.tokenize(""), [])
        self.assertEqual(self.word_tokenizer.tokenize("   \n\t  "), [])


class TestBM25Retriever(unittest.TestCase):

    def setUp(self):
        self.corpus = [
            {
                "provision_id": "BD-ACT-CA1872-SEC-10",
                "doc_id": "CA1872",
                "act_title": "The Contract Act, 1872",
                "section_number": "10",
                "section_heading": "What agreements are contracts",
                "text": "All agreements are contracts if they are made by the free consent of parties competent to contract.",
                "language": "en",
                "source_file": "contract_act.html",
                "is_quarantined": False
            },
            {
                "provision_id": "BD-ACT-CA1872-SEC-25",
                "doc_id": "CA1872",
                "act_title": "The Contract Act, 1872",
                "section_number": "25",
                "section_heading": "Agreement without consideration, void",
                "text": "An agreement made without consideration is void unless it is in writing and registered under law.",
                "language": "en",
                "source_file": "contract_act.html",
                "is_quarantined": False
            },
            {
                "provision_id": "BD-ACT-CRPA2009-SEC-45",
                "doc_id": "CRPA2009",
                "act_title": "ভোক্তা অধিকার সংরক্ষণ আইন, ২০০৯",
                "section_number": "৪৫",
                "section_heading": "ভেজাল পণ্য বিক্রয়ের দণ্ড",
                "text": "কোন ব্যক্তি পণ্যে ভেজাল মিশ্রণ করিলে অনধিক তিন বৎসর কারাদণ্ড বা অনধিক দুই লক্ষ টাকা অর্থদণ্ডে দণ্ডিত হইবেন।",
                "language": "bn",
                "source_file": "crpa_2009.html",
                "is_quarantined": False
            }
        ]
        self.retriever = BM25Retriever(use_char_ngrams=False)
        self.retriever.index_corpus(self.corpus)

    def test_ranking_precision_english(self):
        """Verify query on consideration ranks Section 25 as rank 1."""
        results = self.retriever.search("agreement without consideration", top_k=3)
        self.assertGreaterEqual(len(results), 1)
        top_hit = results[0]
        self.assertEqual(top_hit.provision_id, "BD-ACT-CA1872-SEC-25")
        self.assertGreater(top_hit.score, 0.0)
        self.assertEqual(top_hit.rank, 1)

    def test_ranking_precision_bengali(self):
        """Verify Bengali query on ভেজাল ranks Section 45 at rank 1."""
        results = self.retriever.search("পণ্যে ভেজাল মিশ্রণের শাস্তি", top_k=3)
        self.assertGreaterEqual(len(results), 1)
        top_hit = results[0]
        self.assertEqual(top_hit.provision_id, "BD-ACT-CRPA2009-SEC-45")
        self.assertEqual(top_hit.language, "bn")

    def test_provenance_preservation(self):
        """Verify all provenance fields are preserved in SearchResult."""
        results = self.retriever.search("free consent competent", top_k=1)
        self.assertEqual(len(results), 1)
        hit = results[0]
        self.assertEqual(hit.provision_id, "BD-ACT-CA1872-SEC-10")
        self.assertEqual(hit.act_title, "The Contract Act, 1872")
        self.assertEqual(hit.section_number, "10")
        self.assertEqual(hit.source_file, "contract_act.html")
        self.assertIsInstance(hit.matched_tokens, list)

    def test_empty_query_returns_empty(self):
        """Verify searching with empty or whitespace string safely returns empty list."""
        self.assertEqual(self.retriever.search("", top_k=5), [])
        self.assertEqual(self.retriever.search("   ", top_k=5), [])

    def test_invalid_top_k(self):
        """Verify zero or negative top-k returns empty list."""
        self.assertEqual(self.retriever.search("agreement", top_k=0), [])
        self.assertEqual(self.retriever.search("agreement", top_k=-1), [])

    def test_unindexed_corpus_search(self):
        """Verify unindexed retriever returns empty list without crashing."""
        empty_retriever = BM25Retriever()
        results = empty_retriever.search("test query", top_k=5)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
