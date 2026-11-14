"""
tests/test_retrieval_edges.py
-----------------------------
Unit tests for boundary conditions in lexical retrieval (BM25Index) and
statutory temporal versioning (resolve_provision_version_status).
Verifies behavior on extreme top_k, duplicate records, zero-match queries,
and exact enactment/repeal temporal boundaries.
"""
import pytest
from src.retrieval.bm25 import BM25Index
from src.retrieval.temporal import resolve_provision_version_status, parse_date_string


@pytest.fixture
def sample_corpus():
    """Provides a small controlled corpus for boundary testing."""
    return [
        {
            "provision_id": "ACT2006_S26",
            "act_title": "Bangladesh Labour Act 2006",
            "section_number": "26",
            "section_heading": "Termination of employment by notice",
            "text": "The employment of a permanent worker may be terminated by the employer by giving notice.",
            "language": "en",
            "evidence_type": "official",
            "review_status": "verified",
            "enactment_date": "2006-10-11",
            "effective_date": "2006-10-11",
        },
        {
            "provision_id": "ACT1991_S18",
            "act_title": "Premises Rent Control Act 1991",
            "section_number": "18",
            "section_heading": "Protection of tenant against eviction",
            "text": "No order or decree for recovery of possession of any premises shall be made as long as tenant pays rent.",
            "language": "en",
            "evidence_type": "official",
            "review_status": "verified",
            "enactment_date": "1991-03-31",
            "effective_date": "1991-03-31",
            "repeal_date": "2020-01-01",
            "relation": "repeal",
        },
        {
            "provision_id": "CRPA2009_S37",
            "act_title": "Consumer Rights Protection Act 2009",
            "section_number": "37",
            "section_heading": "Penalty for not selling goods with price label",
            "text": "Failure to affix retail price, expiry date, or weight on consumer goods packaging is an offence.",
            "language": "en",
            "evidence_type": "official",
            "review_status": "verified",
            "enactment_date": "2009-04-06",
            "effective_date": "2009-04-06",
        },
    ]


def test_bm25_top_k_larger_than_corpus_size(sample_corpus):
    """
    Risk: Requesting top_k greater than corpus size must return all matching
    documents without padding with None, throwing IndexError, or crashing.
    """
    index = BM25Index()
    index.fit(sample_corpus)

    results = index.search("employment notice eviction price", top_k=50)
    assert len(results) <= len(sample_corpus)
    assert len(results) == 3
    assert [r.rank for r in results] == [1, 2, 3]


def test_bm25_top_k_zero_returns_empty(sample_corpus):
    """
    Risk: top_k=0 must return an empty list immediately without computation.
    """
    index = BM25Index()
    index.fit(sample_corpus)

    results = index.search("employment notice", top_k=0)
    assert results == []


def test_bm25_no_match_query_returns_empty(sample_corpus):
    """
    Risk: Queries that have zero token overlap with indexed vocabulary must
    safely return an empty list rather than returning arbitrary documents.
    """
    index = BM25Index()
    index.fit(sample_corpus)

    results = index.search("xyzqwerty987 সম্পূর্ণ_অজানা_শব্দ", top_k=5)
    assert results == []


def test_bm25_duplicate_documents_in_corpus():
    """
    Risk: Multiple identical or near-duplicate documents must index properly,
    share identical scores for matching queries, and break ties deterministically.
    """
    duplicates = [
        {
            "provision_id": "DOC_DUP_B",
            "act_title": "Contract Act 1872",
            "section_number": "27",
            "section_heading": "Agreement in restraint of trade",
            "text": "Every agreement in restraint of lawful trade is void.",
            "language": "en",
        },
        {
            "provision_id": "DOC_DUP_A",
            "act_title": "Contract Act 1872",
            "section_number": "27",
            "section_heading": "Agreement in restraint of trade",
            "text": "Every agreement in restraint of lawful trade is void.",
            "language": "en",
        },
    ]
    index = BM25Index()
    index.fit(duplicates)

    results = index.search("restraint of trade void", top_k=5)
    assert len(results) == 2
    # Both receive identical scores
    assert results[0].score == results[1].score
    # Deterministic secondary tie-breaker by provision_id ascending: DOC_DUP_A precedes DOC_DUP_B
    assert results[0].provision_id == "DOC_DUP_A"
    assert results[1].provision_id == "DOC_DUP_B"


def test_as_of_date_exact_enactment_date(sample_corpus):
    """
    Risk: Temporal logic on the exact day of enactment must consider the provision
    active (verified_in_force), whereas the day immediately prior must be verified_not_in_force.
    """
    labour_prov = sample_corpus[0]
    enactment = "2006-10-11"

    # Day before enactment -> verified_not_in_force
    status_before = resolve_provision_version_status(labour_prov, as_of_date="2006-10-10")
    assert status_before == "verified_not_in_force"

    # Exact enactment date -> verified_in_force
    status_exact = resolve_provision_version_status(labour_prov, as_of_date=enactment)
    assert status_exact == "verified_in_force"

    # Day after enactment -> verified_in_force
    status_after = resolve_provision_version_status(labour_prov, as_of_date="2006-10-12")
    assert status_after == "verified_in_force"


def test_as_of_date_exact_repeal_date(sample_corpus):
    """
    Risk: On the exact date of repeal, the provision is repealed and must return
    verified_not_in_force, whereas the day immediately prior must still be in force.
    """
    rent_prov = sample_corpus[1]
    repeal = "2020-01-01"

    # Day prior to repeal -> verified_in_force
    status_prior = resolve_provision_version_status(rent_prov, as_of_date="2019-12-31")
    assert status_prior == "verified_in_force"

    # Exact repeal date -> verified_not_in_force
    status_exact = resolve_provision_version_status(rent_prov, as_of_date=repeal)
    assert status_exact == "verified_not_in_force"

    # Well after repeal -> verified_not_in_force
    status_later = resolve_provision_version_status(rent_prov, as_of_date="2023-01-01")
    assert status_later == "verified_not_in_force"


def test_as_of_date_before_any_provision_enacted(sample_corpus):
    """
    Risk: Queries referencing historical dates prior to modern Bangladeshi statutory
    enactments (e.g. year 1800) must mark all provisions as verified_not_in_force.
    """
    for prov in sample_corpus:
        status_1800 = resolve_provision_version_status(prov, as_of_date="1800-01-01")
        assert status_1800 == "verified_not_in_force"


def test_bm25_search_annotates_version_status_accurately(sample_corpus):
    """
    Risk: BM25Index.search must propagate temporal version status into returned
    SearchResult instances based on provided as_of_date parameter.
    """
    index = BM25Index()
    index.fit(sample_corpus)

    # Historical query as of 2000-01-01:
    # ACT1991_S18 was enacted in 1991 and repealed in 2020 -> verified_in_force
    # ACT2006_S26 was enacted in 2006 -> verified_not_in_force
    results = index.search("employment notice eviction", top_k=5, as_of_date="2000-01-01")
    assert len(results) >= 2

    status_map = {r.provision_id: r.version_status for r in results}
    assert status_map["ACT1991_S18"] == "verified_in_force"
    assert status_map["ACT2006_S26"] == "verified_not_in_force"

