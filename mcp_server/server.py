"""MCP server for GroundedApply.

Run locally with:
    python -m mcp_server.server

The tools are deterministic wrappers around the same functions used by the app
and CLI. This keeps the agent auditable and makes the MCP integration easy to
inspect for capstone review.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Dict

# Allow `python mcp_server/server.py` from project root.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.criteria_tools import (  # noqa: E402
    build_application_pack,
    parse_criteria,
    parse_experience_bank,
    match_evidence,
    application_pack_to_markdown,
)
from tools.security_tools import (  # noqa: E402
    redact_pii,
    detect_prompt_injection,
    check_unsupported_claims,
    run_security_review,
)

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - package may not be installed in notebook preview
    FastMCP = None


if FastMCP:
    mcp = FastMCP("groundedapply")
else:
    mcp = None


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


if mcp:

    @mcp.tool()
    def analyze_job_advert(job_advert: str) -> str:
        """Extract job criteria from a job advert or essential-criteria block."""
        return _json(parse_criteria(job_advert))

    @mcp.tool()
    def analyze_experience_bank(experience_bank: str) -> str:
        """Parse user-provided experience into auditable evidence items."""
        return _json(parse_experience_bank(experience_bank))

    @mcp.tool()
    def match_job_evidence(job_advert: str, experience_bank: str, matching_mode: str = "local") -> str:
        """Map job criteria to explicit user evidence."""
        criteria = parse_criteria(job_advert)
        evidence = parse_experience_bank(experience_bank)
        return _json(match_evidence(criteria, evidence, matching_mode=matching_mode))

    @mcp.tool()
    def build_job_application_pack(job_advert: str, experience_bank: str, target_role: str = "Target role", tone: str = "professional", matching_mode: str = "local") -> str:
        """Build a full application pack with criteria, evidence, draft answers and safety review."""
        return _json(build_application_pack(job_advert, experience_bank, target_role, tone, matching_mode=matching_mode))

    @mcp.tool()
    def build_job_application_markdown(job_advert: str, experience_bank: str, target_role: str = "Target role", tone: str = "professional", matching_mode: str = "local") -> str:
        """Build a Markdown application pack suitable for review or download."""
        pack = build_application_pack(job_advert, experience_bank, target_role, tone, matching_mode=matching_mode)
        return application_pack_to_markdown(pack)

    @mcp.tool()
    def redact_personal_information(text: str) -> str:
        """Redact emails, UK phone numbers, postcodes and common profile URLs."""
        return _json(redact_pii(text))

    @mcp.tool()
    def detect_prompt_injection_text(text: str) -> str:
        """Detect suspicious prompt-injection or fabrication instructions."""
        return _json(detect_prompt_injection(text))

    @mcp.tool()
    def check_draft_claims(draft: str, evidence_bank: str) -> str:
        """Flag potentially unsupported claims in a draft answer."""
        return _json(check_unsupported_claims(draft, evidence_bank))

    @mcp.tool()
    def run_full_security_review(job_advert: str, experience_bank: str, draft: str = "") -> str:
        """Run PII, prompt-injection and unsupported-claim checks."""
        return _json(run_security_review(job_advert, experience_bank, draft))


def main() -> None:
    if not mcp:
        print("The 'mcp' package is not installed. Install with: pip install mcp")
        raise SystemExit(1)
    mcp.run()


if __name__ == "__main__":
    main()
