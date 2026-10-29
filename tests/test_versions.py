"""
tests/test_versions.py
-----------------------
Pytest suite verifying Week 6 Phase 1 Track A temporal versioning gates:
1. Unknown effective date -> 'uncertain'
2. as_of before enactment -> 'verified_not_in_force'
3. Repealed before as_of -> 'verified_not_in_force'
4. Conflicting metadata -> 'uncertain'
5. No verified evidence -> qualified response ("legal status as of <date> cannot be established")
6. Exit gate: no response claims "as of <date>" unless every cited provision is verified_*
"""
import unittest
from pathlib import Path
from typing import Dict, Any

from src.retrieval.temporal import (
    resolve_provision_version_status,
    parse_date_string,
    get_corpus_verification_date,
    check_temporal_qualification,
)
from src.rag.api import ask_legal, AskRequest, AskResponse


class TestTemporalVersioning(unittest.TestCase):

    def setUp(self):
        # Base official, verified provision template
        self.verified_provision = {
            "provision_id": "BLA2006_S26",
            "act_title": "Bangladesh Labour Act, 2006",
            "section_number": "26",
            "enactment_date": "2006-10-11",
            "effective_date": "2006-10-11",
            "relation": "none",
            "evidence_type": "official",
            "review_status": "verified",
            "conflict_note": "",
            "is_quarantined": False,
        }

    def test_unknown_effective_date_yields_uncertain(self):
        """Rule: Missing or unknown effective/enactment date must evaluate to uncertain."""
        prov = dict(self.verified_provision)
        prov["effective_date"] = None
        prov["enactment_date"] = ""
        status = resolve_provision_version_status(prov, as_of_date="2020-01-01")
        self.assertEqual(status, "uncertain")

        # Inferred or unverified status must also be uncertain even if date is present
        unverified_prov = dict(self.verified_provision)
        unverified_prov["review_status"] = "pending"
        status2 = resolve_provision_version_status(unverified_prov, as_of_date="2020-01-01")
        self.assertEqual(status2, "uncertain")

    def test_as_of_before_enactment_yields_verified_not_in_force(self):
        """Rule: as_of_date prior to enactment/commencement must evaluate to verified_not_in_force."""
        prov = dict(self.verified_provision)
        status = resolve_provision_version_status(prov, as_of_date="2000-01-01")
        self.assertEqual(status, "verified_not_in_force")

        # When as_of_date is after enactment -> verified_in_force
        status_after = resolve_provision_version_status(prov, as_of_date="2010-01-01")
        self.assertEqual(status_after, "verified_in_force")

    def test_repealed_before_as_of_yields_verified_not_in_force(self):
        """Rule: Provision repealed or replaced prior to as_of_date must evaluate to verified_not_in_force."""
        prov = dict(self.verified_provision)
        prov["relation"] = "repeal"
        prov["repeal_date"] = "2013-07-22"

        # as_of after repeal
        status_after_repeal = resolve_provision_version_status(prov, as_of_date="2015-01-01")
        self.assertEqual(status_after_repeal, "verified_not_in_force")

        # as_of before repeal
        status_before_repeal = resolve_provision_version_status(prov, as_of_date="2010-01-01")
        self.assertEqual(status_before_repeal, "verified_in_force")

    def test_conflicting_metadata_yields_uncertain(self):
        """Rule: Conflicting amendment notes or quarantine status forces uncertain."""
        prov = dict(self.verified_provision)
        prov["conflict_note"] = "Conflicting amendment dates across Gazette notices"
        status = resolve_provision_version_status(prov, as_of_date="2020-01-01")
        self.assertEqual(status, "uncertain")

        # Quarantine flag forces uncertain
        prov2 = dict(self.verified_provision)
        prov2["is_quarantined"] = True
        status2 = resolve_provision_version_status(prov2, as_of_date="2020-01-01")
        self.assertEqual(status2, "uncertain")

    def test_no_verified_evidence_triggers_qualified_response(self):
        """
        Rule: If as_of_date is given and no cited provision is verified,
        the response must be qualified: 'legal status as of <date> cannot be established'.
        """
        # All fixture corpus provisions currently have evidence_type=unknown / review_status=pending
        req = AskRequest(
            query="What is the compensation for termination under Section 26?",
            lang="en",
            mode="extractive",
            as_of_date="2015-05-01",
        )
        resp = ask_legal(req)
        self.assertTrue(resp.abstained)
        self.assertIn("legal status as of 2015-05-01 cannot be established", resp.answer.lower())
        self.assertEqual(len(resp.claims), 0)

    def test_exit_gate_no_response_claims_as_of_without_verified_evidence(self):
        """
        Exit Gate: No response may claim 'as of <date>' unless every cited provision is verified_*.
        """
        # Test helper function directly
        cited_unverified = [{"provision_id": "P1", "version_status": "uncertain"}]
        is_unverified, text = check_temporal_qualification("2020-01-01", cited_unverified)
        self.assertTrue(is_unverified)
        self.assertEqual(text, "Legal status as of 2020-01-01 cannot be established.")

        # With verified provisions
        cited_verified = [{"provision_id": "P1", "version_status": "verified_in_force"}]
        is_unverified_2, _ = check_temporal_qualification("2020-01-01", cited_verified)
        self.assertFalse(is_unverified_2)


if __name__ == "__main__":
    unittest.main()

