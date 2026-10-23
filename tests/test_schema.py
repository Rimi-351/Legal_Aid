"""
tests/test_schema.py
--------------------
Automated test suite verifying the Legal Aid BD research data schema.

Covers the 8 mandatory Day 2 test requirements:
1. Every provision links to a valid document version and source.
2. Missing or invalid foreign-key references are rejected.
3. Unknown effective dates are supported.
4. Chunks reference valid provisions and retain location information when available.
5. Amendment relations reference valid instruments and affected provisions, with evidence recorded.
6. Benchmark cases support multilingual queries and explicit review status.
7. Duplicate identifiers and invalid required fields are handled correctly.
8. Bangla text survives serialization and deserialization without corruption.
"""

import unittest
import tempfile
import json
from pathlib import Path

from src.schema import (
    Source,
    Document,
    Version,
    Provision,
    Chunk,
    AmendmentRelation,
    BenchmarkCase,
    DocumentType,
    LegalDomain,
    Language,
    AmendmentType,
    ReviewStatus,
    SchemaValidationError,
    ForeignKeyError,
    DuplicateKeyError,
    TraceabilityError,
    LegalDataRegistry,
    Lineage,
)


class TestLegalDataSchema(unittest.TestCase):

    def setUp(self):
        """Set up standard fixtures representing real Bangladesh legal sources."""
        self.sample_sha256 = "4757a0e0e0bb60421c6c7214e7491e0f7c18071aabc483d5a9372fc378437739"
        self.sample_sha256_amend = "db74a202bd7d6fd44c60747120660306ff0596525f5e52d63d8bd7dba3a24588"

        self.registry = LegalDataRegistry()

        # Valid Source
        self.source = Source(
            source_id="SRC_BDLAWS_001",
            institution="Legislative and Parliamentary Affairs Division, Ministry of Law",
            url="http://bdlaws.minlaw.gov.bd/act-details-1016.html",
            access_method="manual_download",
            collection_date="2026-10-20",
        )
        self.registry.add_source(self.source)

        # Valid Document (Principal Act)
        self.doc_crpa = Document(
            doc_id="DOC_CRPA_2009",
            source_id="SRC_BDLAWS_001",
            title="ভোক্তা-অধিকার সংরক্ষণ আইন, ২০০৯",
            document_type=DocumentType.ACT,
            legal_domain=LegalDomain.CONSUMER,
            language=Language.BN,
            act_no="২০০৯ সনের ২৬ নং আইন",
        )
        self.registry.add_document(self.doc_crpa)

        # Valid Version
        self.version_crpa = Version(
            version_id="VER_CRPA_2009_ORIG",
            doc_id="DOC_CRPA_2009",
            checksum=self.sample_sha256,
            publication_date="২০০৯-০৪-০৬",
            effective_start_date=None,  # Unknown / immediate gazette
            version_label="Original Gazette Publication",
        )
        self.registry.add_version(self.version_crpa)

        # Valid Provision
        self.provision_s37 = Provision(
            provision_id="CRPA2009_S৩৭",
            version_id="VER_CRPA_2009_ORIG",
            act_id="DOC_CRPA_2009",
            section="৩৭",
            heading="পণ্যের মোড়ক ইত্যাদি ব্যবহার না করিবার দণ্ড",
            text="কোন ব্যক্তি কোন আইন বা বিধির অধীন নির্ধারিত বাধ্যবাধকতা অমান্য করিয়া কোন পণ্যের মোড়কে "
                 "খুচরা বিক্রয় মূল্য বা মেয়াদ উত্তীর্ণের তারিখ উল্লেখ না করিলে তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।",
            language="bn",
        )
        self.registry.add_provision(self.provision_s37)

    # -----------------------------------------------------------------
    # Test 1: Every provision links to a valid document version and source
    # -----------------------------------------------------------------
    def test_01_provision_traceability_to_version_and_source(self):
        """Acceptance Criterion: No provision can exist without a traceable document version and source."""
        lineage = self.registry.get_provision_lineage("CRPA2009_S৩৭")
        self.assertIsInstance(lineage, Lineage)
        self.assertEqual(lineage.provision.provision_id, "CRPA2009_S৩৭")
        self.assertEqual(lineage.version.version_id, "VER_CRPA_2009_ORIG")
        self.assertEqual(lineage.document.doc_id, "DOC_CRPA_2009")
        self.assertEqual(lineage.source.source_id, "SRC_BDLAWS_001")
        self.assertEqual(lineage.source.institution, "Legislative and Parliamentary Affairs Division, Ministry of Law")

        # Global audit passes
        is_valid, errors = self.registry.verify_all_provisions_traceable()
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    # -----------------------------------------------------------------
    # Test 2: Missing or invalid foreign-key references are rejected
    # -----------------------------------------------------------------
    def test_02_foreign_key_rejections(self):
        """Reject documents, versions, provisions, chunks, amendments, and benchmark cases with invalid FKs."""
        # 2a. Document with non-existent source
        invalid_doc = Document(
            doc_id="DOC_ORPHAN",
            source_id="SRC_NON_EXISTENT",
            title="Orphan Act",
            document_type=DocumentType.ACT,
            legal_domain=LegalDomain.GENERAL,
            language=Language.EN,
        )
        with self.assertRaises(ForeignKeyError) as ctx:
            self.registry.add_document(invalid_doc)
        self.assertIn("non-existent Source", str(ctx.exception))

        # 2b. Version with non-existent document
        invalid_version = Version(
            version_id="VER_ORPHAN",
            doc_id="DOC_NON_EXISTENT",
            checksum=self.sample_sha256,
        )
        with self.assertRaises(ForeignKeyError) as ctx:
            self.registry.add_version(invalid_version)
        self.assertIn("non-existent Document", str(ctx.exception))

        # 2c. Provision with non-existent version
        invalid_prov = Provision(
            provision_id="PROV_ORPHAN",
            version_id="VER_NON_EXISTENT",
            act_id="DOC_CRPA_2009",
            section="1",
            text="Some legal text",
        )
        with self.assertRaises(ForeignKeyError) as ctx:
            self.registry.add_provision(invalid_prov)
        self.assertIn("non-existent Version", str(ctx.exception))

        # 2d. Provision whose act_id does not match Version doc_id
        mismatched_prov = Provision(
            provision_id="PROV_MISMATCH",
            version_id="VER_CRPA_2009_ORIG",
            act_id="DOC_DIFFERENT_ACT",
            section="1",
            text="Some text",
        )
        with self.assertRaises(ForeignKeyError) as ctx:
            self.registry.add_provision(mismatched_prov)
        self.assertIn("does not match Version doc_id", str(ctx.exception))

        # 2e. Chunk with non-existent provision
        invalid_chunk = Chunk(
            chunk_id="CHK_ORPHAN",
            provision_id="PROV_NON_EXISTENT",
            text_span="Some span",
        )
        with self.assertRaises(ForeignKeyError) as ctx:
            self.registry.add_chunk(invalid_chunk)
        self.assertIn("non-existent Provision", str(ctx.exception))

        # 2f. Benchmark case with non-existent expected provision
        invalid_bm = BenchmarkCase(
            case_id="BM_INVALID",
            query="Where is the non-existent provision?",
            language=Language.EN,
            expected_provision_ids=["NON_EXISTENT_PROVISION_ID"],
            review_status=ReviewStatus.UNREVIEWED,
        )
        with self.assertRaises(ForeignKeyError) as ctx:
            self.registry.add_benchmark_case(invalid_bm)
        self.assertIn("non-existent expected Provision", str(ctx.exception))

    # -----------------------------------------------------------------
    # Test 3: Unknown effective dates are supported
    # -----------------------------------------------------------------
    def test_03_unknown_dates_supported_without_fabrication(self):
        """Unknown effective dates must be represented as None/null without inventing dates."""
        v = Version(
            version_id="VER_UNKNOWN_DATES",
            doc_id="DOC_CRPA_2009",
            checksum=self.sample_sha256,
            publication_date=None,
            effective_start_date=None,
            effective_end_date=None,
        )
        self.assertIsNone(v.publication_date)
        self.assertIsNone(v.effective_start_date)
        self.assertIsNone(v.effective_end_date)
        self.assertEqual(v.effective_dates["start"], None)
        self.assertEqual(v.effective_dates["end"], None)
        self.assertFalse(v.effective_dates["is_known"])

        # Dict export serializes to None/null
        d = v.to_dict()
        self.assertIsNone(d["publication_date"])
        self.assertIsNone(d["effective_start_date"])

        # Deserialization preserves None
        v2 = Version.from_dict(d)
        self.assertIsNone(v2.publication_date)
        self.assertIsNone(v2.effective_start_date)

    # -----------------------------------------------------------------
    # Test 4: Chunks reference valid provisions and retain location info
    # -----------------------------------------------------------------
    def test_04_chunks_location_info_and_validation(self):
        """Chunks reference valid provisions and retain location information when available."""
        # Chunk with complete location metadata
        chunk_full = Chunk(
            chunk_id="CHK_CRPA_S37_01",
            provision_id="CRPA2009_S৩৭",
            text_span="কোন ব্যক্তি কোন আইন বা বিধির অধীন নির্ধারিত বাধ্যবাধকতা অমান্য করিয়া...",
            char_start=0,
            char_end=75,
            page_number=12,
            paragraph_reference="অনুচ্ছেদ (১)",
        )
        self.registry.add_chunk(chunk_full)

        # Chunk with minimal location metadata (digital HTML source without pagination)
        chunk_min = Chunk(
            chunk_id="CHK_CRPA_S37_02",
            provision_id="CRPA2009_S৩৭",
            text_span="তিনি অনূর্ধ্ব এক বৎসর কারাদণ্ডে দণ্ডনীয় হইবেন।",
        )
        self.registry.add_chunk(chunk_min)

        # Lineage tracks chunks
        lineage = self.registry.get_provision_lineage("CRPA2009_S৩৭")
        self.assertEqual(len(lineage.chunks), 2)
        chunk_ids = {c.chunk_id for c in lineage.chunks}
        self.assertIn("CHK_CRPA_S37_01", chunk_ids)
        self.assertIn("CHK_CRPA_S37_02", chunk_ids)

        # Negative tests on chunk location
        with self.assertRaises(SchemaValidationError):
            Chunk(
                chunk_id="CHK_BAD_OFFSETS",
                provision_id="CRPA2009_S৩৭",
                text_span="Invalid span",
                char_start=50,
                char_end=20,  # char_end < char_start
            )

        with self.assertRaises(SchemaValidationError):
            Chunk(
                chunk_id="CHK_BAD_PAGE",
                provision_id="CRPA2009_S৩৭",
                text_span="Invalid page",
                page_number=0,  # page_number < 1
            )

    # -----------------------------------------------------------------
    # Test 5: Amendment relations with required supporting evidence
    # -----------------------------------------------------------------
    def test_05_amendment_relations_and_evidence(self):
        """Amendment relations reference valid instruments and provisions, requiring non-empty supporting evidence."""
        # Register Amending Act Document
        doc_amend = Document(
            doc_id="DOC_BLAA_2013",
            source_id="SRC_BDLAWS_001",
            title="বাংলাদেশ শ্রম (সংশোধন) আইন, ২০১৩",
            document_type=DocumentType.AMENDING_ACT,
            legal_domain=LegalDomain.LABOUR,
            language=Language.BN,
            act_no="২০১৩ সনের ৩০ নং আইন",
        )
        self.registry.add_document(doc_amend)

        # Register Amending Act Version
        ver_amend = Version(
            version_id="VER_BLAA_2013_ORIG",
            doc_id="DOC_BLAA_2013",
            checksum=self.sample_sha256_amend,
            publication_date="২০১৩-০৭-২২",
        )
        self.registry.add_version(ver_amend)

        # Valid Amendment Relation with explicit evidence
        valid_amendment = AmendmentRelation(
            relation_id="AMD_BLAA2013_CRPA_S37",
            amending_instrument_id="DOC_BLAA_2013",
            affected_provision_id="CRPA2009_S৩৭",
            amendment_type=AmendmentType.AMENDMENT,
            supporting_evidence="বাংলাদেশ গেজেট অতিরিক্ত, ২২ জুলাই ২০১৩, পৃষ্ঠা ৬১৮৪, ধারা ৩ মোতাবেক সংশোধিত।",
            effective_date="২০১৩-০৭-২২",
        )
        self.registry.add_amendment(valid_amendment)

        # Verify lineage tracks the amendment
        lineage = self.registry.get_provision_lineage("CRPA2009_S৩৭")
        self.assertEqual(len(lineage.amendments), 1)
        self.assertEqual(lineage.amendments[0].relation_id, "AMD_BLAA2013_CRPA_S37")

        # Negative Test: Inferred amendment relationship without supporting evidence must be rejected
        with self.assertRaises(SchemaValidationError) as ctx:
            AmendmentRelation(
                relation_id="AMD_UNSUPPORTED",
                amending_instrument_id="DOC_BLAA_2013",
                affected_provision_id="CRPA2009_S৩৭",
                supporting_evidence="",  # Empty evidence disallowed!
            )
        self.assertIn("supporting_evidence", str(ctx.exception))

        # Negative Test: Whitespace-only evidence disallowed
        with self.assertRaises(SchemaValidationError):
            AmendmentRelation(
                relation_id="AMD_WHITESPACE",
                amending_instrument_id="DOC_BLAA_2013",
                affected_provision_id="CRPA2009_S৩৭",
                supporting_evidence="   \n\t   ",
            )

        # Negative Test: Referencing non-existent amending instrument
        invalid_amend_fk = AmendmentRelation(
            relation_id="AMD_INVALID_DOC",
            amending_instrument_id="DOC_NON_EXISTENT_AMEND",
            affected_provision_id="CRPA2009_S৩৭",
            supporting_evidence="Valid citation string",
        )
        with self.assertRaises(ForeignKeyError):
            self.registry.add_amendment(invalid_amend_fk)

    # -----------------------------------------------------------------
    # Test 6: Benchmark cases support multilingual queries and explicit review status
    # -----------------------------------------------------------------
    def test_06_benchmark_cases_multilingual_and_review_tiers(self):
        """Benchmark cases support Bangla, English, Banglish and enforce explicit ReviewStatus."""
        # 6a. Bangla query with lawyer_reviewed tier
        case_bn = BenchmarkCase(
            case_id="BM_Q01_BN",
            query="দোকানদার পণ্যের গায়ে মেয়াদোত্তীর্ণের তারিখ না লিখে বিক্রি করলে কি শাস্তি হবে?",
            language=Language.BN,
            expected_provision_ids=["CRPA2009_S৩৭"],
            review_status=ReviewStatus.LAWYER_REVIEWED,
            scenario_id="SCENARIO_CRPA_01",
            reviewer_id="REV_ADV_001",
            reviewer_notes="Verified against Consumer Rights Protection Act, 2009 Section 37.",
        )
        self.registry.add_benchmark_case(case_bn)

        # 6b. Banglish query with researcher_reviewed tier
        case_banglish = BenchmarkCase(
            case_id="BM_Q01_BANGLISH",
            query="Dokandar expiry date na likhe ponno sell korle ki shasti hobe consumer rights law te?",
            language=Language.BANGLISH,
            expected_provision_ids=["CRPA2009_S৩৭"],
            review_status=ReviewStatus.RESEARCHER_REVIEWED,
            scenario_id="SCENARIO_CRPA_01",
        )
        self.registry.add_benchmark_case(case_banglish)

        # 6c. English query with unreviewed tier
        case_en = BenchmarkCase(
            case_id="BM_Q01_EN",
            query="What is the penalty if a seller sells goods without expiration date on packaging?",
            language=Language.EN,
            expected_provision_ids=["CRPA2009_S৩৭"],
            review_status=ReviewStatus.UNREVIEWED,
            scenario_id="SCENARIO_CRPA_01",
        )
        self.registry.add_benchmark_case(case_en)

        self.assertEqual(len(self.registry.benchmark_cases), 3)

        # Negative Test: Arbitrary or fabricated review status is rejected
        with self.assertRaises(SchemaValidationError) as ctx:
            BenchmarkCase(
                case_id="BM_INVALID_STATUS",
                query="Sample query",
                language=Language.EN,
                expected_provision_ids=["CRPA2009_S৩৭"],
                review_status="provisional_guess",  # Disallowed
            )
        self.assertIn("review_status", str(ctx.exception))

        # Negative Test: Empty expected_provision_ids is rejected
        with self.assertRaises(SchemaValidationError):
            BenchmarkCase(
                case_id="BM_EMPTY_EXPECTED",
                query="Sample query",
                language=Language.EN,
                expected_provision_ids=[],  # Must have at least one target
                review_status=ReviewStatus.UNREVIEWED,
            )

    # -----------------------------------------------------------------
    # Test 7: Duplicate identifiers and invalid required fields
    # -----------------------------------------------------------------
    def test_07_duplicate_identifiers_and_empty_required_fields(self):
        """Duplicate identifiers and invalid required fields are rejected."""
        # 7a. Duplicate Source ID
        dup_source = Source(
            source_id="SRC_BDLAWS_001",  # Duplicate!
            institution="Different Institution",
        )
        with self.assertRaises(DuplicateKeyError):
            self.registry.add_source(dup_source)

        # 7b. Duplicate Provision ID
        dup_prov = Provision(
            provision_id="CRPA2009_S৩৭",  # Duplicate!
            version_id="VER_CRPA_2009_ORIG",
            act_id="DOC_CRPA_2009",
            section="৩৭",
            text="Duplicate provision text",
        )
        with self.assertRaises(DuplicateKeyError):
            self.registry.add_provision(dup_prov)

        # 7c. Empty required fields
        with self.assertRaises(SchemaValidationError):
            Source(source_id="", institution="Valid Institution")

        with self.assertRaises(SchemaValidationError):
            Document(
                doc_id="DOC_EMPTY_TITLE",
                source_id="SRC_BDLAWS_001",
                title="",  # Empty title
                document_type=DocumentType.ACT,
                legal_domain=LegalDomain.CONTRACT,
                language=Language.BN,
            )

        with self.assertRaises(SchemaValidationError):
            Provision(
                provision_id="PROV_EMPTY_TEXT",
                version_id="VER_CRPA_2009_ORIG",
                act_id="DOC_CRPA_2009",
                section="1",
                text="",  # Empty text
            )

        # 7d. Invalid SHA-256 Checksum
        with self.assertRaises(SchemaValidationError):
            Version(
                version_id="VER_BAD_HASH",
                doc_id="DOC_CRPA_2009",
                checksum="not_a_valid_64_character_hex_hash",  # Invalid checksum
            )

    # -----------------------------------------------------------------
    # Test 8: Bangla text survives serialization and deserialization
    # -----------------------------------------------------------------
    def test_08_bangla_unicode_serialization_integrity(self):
        """Bangla and Banglish text survives JSON and JSONL round-trips without mojibake or ASCII corruption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Export registry to JSONL directory
            self.registry.export_jsonl(tmppath)

            # Inspect the raw JSONL files to ensure Bangla is NOT ASCII-escaped (\u09xx)
            doc_file = tmppath / "documents.jsonl"
            self.assertTrue(doc_file.exists())
            raw_doc_content = doc_file.read_text(encoding="utf-8")
            self.assertIn(self.doc_crpa.title, raw_doc_content)
            self.assertNotIn("\\u09", raw_doc_content)  # Must be raw Unicode, not escaped

            prov_file = tmppath / "provisions.jsonl"
            self.assertTrue(prov_file.exists())
            raw_prov_content = prov_file.read_text(encoding="utf-8")
            self.assertIn(self.provision_s37.heading, raw_prov_content)
            self.assertNotIn("\\u09", raw_prov_content)  # Must be raw Unicode, not escaped

            # Re-import into a fresh registry
            reimported = LegalDataRegistry.import_jsonl(tmppath)

            # Verify identical count
            self.assertEqual(len(reimported.sources), len(self.registry.sources))
            self.assertEqual(len(reimported.documents), len(self.registry.documents))
            self.assertEqual(len(reimported.versions), len(self.registry.versions))
            self.assertEqual(len(reimported.provisions), len(self.registry.provisions))

            # Character-for-character comparison of Bangla text and conjuncts
            orig_p = self.registry.provisions["CRPA2009_S৩৭"]
            reimp_p = reimported.provisions["CRPA2009_S৩৭"]

            self.assertEqual(orig_p.provision_id, reimp_p.provision_id)
            self.assertEqual(orig_p.heading, reimp_p.heading)
            self.assertEqual(orig_p.text, reimp_p.text)
            self.assertEqual(orig_p.section, reimp_p.section)

            # Test dictionary round-trip
            d = self.registry.to_dict()
            reimported_from_dict = LegalDataRegistry.from_dict(d)
            self.assertEqual(
                reimported_from_dict.provisions["CRPA2009_S৩৭"].text,
                orig_p.text
            )


if __name__ == "__main__":
    unittest.main()
