from __future__ import annotations

import json
import pathlib

import streamlit as st

from agents.root_agent import adk_runtime_status, run_live_adk_agent_sync
from tools.criteria_tools import application_pack_to_markdown, build_application_pack, semantic_match_available
from tools.ingestion_tools import extract_career_profile_from_file

ROOT = pathlib.Path(__file__).resolve().parent

st.set_page_config(page_title="GroundedApply", layout="wide")

st.title("GroundedApply")
st.caption("An evidence-grounded job application agent with live ADK/Gemini mode, MCP tools and security guardrails.")

with st.expander("Introduction and workflow guide"):
    st.markdown(
        """
        GroundedApply helps turn a job advert and your own evidence into a cautious, evidence-grounded
        application pack. It is designed to support drafting, not to invent experience or submit anything
        automatically.

        **How to use it**

        1. Paste the job advert or essential criteria on the left.
        2. Paste anonymised CV evidence, project notes or bullet points on the right, or upload a
           `.txt`, `.md` or `.pdf` CV/evidence file for local text extraction.
        3. Choose the draft tone, target role, run mode and evidence-matching mode in the sidebar.
        4. Click **Build application pack**.
        5. Review the tabs in order: criteria, evidence matches, draft answers, security review, ADK trace
           and advanced audit.

        **What each output tab means**

        - **Criteria**: requirements extracted from the job advert.
        - **Evidence matches**: which user-supplied evidence supports each criterion, with coverage labels.
        - **Draft answers**: draft text grounded in matched evidence.
        - **Security review**: PII redaction, prompt-injection warnings and unsupported-claim checks.
        - **ADK trace**: live Gemini/ADK runner output when live mode succeeds.
        - **Advanced audit**: raw structured data for debugging and capstone review.
        """
    )

sample_job = (ROOT / "examples" / "sample_job_advert.txt").read_text(encoding="utf-8")
sample_exp = (ROOT / "examples" / "sample_experience_bank.txt").read_text(encoding="utf-8")

if "experience_bank_text" not in st.session_state:
    st.session_state["experience_bank_text"] = sample_exp
if "uploaded_profile_fingerprint" not in st.session_state:
    st.session_state["uploaded_profile_fingerprint"] = None

with st.sidebar:
    st.header("Agent settings")
    tone = st.selectbox("Draft tone", ["professional", "concise"], index=0)
    st.caption("Controls the style of the generated draft answers.")
    target_role = st.text_input("Target role", "Data Analyst / Data Scientist")
    run_mode = st.radio("Run mode", ["Deterministic fallback", "Live ADK/Gemini"], index=0)
    st.caption(
        "Deterministic fallback is local and quota-free. Live ADK/Gemini uses the Google ADK runner "
        "and requires available Gemini quota."
    )
    matching_backend = st.radio(
        "Evidence matching",
        ["Local semantic rules", "Gemini semantic matcher"],
        index=1 if semantic_match_available() else 0,
    )
    st.caption(
        "Local rules are reproducible and private. Gemini semantic matcher is more flexible but uses API quota."
    )
    status = adk_runtime_status()
    st.subheader("Runtime status")
    st.caption(
        f"ADK installed: {status['adk_installed']} | "
        f"Gemini credentials: {status['has_gemini_credentials']} | "
        f"Model: {status['model']}"
    )

col1, col2 = st.columns(2)
with col1:
    st.subheader("Job advert / criteria")
    job_advert = st.text_area("Paste the job advert or essential criteria", sample_job, height=340)
with col2:
    st.subheader("Experience bank")
    uploaded_profile = st.file_uploader(
        "Optional: upload CV / evidence file",
        type=["txt", "md", "pdf"],
        help="Extracts text locally into the editable experience bank. Review and anonymise before using live Gemini mode.",
    )
    if uploaded_profile is not None:
        file_bytes = uploaded_profile.getvalue()
        fingerprint = (uploaded_profile.name, len(file_bytes))
        if st.session_state["uploaded_profile_fingerprint"] != fingerprint:
            try:
                extraction = extract_career_profile_from_file(uploaded_profile.name, file_bytes)
            except Exception as exc:
                st.error(f"Could not parse uploaded file: {exc}")
            else:
                if extraction["ok"]:
                    st.session_state["experience_bank_text"] = str(extraction["text"])
                    st.session_state["uploaded_profile_fingerprint"] = fingerprint
                    st.success(
                        f"Extracted {extraction.get('char_count', 0)} characters from {extraction['source_name']}."
                    )
                    if extraction.get("warning"):
                        st.warning(str(extraction["warning"]))
                else:
                    st.error(str(extraction["error"]))
    st.caption(
        "This text is treated as user-provided evidence. Edit it to remove sensitive details before building a pack."
    )
    experience_bank = st.text_area(
        "Paste anonymised CV evidence or bullet points",
        key="experience_bank_text",
        height=340,
    )

if st.button("Build application pack", type="primary"):
    matching_mode = "gemini" if matching_backend == "Gemini semantic matcher" else "local"
    pack = build_application_pack(
        job_advert,
        experience_bank,
        target_role=target_role,
        tone=tone,
        matching_mode=matching_mode,
    )
    markdown = application_pack_to_markdown(pack)
    adk_result = None

    if run_mode == "Live ADK/Gemini":
        try:
            with st.spinner("Running live ADK multi-agent workflow with Gemini..."):
                adk_result = run_live_adk_agent_sync(
                    job_advert,
                    experience_bank,
                    target_role=target_role,
                    tone=tone,
                    matching_mode=matching_mode,
                )
        except Exception as exc:
            st.warning(f"Live ADK/Gemini mode was not available: {exc}")

    st.success("Application pack generated. Review the security findings before using any draft text.")
    if pack.get("matching_info", {}).get("warning"):
        st.warning(pack["matching_info"]["warning"])

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Criteria",
            "Evidence matches",
            "Draft answers",
            "Markdown pack",
            "Security review",
            "ADK trace",
            "Advanced audit",
        ]
    )
    with tab1:
        st.dataframe(pack["criteria"], use_container_width=True)
    with tab2:
        st.caption(
            f"Matching mode: {pack.get('matching_info', {}).get('actual_mode', 'local')} "
            f"(requested: {pack.get('matching_info', {}).get('requested_mode', 'local')})"
        )
        flattened = []
        for match in pack["evidence_matches"]:
            flattened.append(
                {
                    "criterion_id": match["criterion_id"],
                    "coverage": match["coverage"],
                    "match_score": match["match_score"],
                    "matched_evidence_ids": ", ".join([e["evidence_id"] for e in match["matched_evidence"]]),
                    "semantic_rationale": " | ".join(
                        [
                            e.get("semantic_rationale", "")
                            for e in match["matched_evidence"]
                            if e.get("semantic_rationale")
                        ]
                    ),
                    "risk_note": match["risk_note"],
                }
            )
        st.dataframe(flattened, use_container_width=True)
    with tab3:
        for draft in pack["draft_answers"]:
            st.markdown(f"### {draft['criterion_id']}: {draft['coverage']} coverage")
            st.write(draft["answer"])
    with tab4:
        st.caption("This Markdown is generated from the same current run shown in the Criteria and Evidence tabs.")
        st.markdown(markdown)
    with tab5:
        security = pack["security_review"]
        st.caption(
            "Deterministic guardrails check privacy leakage, prompt injection and unsupported claims. "
            "Review these findings before using any draft text."
        )
        pii_counts = security.get("pii_redaction_counts", {})
        if pii_counts:
            st.warning("Personal information was detected and redacted before analysis.")
            st.dataframe(
                [{"type": label, "redactions": count} for label, count in pii_counts.items()],
                use_container_width=True,
            )
        else:
            st.success("No supported PII patterns were detected in the pasted input.")

        findings = security.get("findings", [])
        if findings:
            st.warning(f"{len(findings)} security or honesty finding(s) need review.")
            st.dataframe(
                [
                    {
                        "severity": finding.get("severity", ""),
                        "category": finding.get("category", ""),
                        "message": finding.get("message", ""),
                        "evidence": finding.get("evidence", ""),
                    }
                    for finding in findings
                ],
                use_container_width=True,
            )
        else:
            st.success("No prompt-injection or unsupported-claim findings from deterministic checks.")

        with st.expander("Safe input preview"):
            st.code(security.get("safe_input_preview", ""), language="text")
    with tab6:
        if adk_result:
            st.subheader("Live ADK/Gemini result")
            st.write(adk_result.get("final_text") or "No final text returned.")
            st.json(adk_result.get("events", []))
        else:
            st.info("Select Live ADK/Gemini mode and provide GOOGLE_API_KEY to show a real ADK runner trace.")
    with tab7:
        st.caption("Raw audit data for debugging, reproducibility and capstone review.")
        st.json(
            {
                "project": pack.get("project"),
                "target_role": pack.get("target_role"),
                "matching_info": pack.get("matching_info"),
                "counts": {
                    "criteria": len(pack.get("criteria", [])),
                    "evidence_items": len(pack.get("evidence", [])),
                    "matches": len(pack.get("evidence_matches", [])),
                    "draft_answers": len(pack.get("draft_answers", [])),
                    "security_findings": len(pack.get("security_review", {}).get("findings", [])),
                },
            }
        )
        with st.expander("Full JSON application pack"):
            st.code(json.dumps(pack, indent=2, ensure_ascii=False), language="json")

    st.download_button(
        label="Download Markdown application pack",
        data=markdown,
        file_name="groundedapply_application_pack.md",
        mime="text/markdown",
    )
