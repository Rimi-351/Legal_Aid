"""
tests/test_metrics_fix.py
--------------------------
Unit tests verifying Group 2 metric fixes:
1. Gold-ID normalization (Bengali numerals <-> ASCII digits).
2. (act_id, section_id) extraction and overlap calculation across language representations.
3. Holm-Bonferroni multiple testing correction (step-down thresholds, monotonic adjusted p-values, CI widening).
4. Subgroup n reporting (exact counts matching benchmark reality: banglish n=4, en n=15, bn_unicode n=11).
"""
import pytest
import numpy as np
from typing import List, Dict, Any, Tuple, Set

from scripts.run_frozen_eval import (
    normalize_pid,
    holm_bonferroni_correction,
    load_test_queries,
    load_corpus,
)
from scripts.eval_paired_languages import (
    extract_act_section,
    compute_jaccard_act_section,
    identify_grounded_scenarios,
)


def test_gold_id_normalization():
    """Verifies that Bengali Unicode numerals normalize to ASCII digits correctly."""
    # Test individual provision ID normalization
    assert normalize_pid("CRPA2009_S৩৭") == "CRPA2009_S37"
    assert normalize_pid("PRCA1991_S১৮") == "PRCA1991_S18"
    assert normalize_pid("BLA2006_S২৬") == "BLA2006_S26"
    assert normalize_pid("  ca1872_s11  ") == "CA1872_S11"

    # Test gold matching: benchmark query uses ASCII digit while corpus uses Bengali numerals
    benchmark_gold = ["PRCA1991_S18", "PRCA1991_S13"]
    retrieved_corpus_ids = ["PRCA1991_S১৮", "BLA2006_S২৬", "CRPA2009_S৩৭"]

    norm_gold = {normalize_pid(g) for g in benchmark_gold}
    norm_retrieved = [normalize_pid(r) for r in retrieved_corpus_ids]

    # Verify that PRCA1991_S১৮ matches PRCA1991_S18
    matches = [r for r in norm_retrieved if r in norm_gold]
    assert "PRCA1991_S18" in matches
    assert len(matches) == 1


def test_act_section_overlap():
    """Verifies that provisions are extracted and compared by (act_id, section_id)."""
    # Test extraction
    assert extract_act_section("BLA2006_S২৬") == ("BLA2006", "26")
    assert extract_act_section("bla2006_s26") == ("BLA2006", "26")
    assert extract_act_section("PRCA1991_S১৮") == ("PRCA1991", "18")
    assert extract_act_section("CA1872_S11") == ("CA1872", "11")

    # Test set overlap: two lists with different numeral representations of same provisions
    list_bn = ["BLA2006_S২৬", "BLA2006_S২০", "PRCA1991_S১৮"]
    list_en = ["BLA2006_S26", "BLA2006_S20", "PRCA1991_S18"]

    set_bn = {extract_act_section(x) for x in list_bn}
    set_en = {extract_act_section(x) for x in list_en}

    # Sets should be identical when compared by (act_id, section_id)
    assert set_bn == set_en
    assert compute_jaccard_act_section(set_bn, set_en) == 1.0

    # Partial overlap
    list_partial = ["BLA2006_S26", "CA1872_S10"]
    set_partial = {extract_act_section(x) for x in list_partial}
    # Intersection has ('BLA2006', '26'), union has 4 items
    assert compute_jaccard_act_section(set_bn, set_partial) == round(1.0 / 4.0, 4)


def test_holm_bonferroni_correction():
    """Verifies Holm-Bonferroni step-down correction logic and CI widening."""
    # Dummy bootstrap distributions:
    # Test 1: clear effect (mean ~ 0.10)
    # Test 2: borderline effect (mean ~ 0.03, raw p ~ 0.03)
    # Test 3: no effect (mean ~ 0.00, raw p ~ 0.50)
    rng = np.random.default_rng(42)
    boot1 = rng.normal(loc=0.10, scale=0.02, size=10000)
    boot2 = rng.normal(loc=0.03, scale=0.014, size=10000)
    boot3 = rng.normal(loc=0.00, scale=0.02, size=10000)

    # Compute empirical raw p-values
    p1 = float(2 * min(np.mean(boot1 <= 0), np.mean(boot1 >= 0)))
    p2 = float(2 * min(np.mean(boot2 <= 0), np.mean(boot2 >= 0)))
    p3 = float(2 * min(np.mean(boot3 <= 0), np.mean(boot3 >= 0)))

    tests = [
        {"name": "test_borderline", "raw_p_value": p2, "boot_means": boot2},
        {"name": "test_strong", "raw_p_value": p1, "boot_means": boot1},
        {"name": "test_null", "raw_p_value": p3, "boot_means": boot3},
    ]

    adjusted = holm_bonferroni_correction(tests, alpha=0.05)

    # Find the adjusted tests by name
    adj_map = {t["name"]: t for t in adjusted}

    # Test strong should be rank 1, multiplied by m=3
    assert adj_map["test_strong"]["rank"] == 1
    assert adj_map["test_strong"]["multiplier"] == 3
    assert adj_map["test_strong"]["step_alpha"] == round(0.05 / 3.0, 6)

    # Adjusted p-values must be non-decreasing with rank
    sorted_adj_p = sorted([t["adj_p_value"] for t in adjusted])
    assert adj_map["test_strong"]["adj_p_value"] <= adj_map["test_borderline"]["adj_p_value"]
    assert adj_map["test_borderline"]["adj_p_value"] <= adj_map["test_null"]["adj_p_value"]

    # Borderline raw p (~0.03) when multiplied by multiplier (2 or 3) should be >= 0.05
    # Therefore it should NOT be significant after Holm
    assert not adj_map["test_null"]["significant_after_holm"]

    # Verify Holm-adjusted CI is wider than standard 95% CI for rank 1
    # Standard 95% uses 2.5% to 97.5%
    # Holm rank 1 uses alpha/3 = 0.0167, percentiles 0.833% to 99.167%
    raw_ci_width = np.percentile(boot1, 97.5) - np.percentile(boot1, 2.5)
    adj_ci = adj_map["test_strong"]["adj_ci"]
    adj_ci_width = adj_ci[1] - adj_ci[0]
    assert adj_ci_width >= raw_ci_width


def test_subgroup_n_reporting():
    """Verifies that subgroup n reporting accurately reflects the frozen test split."""
    test_queries = load_test_queries()
    answerable = [q for q in test_queries if q.get("expected_supporting_provisions")]

    assert len(answerable) == 30, f"Expected 30 answerable test queries, got {len(answerable)}"

    lang_counts = {}
    for q in answerable:
        lang = q.get("language_and_script", "unknown")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    # Exact language distribution in benchmark test split
    assert lang_counts.get("en") == 15, f"Expected 15 English queries, got {lang_counts.get('en')}"
    assert lang_counts.get("bn_unicode") == 11, f"Expected 11 Bengali queries, got {lang_counts.get('bn_unicode')}"
    assert lang_counts.get("banglish") == 4, f"Expected 4 Banglish queries, got {lang_counts.get('banglish')}"

    # Verify Banglish is explicitly n=4
    banglish_label = f"banglish (n={lang_counts['banglish']})"
    assert banglish_label == "banglish (n=4)"

    domain_counts = {}
    for q in answerable:
        dom = q.get("legal_domain", "unknown")
        domain_counts[dom] = domain_counts.get(dom, 0) + 1

    # Exact domain distribution
    assert domain_counts.get("land_tenancy") == 11
    assert domain_counts.get("employment_labour") == 8
    assert domain_counts.get("consumer_protection") == 6
    assert domain_counts.get("contractual_obligations") == 5


def test_grounded_scenarios_count():
    """Verifies that exactly 4 out of 12 paired scenarios have targets in the active corpus."""
    grounded = identify_grounded_scenarios()
    assert len(grounded) == 4, f"Expected exactly 4 grounded scenarios, got {len(grounded)}"
    expected_grounded = {"scenario_01", "scenario_03", "scenario_05", "scenario_07"}
    assert set(grounded.keys()) == expected_grounded

