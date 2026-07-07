# GroundedApply

**An evidence-grounded job application agent built with Google ADK, Gemini, MCP tools, Streamlit and security guardrails.**

GroundedApply helps applicants compare a job advert against their own career evidence and produce a cautious, reviewable application pack. It extracts role criteria, maps them to explicit user-provided evidence, drafts criterion-by-criterion answers, and flags privacy or honesty risks before the user copies any text.

The project is intentionally local-first and transparent. A deterministic mode keeps the app testable without model credentials, while optional live ADK/Gemini modes demonstrate the real multi-agent path when a Google API key and quota are available.

## Highlights

- Four-agent ADK workflow: Criteria Parser -> Evidence Matcher -> Draft Writer -> Safety Reviewer.
- Streamlit app with local fallback, live ADK/Gemini mode and optional Gemini semantic matching.
- MCP server exposing the core analysis, drafting and security-review tools.
- CV/evidence upload for `.txt`, `.md` and `.pdf` files, parsed locally into an editable Experience bank.
- Security review for PII redaction, prompt injection and unsupported claims.
- Dockerfile, CLI, tests, threat model, reusable agent skill and capstone demo notes.

## What It Does

The user provides:

1. Job advert / essential criteria
2. User experience bank, ideally anonymised CV evidence or bullet points, pasted manually or extracted from an uploaded `.txt`, `.md` or `.pdf` CV/evidence file
3. Target role and tone

GroundedApply produces:

1. Extracted criteria table
2. Evidence mapping with coverage labels, using either local semantic rules or an optional Gemini semantic matcher
3. Draft criterion-by-criterion answers
4. Security review with privacy and honesty warnings
5. Markdown application pack for download or review

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local Streamlit URL, review the introduction panel, and build an application pack with the sample inputs.

## Why this is safe by design

GroundedApply is not designed to fabricate job applications. It uses explicit evidence from the user and flags weak or unsupported claims.

Security features include:

- redaction of emails, UK phone numbers, postcodes and profile URLs,
- local-only CV/evidence file text extraction with size/page/character limits,
- prompt-injection detection,
- unsupported-claim detection for over-strong phrases such as "extensive", "10 years", or direct NHS/cloud/team-management claims where evidence is missing.

Secure-agent lifecycle artifacts:

- `docs/threat_model.md`: STRIDE-style threat model and reviewer demo steps.
- `.agents/CONTEXT.md`: persistent secure-coding rules for future agent work.
- `.semgrep/rules.yaml`: local static checks for hardcoded Gemini keys and risky shell usage.
- `.pre-commit-config.yaml`: optional Semgrep pre-commit hook.

## Run the CLI

```bash
python main.py \
  --job examples/sample_job_advert.txt \
  --experience examples/sample_experience_bank.txt \
  --target-role "Data Analyst / Data Scientist" \
  --format markdown \
  --out outputs/application_pack.md
```

## Run tests

```bash
python -m pytest
```

If `pytest` is not installed in the active environment:

```bash
python -m pip install pytest
python -m pytest
```

## Run the MCP server

```bash
python -m mcp_server.server
```

The MCP server exposes tools such as:

- `analyze_job_advert`
- `analyze_experience_bank`
- `match_job_evidence`
- `build_job_application_pack`
- `build_job_application_markdown`
- `redact_personal_information`
- `detect_prompt_injection_text`
- `check_draft_claims`
- `run_full_security_review`

## Docker deployment

```bash
docker build -t groundedapply .
docker run -p 8501:8501 groundedapply
```

Then open `http://localhost:8501`.

## Optional Cloud Run deployment

```bash
gcloud run deploy groundedapply \
  --source . \
  --region europe-west2 \
  --allow-unauthenticated
```

## ADK notes

`agents/root_agent.py` builds a real ADK `SequentialAgent` when `google-adk` is installed. The Streamlit app can run this live Gemini-backed ADK path when `GOOGLE_API_KEY` is available. The deterministic backend remains available so the CLI, tests and Kaggle notebook still run without model credentials.

The ADK 2.0 lifecycle codelabs often describe graph-style workflows. GroundedApply's current runtime is a straight-line four-agent workflow, so `SequentialAgent` is the simplest stable implementation. `docs/adk_workflow_notes.md` maps it to the graph concepts used in the course and explains how to prove the live ADK path in the app.

To run the live ADK path:

```bash
export GOOGLE_API_KEY="your-api-key"  # Windows PowerShell: $env:GOOGLE_API_KEY="your-api-key"
python -m streamlit run app.py
```

Then select **Live ADK/Gemini** in the app sidebar and generate the application pack.

The app also includes an **Evidence matching** setting:

- **Local semantic rules**: reproducible, no API key required.
- **Gemini semantic matcher**: uses Gemini to judge criterion/evidence relationships more generally, then still grounds the draft in the user's explicit evidence.

If you add or update the Gemini matcher, reinstall dependencies:

```bash
python -m pip install -r requirements.txt
```

To inspect the ADK objects, open:

```text
agents/root_agent.py
agent.py
```

## Suggested video demo

Use `docs/demo_script.md`. Show these files in order:

1. `agents/root_agent.py`
2. `mcp_server/server.py`
3. `tools/security_tools.py`
4. `docs/threat_model.md`
5. `.agents/CONTEXT.md`
6. `skills/job_application_reviewer/SKILL.md`
7. `app.py` running locally
8. `Dockerfile`

## Repository layout

```text
groundedapply/
|-- agent.py
|-- app.py
|-- main.py
|-- Dockerfile
|-- requirements.txt
|-- agents/
|   `-- root_agent.py
|-- mcp_server/
|   `-- server.py
|-- tools/
|   |-- criteria_tools.py
|   |-- ingestion_tools.py
|   `-- security_tools.py
|-- skills/
|   `-- job_application_reviewer/
|       `-- SKILL.md
|-- examples/
|-- docs/
|   |-- adk_workflow_notes.md
|   `-- threat_model.md
|-- tests/
|-- .agents/
|-- .semgrep/
`-- .antigravity/
```

## Limitations

- The local matcher uses transparent semantic rules, not a full embedding retrieval model.
- Drafts should be reviewed by the applicant before use.
- The security checks are practical heuristics, not a guarantee.
- The running ADK path uses a stable `SequentialAgent`; `docs/adk_workflow_notes.md` maps it to the graph workflow pattern from the newer ADK lifecycle material.
- The project has room to grow, especially around richer retrieval, hosted deployment, stronger evaluation datasets and deeper document parsing.

## Capstone Notes

This project was built for the Kaggle Vibe Coding Agents Capstone. The closest submission track is **Concierge Agents**. It also has some overlap with **Agents for Good**, because the use case supports employability and career access.

The main capstone signals are:

| Signal | Where to look |
|---|---|
| ADK multi-agent workflow | `agents/root_agent.py`, `agent.py`, `docs/adk_workflow_notes.md` |
| MCP tools | `mcp_server/server.py` |
| Agent skill / Antigravity context | `skills/job_application_reviewer/SKILL.md`, `.antigravity/agents.md`, `.antigravity/skills.md` |
| Security and evaluation | `tools/security_tools.py`, `docs/threat_model.md`, `.agents/CONTEXT.md`, `.semgrep/rules.yaml`, `tests/test_tools.py` |
| CV/evidence ingestion | `tools/ingestion_tools.py`, `app.py` |
| Deployability | `app.py`, `Dockerfile`, `main.py`, `docs/deployment.md` |

A short demo should show the app running, an application pack being generated, the security review, the Markdown pack, and the live ADK/Gemini trace if quota is available.
