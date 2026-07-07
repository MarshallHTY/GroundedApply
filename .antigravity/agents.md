# Antigravity Agent Notes

Use this repository as a capstone demo project for a deployable job application agent.

Recommended Antigravity workflow:
1. Inspect `README.md` and `docs/submission_checklist.md`.
2. Run `pytest` to verify deterministic tools.
3. Run `python -m streamlit run app.py` for the local demo.
4. Inspect `agents/root_agent.py` for ADK multi-agent orchestration.
5. Inspect `mcp_server/server.py` for MCP tools.
6. Use `skills/job_application_reviewer/SKILL.md` when modifying career-advice logic.

Development rule: do not add features that invent job-application evidence.
