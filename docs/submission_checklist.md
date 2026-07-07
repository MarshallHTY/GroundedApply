# Capstone Submission Checklist

| Requirement / judging signal | Where it is covered |
|---|---|
| Agent / multi-agent system using ADK | `agents/root_agent.py` defines an ADK `SequentialAgent` with Criteria Parser, Evidence Matcher, Draft Writer and Safety Reviewer sub-agents. The Streamlit app can run this live through ADK `Runner` when `GOOGLE_API_KEY` is set. Root-level `agent.py` exposes `root_agent`. `docs/adk_workflow_notes.md` maps the straight-line runtime to the graph workflow concepts from the ADK lifecycle material. |
| MCP Server | `mcp_server/server.py` exposes MCP tools for job-advert analysis, evidence matching, application-pack generation and safety checks. |
| Antigravity | `.antigravity/agents.md`, `.antigravity/skills.md`, and `skills/job_application_reviewer/SKILL.md`; record a video showing the project running in Antigravity. |
| Security features | `tools/security_tools.py`: PII redaction, prompt-injection detection and unsupported-claim checking. `docs/threat_model.md`, `.agents/CONTEXT.md`, `.semgrep/rules.yaml` and `.pre-commit-config.yaml` demonstrate secure-agent lifecycle controls. |
| User-controlled file ingestion | `tools/ingestion_tools.py` and `app.py` support local CV/evidence upload into an editable experience bank before analysis. |
| Deployability | `app.py` Streamlit interface, `Dockerfile`, CLI `main.py`, and README deployment commands. |
| Agent skills | `skills/job_application_reviewer/SKILL.md` defines a reusable job-application-reviewer skill. |

## Suggested Kaggle writeup wording

GroundedApply is a privacy-aware job-application agent for UK-style criterion-by-criterion applications. It uses a fixed live ADK multi-agent workflow to extract job requirements, match them to user-provided evidence, draft cautious answers, and run security checks. The system intentionally avoids inventing experience and flags weak evidence, PII and prompt-injection attempts.

## Minimal evidence for recording

1. Show repository structure.
2. Open `agents/root_agent.py` and point to the `SequentialAgent`.
3. Open `docs/adk_workflow_notes.md` and show the graph mapping.
4. Open `mcp_server/server.py` and point to MCP tools.
5. Open `docs/threat_model.md` and `.agents/CONTEXT.md`.
6. Run `python -m streamlit run app.py`.
7. Show the sidebar ADK status and select Live ADK/Gemini if `GOOGLE_API_KEY` is available.
8. Generate an application pack using the sample inputs.
9. Upload a small `.txt` or `.pdf` CV/evidence file and show that it populates the editable Experience bank.
10. Paste a prompt-injection phrase and show the security warning.
11. Run Docker build or show the Dockerfile.
12. Open `skills/job_application_reviewer/SKILL.md`.
