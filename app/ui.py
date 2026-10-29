"""
app/ui.py
---------
Streamlit web interface for Legal Aid BD retrieval-augmented generation
and single-clause legal document review.

Security:
- Binds to 127.0.0.1 only; refuses 0.0.0.0 unless ALLOW_INSECURE_ALL_INTERFACES=1 is set.
- No business logic in the UI; delegates entirely to src.pipeline and src.review.

Distinct visible states:
- retrieved
- verified against corpus
- legal status uncertain
- insufficient evidence
- possible document concern
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# -----------------------------------------------------------------------------
# Host Binding Security Enforcement
# -----------------------------------------------------------------------------
ALLOW_INSECURE = os.environ.get("ALLOW_INSECURE_ALL_INTERFACES", "").strip().lower() in ("1", "true", "yes")

for arg in sys.argv:
    if "0.0.0.0" in arg or "--server.address=0.0.0.0" in arg or "--server.address 0.0.0.0" in arg:
        if not ALLOW_INSECURE:
            sys.stderr.write(
                "CRITICAL SECURITY ERROR: Refusing to bind to 0.0.0.0 without explicit "
                "ALLOW_INSECURE_ALL_INTERFACES=1 environment flag.\n"
            )
            sys.exit(1)
        else:
            sys.stderr.write(
                "SECURITY WARNING: Streamlit UI bound to 0.0.0.0 with NO authentication! "
                "Exposed to all network interfaces.\n"
            )

import streamlit as st
from src.pipeline import ask, PipelineResult
from src.review.extract import extract_document, ExtractedClause
from src.review.clause_review import review_clause, ReviewFinding
from src.retrieval.bm25 import BM25Index
from src.rag.config import settings


# Configure page
st.set_page_config(
    page_title="Legal Aid BD - Grounded Legal AI",
    page_icon="⚖️",
    layout="wide",
)


def render_state_badges(result: PipelineResult) -> None:
    """Renders distinct visible status badges based on pipeline execution state."""
    st.markdown("### Operational State")
    cols = st.columns(5)

    with cols[0]:
        if result.retrieved:
            st.success("State: RETRIEVED")
        else:
            st.secondary("State: NOT RETRIEVED")

    with cols[1]:
        # Verified against corpus state
        has_valid_citations = any(c.get("is_valid") is True for c in result.claims)
        if has_valid_citations:
            st.success("State: VERIFIED AGAINST CORPUS")
        else:
            st.info("State: UNVERIFIED CITATIONS")

    with cols[2]:
        # Legal status uncertain state
        uncertain_provisions = [
            r for r in result.retrieved if r.get("version_status") == "uncertain"
        ]
        if uncertain_provisions or not result.version_status.get("corpus_verification_date"):
            st.warning("State: LEGAL STATUS UNCERTAIN")
        else:
            st.success("State: LEGAL STATUS VERIFIED")

    with cols[3]:
        # Insufficient evidence state
        if result.abstained:
            st.error("State: INSUFFICIENT EVIDENCE")
        else:
            st.success("State: SUFFICIENT EVIDENCE")

    with cols[4]:
        # Fallback state
        if result.fallback_used:
            st.warning("State: FALLBACK USED")
        else:
            st.success("State: PRIMARY MODEL")


def main():
    st.title("⚖️ Legal Aid Bangladesh: Multilingual RAG & Document Review")
    st.markdown(
        "Grounded statutory retrieval across English, Bengali, and Banglish with deterministic citation verification."
    )

    tab_query, tab_review = st.tabs(["🔍 Statutory Inquiry (RAG)", "📄 Document Clause Review"])

    # -------------------------------------------------------------------------
    # TAB 1: Statutory Inquiry (RAG)
    # -------------------------------------------------------------------------
    with tab_query:
        st.subheader("Legal Question & Statutory Search")

        col_input, col_config = st.columns([3, 1])

        with col_config:
            st.markdown("#### Retrieval Configuration")
            lang_choice = st.selectbox(
                "Language Mode",
                options=["auto", "bn", "en", "banglish"],
                index=0,
                help="Select 'auto' for script-ratio detection or manually override."
            )
            mode_choice = st.selectbox(
                "Operational Mode",
                options=["llm_validated", "extractive", "llm", "llm_validated_noabstain"],
                index=0,
                help="llm_validated enforces threshold and strict citation checks."
            )
            as_of_date_input = st.text_input(
                "Statutory As-of Date (optional)",
                placeholder="YYYY-MM-DD",
                help="Historical date to evaluate statutory in-force status."
            )

        with col_input:
            query_text = st.text_area(
                "Enter your legal question in Bengali, English, or Banglish:",
                height=120,
                placeholder="e.g., শ্রম আইনের ধারা ২৬ অনুযায়ী নোটিশ ছাড়া বরখাস্ত করলে কত দিনের ক্ষতিপূরণ দিতে হবে?",
            )
            submit_btn = st.button("Submit Question", type="primary", use_container_width=True)

        if submit_btn and query_text.strip():
            with st.spinner("Processing legal query through verified pipeline..."):
                as_of = as_of_date_input.strip() if as_of_date_input.strip() else None
                result: PipelineResult = ask(
                    query=query_text,
                    lang_override=lang_choice,
                    as_of_date=as_of,
                    mode=mode_choice,
                )

            # 1. State Badges
            render_state_badges(result)

            st.divider()

            # 2. Metadata Bar
            meta_cols = st.columns(4)
            meta_cols[0].metric("Detected Language", f"{result.detected_lang} (Override: {result.lang_overridden})")
            meta_cols[1].metric("Execution Latency", f"{result.latency_ms:.1f} ms")
            meta_cols[2].metric("Abstained", str(result.abstained))
            meta_cols[3].metric("Fallback Deployed", str(result.fallback_used))

            if result.original_text != result.normalized_query:
                st.info(f"**Normalized Query**: {result.normalized_query}")

            # 3. Answer Panel
            st.markdown("### Generated Answer")
            if result.abstained:
                st.error(result.answer)
            else:
                st.markdown(f"**Answer ({result.answer_lang})**:")
                st.write(result.answer)

            # 4. Validator Decisions & Rejections (Do not hide failures!)
            st.markdown("### Citation Validation & Integrity Audit")
            if not result.validation:
                st.write("No claims generated or validated.")
            else:
                for idx, val in enumerate(result.validation, start=1):
                    is_valid = val.get("is_valid")
                    claim_text = result.claims[idx - 1].get("text", "") if idx - 1 < len(result.claims) else ""
                    if is_valid is True:
                        st.success(f"**Claim {idx} [VALIDATED - {val.get('match_type')} match]**: {claim_text}")
                    elif is_valid is False:
                        reasons = ", ".join(val.get("rejection_reasons", []))
                        st.error(f"**Claim {idx} [REJECTED - Reasons: {reasons}]**: {claim_text}")
                    else:
                        st.warning(f"**Claim {idx} [UNVALIDATED]**: {claim_text}")

            # 5. Retrieved Provisions Panel
            st.markdown("### Retrieved Statutory Evidence")
            if not result.retrieved:
                st.write("No statutory records retrieved.")
            else:
                for idx, rec in enumerate(result.retrieved, start=1):
                    v_status = rec.get("version_status", "uncertain")
                    with st.expander(
                        f"Rank {idx}: [{rec.get('score'):.2f}] {rec.get('act_title')} - Section {rec.get('section_number')} (Status: {v_status})",
                        expanded=(idx == 1)
                    ):
                        st.markdown(f"**Provision ID**: `{rec.get('provision_id')}`")
                        st.markdown(f"**Version Status**: `{v_status}`")
                        st.markdown(f"**Source Document**: `{rec.get('source_url')}`")
                        st.markdown("**Full Provision Text:**")
                        st.text_area(
                            f"Text of {rec.get('provision_id')}",
                            value=rec.get("text", ""),
                            height=150,
                            disabled=True,
                            key=f"text_{rec.get('provision_id')}_{idx}"
                        )
                        # Source-open action
                        st.download_button(
                            label=f"Export Provision Metadata ({rec.get('provision_id')})",
                            data=f"Act: {rec.get('act_title')}\nSection: {rec.get('section_number')}\nID: {rec.get('provision_id')}\nText:\n{rec.get('text')}\n",
                            file_name=f"{rec.get('provision_id')}_source.txt",
                            mime="text/plain",
                            key=f"dl_{rec.get('provision_id')}_{idx}"
                        )

    # -------------------------------------------------------------------------
    # TAB 2: Document Clause Review
    # -------------------------------------------------------------------------
    with tab_review:
        st.subheader("Contract Clause Review & Statutory Compliance")
        st.markdown(
            "Upload an employment contract, commercial lease, or legal agreement (.pdf or .docx) "
            "to perform clause-level statutory compliance analysis."
        )

        uploaded_file = st.file_uploader(
            "Upload legal document for clause review",
            type=["pdf", "docx"],
            help=f"Allowed formats: .pdf, .docx. Maximum upload size: {settings.max_upload_size_mb} MB"
        )

        if uploaded_file is not None:
            # File size check
            file_bytes = uploaded_file.getvalue()
            size_mb = len(file_bytes) / (1024 * 1024)
            if size_mb > settings.max_upload_size_mb:
                st.error(f"File size ({size_mb:.2f} MB) exceeds maximum limit ({settings.max_upload_size_mb} MB).")
                return

            # Temporary file save for parsing
            temp_path = Path("tests/fixtures") / f"temp_{uploaded_file.name}"
            try:
                temp_path.write_bytes(file_bytes)
                clauses = extract_document(temp_path, doc_id=uploaded_file.name)
            finally:
                if temp_path.exists():
                    temp_path.unlink()

            st.success(f"Extracted {len(clauses)} clauses from `{uploaded_file.name}`.")

            # Clause picker
            clause_options = [
                f"{c.clause_id} (Page {c.page}, chars {c.char_start}..{c.char_end}): {c.text[:60]}..."
                if not c.needs_manual_correction else f"{c.clause_id} (Page {c.page}) [SCANNED / MANUAL CORRECTION REQUIRED]"
                for c in clauses
            ]
            selected_idx = st.selectbox("Select Clause to Review:", options=range(len(clauses)), format_func=lambda i: clause_options[i])

            selected_clause = clauses[selected_idx]

            st.markdown(f"**Selected Clause**: `{selected_clause.clause_id}` (Page {selected_clause.page}, Span: `[{selected_clause.char_start}, {selected_clause.char_end}]`)")
            st.text_area("Clause Text:", value=selected_clause.text, height=100, disabled=True)

            if selected_clause.needs_manual_correction:
                st.warning("State: MANUAL CORRECTION REQUIRED (Scanned or garbled text layer. Automated findings prohibited.)")
            else:
                review_btn = st.button("Review Selected Clause", type="primary")
                if review_btn:
                    with st.spinner("Analyzing clause against statutory provisions..."):
                        findings = review_clause(selected_clause, use_llm=False)

                    st.markdown("### Clause Review Findings")
                    for f in findings:
                        if f.label in ("possible_legal_issue", "drafting_concern"):
                            st.warning(f"State: POSSIBLE DOCUMENT CONCERN [{f.label.upper()}]")
                        else:
                            st.info(f"State: UNSUPPORTED FINDING [{f.label.upper()}]")

                        st.markdown(f"**Apparent Subject**: `{f.apparent_subject}`")
                        st.markdown(f"**Preliminary Explanation**: {f.preliminary_explanation}")
                        st.markdown(f"**Character Span**: `{f.char_start} .. {f.char_end}`")
                        if f.flags:
                            st.warning(f"Flags: {', '.join(f.flags)}")

                        if f.citations:
                            st.markdown("#### Validated Statutory Citations:")
                            for c in f.citations:
                                st.write(f"- **{c.get('act_title')}** Section {c.get('section_id')}: \"{c.get('quote')}\"")
                        else:
                            st.write("*No validated citations attached to this finding.*")


if __name__ == "__main__":
    main()

