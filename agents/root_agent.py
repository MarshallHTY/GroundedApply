"""ADK multi-agent definition and live runner for GroundedApply.

The repository stays runnable without model credentials, but when google-adk
and GOOGLE_API_KEY are available this module can execute the real ADK
SequentialAgent with Gemini through Runner and InMemorySessionService.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

from tools.criteria_tools import application_pack_to_markdown, build_application_pack

APP_NAME = "groundedapply"
DEFAULT_MODEL = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")


def extract_criteria_tool(job_advert: str) -> Dict[str, Any]:
    """Extract job criteria from the job advert."""
    from tools.criteria_tools import parse_criteria

    return {"criteria": parse_criteria(job_advert)}


def match_evidence_tool(job_advert: str, experience_bank: str, matching_mode: str = "local") -> Dict[str, Any]:
    """Match job criteria to explicit user evidence."""
    from tools.criteria_tools import match_evidence, parse_criteria, parse_experience_bank

    criteria = parse_criteria(job_advert)
    evidence = parse_experience_bank(experience_bank)
    return {"evidence_matches": match_evidence(criteria, evidence, matching_mode=matching_mode)}


def draft_answers_tool(
    job_advert: str,
    experience_bank: str,
    target_role: str = "Target role",
    tone: str = "professional",
    matching_mode: str = "local",
) -> Dict[str, Any]:
    """Draft answers grounded in the matched evidence."""
    pack = build_application_pack(job_advert, experience_bank, target_role, tone, matching_mode=matching_mode)
    return {"draft_answers": pack["draft_answers"]}


def safety_review_tool(job_advert: str, experience_bank: str, draft: str = "") -> Dict[str, Any]:
    """Run privacy, prompt-injection and unsupported-claim checks."""
    from tools.security_tools import run_security_review

    return run_security_review(job_advert, experience_bank, draft)


def build_markdown_pack_tool(
    job_advert: str,
    experience_bank: str,
    target_role: str = "Target role",
    tone: str = "professional",
    matching_mode: str = "local",
) -> Dict[str, str]:
    """Build the final Markdown application pack using deterministic tools."""
    pack = build_application_pack(job_advert, experience_bank, target_role, tone, matching_mode=matching_mode)
    return {"markdown_application_pack": application_pack_to_markdown(pack)}


@dataclass
class DeterministicJobApplicationPipeline:
    """Fallback runner used for demos/tests when ADK runtime is unavailable."""

    name: str = "GroundedApply_Deterministic_Fallback"

    def run(
        self,
        job_advert: str,
        experience_bank: str,
        target_role: str = "Target role",
        tone: str = "professional",
        matching_mode: str = "local",
    ) -> Dict[str, Any]:
        return build_application_pack(job_advert, experience_bank, target_role, tone, matching_mode=matching_mode)

    def run_markdown(
        self,
        job_advert: str,
        experience_bank: str,
        target_role: str = "Target role",
        tone: str = "professional",
        matching_mode: str = "local",
    ) -> str:
        return application_pack_to_markdown(
            self.run(job_advert, experience_bank, target_role, tone, matching_mode=matching_mode)
        )


def _import_adk_agent_classes() -> tuple[Any, Any] | None:
    try:
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.agents.sequential_agent import SequentialAgent

        return LlmAgent, SequentialAgent
    except Exception:
        try:
            from google.adk.agents import LlmAgent, SequentialAgent

            return LlmAgent, SequentialAgent
        except Exception:
            return None


def adk_runtime_status() -> Dict[str, Any]:
    """Return a display-friendly status for the live ADK path."""
    adk_installed = _import_adk_agent_classes() is not None
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true", "yes"}
    has_vertex_credentials = use_vertex and bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
    has_gemini_credentials = bool(os.getenv("GOOGLE_API_KEY") or has_vertex_credentials)
    return {
        "adk_installed": adk_installed,
        "has_gemini_credentials": has_gemini_credentials,
        "model": DEFAULT_MODEL,
        "can_run_live": adk_installed and has_gemini_credentials,
    }


def build_adk_root_agent() -> Any:
    """Build a real ADK SequentialAgent with specialised sub-agents."""
    classes = _import_adk_agent_classes()
    if classes is None:  # pragma: no cover - depends on optional ADK install
        return DeterministicJobApplicationPipeline()

    LlmAgent, SequentialAgent = classes

    criteria_parser_agent = LlmAgent(
        name="criteria_parser_agent",
        model=DEFAULT_MODEL,
        description="Extracts essential/desirable criteria from a job advert.",
        instruction=(
            "You are the Criteria Parser. Extract only job requirements and criteria. "
            "Use extract_criteria_tool with the job advert supplied by the user. "
            "Do not invent requirements. Store your result for the next agent."
        ),
        tools=[extract_criteria_tool],
        output_key="criteria_analysis",
    )

    evidence_matcher_agent = LlmAgent(
        name="evidence_matcher_agent",
        model=DEFAULT_MODEL,
        description="Maps job criteria to user-provided evidence.",
        instruction=(
            "You are the Evidence Matcher. Match each criterion to explicit evidence supplied by the user. "
            "Use match_evidence_tool with the job advert, experience bank and requested matching_mode. "
            "If evidence is weak, say it is weak; never fabricate experience."
        ),
        tools=[match_evidence_tool],
        output_key="evidence_matches",
    )

    draft_writer_agent = LlmAgent(
        name="draft_writer_agent",
        model=DEFAULT_MODEL,
        description="Writes concise application answers grounded in matched evidence.",
        instruction=(
            "You are the Draft Writer. Draft short application answers using only supplied evidence. "
            "Prefer cautious wording where experience is indirect. Use draft_answers_tool with the requested matching_mode."
        ),
        tools=[draft_answers_tool],
        output_key="draft_answers",
    )

    safety_reviewer_agent = LlmAgent(
        name="safety_reviewer_agent",
        model=DEFAULT_MODEL,
        description="Checks privacy, prompt-injection and unsupported-claim risks.",
        instruction=(
            "You are the Safety Reviewer. Run privacy and honesty checks before final output. "
            "Use safety_review_tool and build_markdown_pack_tool with the requested matching_mode. Return the final Markdown application pack "
            "plus any warnings. Highlight unsupported claims and redacted PII."
        ),
        tools=[safety_review_tool, build_markdown_pack_tool],
        output_key="safety_review",
    )

    return SequentialAgent(
        name="groundedapply_root_agent",
        description="A fixed-order ADK multi-agent workflow for evidence-grounded job applications.",
        sub_agents=[
            criteria_parser_agent,
            evidence_matcher_agent,
            draft_writer_agent,
            safety_reviewer_agent,
        ],
    )


def build_agent_prompt(
    job_advert: str,
    experience_bank: str,
    target_role: str = "Target role",
    tone: str = "professional",
    matching_mode: str = "local",
) -> str:
    """Create a structured prompt for the live ADK runner."""
    return f"""Build an evidence-grounded application pack.

Target role: {target_role}
Tone: {tone}
Evidence matching mode: {matching_mode}

Job advert:
{job_advert}

Experience bank:
{experience_bank}

Required output:
1. Extracted criteria
2. Evidence mapping
3. Draft answers
4. Security review
5. Final Markdown application pack

Important:
- Pass matching_mode="{matching_mode}" to match_evidence_tool, draft_answers_tool and build_markdown_pack_tool.
- Keep the evidence table, draft answers and Markdown pack consistent with that matching mode.
"""


def _event_text(event: Any) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) if content else None
    if not parts:
        return ""
    return "".join(getattr(part, "text", None) or "" for part in parts)


async def run_live_adk_agent_async(
    job_advert: str,
    experience_bank: str,
    target_role: str = "Target role",
    tone: str = "professional",
    matching_mode: str = "local",
    user_id: str = "groundedapply_user",
) -> Dict[str, Any]:
    """Run the real ADK SequentialAgent and return a compact event trace."""
    status = adk_runtime_status()
    if not status["adk_installed"]:
        raise RuntimeError("google-adk is not installed. Run `pip install google-adk` first.")
    if not status["has_gemini_credentials"]:
        raise RuntimeError("Set GOOGLE_API_KEY or Vertex AI credentials before using live ADK/Gemini mode.")

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    live_agent = build_adk_root_agent()
    if isinstance(live_agent, DeterministicJobApplicationPipeline):
        raise RuntimeError("ADK agent could not be constructed; deterministic fallback was returned.")

    session_service = InMemorySessionService()
    session_id = f"groundedapply-{uuid.uuid4().hex}"
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    runner = Runner(agent=live_agent, app_name=APP_NAME, session_service=session_service)
    content = types.Content(
        role="user",
        parts=[types.Part(text=build_agent_prompt(job_advert, experience_bank, target_role, tone, matching_mode))],
    )

    events: List[Dict[str, str]] = []
    final_text = ""
    async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
        text = _event_text(event)
        author = str(getattr(event, "author", "unknown"))
        if text:
            events.append({"author": author, "text": text})
        is_final = getattr(event, "is_final_response", None)
        if callable(is_final) and is_final() and text:
            final_text = text

    if not final_text and events:
        final_text = events[-1]["text"]

    return {
        "mode": "live_adk_gemini",
        "model": DEFAULT_MODEL,
        "session_id": session.id,
        "events": events,
        "final_text": final_text,
    }


def run_live_adk_agent_sync(
    job_advert: str,
    experience_bank: str,
    target_role: str = "Target role",
    tone: str = "professional",
    matching_mode: str = "local",
) -> Dict[str, Any]:
    """Synchronous wrapper for Streamlit and simple scripts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_live_adk_agent_async(job_advert, experience_bank, target_role, tone, matching_mode))
    raise RuntimeError("An event loop is already running. In notebooks, use `await run_live_adk_agent_async(...)`.")


root_agent = build_adk_root_agent()
fallback_pipeline = DeterministicJobApplicationPipeline()
