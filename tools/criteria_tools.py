"""Tools for job-application evidence matching.

The aim is not to replace an applicant. It is to structure the applicant's own
evidence and prevent unsupported claims.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Tuple

from .security_tools import detect_prompt_injection, redact_pii, run_security_review

DEFAULT_MATCH_MODEL = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

STOPWORDS = {
    "and", "or", "the", "a", "an", "to", "of", "in", "for", "with", "on", "by", "as", "is", "are",
    "be", "have", "has", "this", "that", "you", "your", "we", "our", "will", "can", "from", "at", "role",
    "when", "then", "than", "into", "using", "used", "aimed", "ensure", "operate", "such", "similar",
    "useful", "well", "any", "excellent",
    "ability", "experience", "knowledge", "skills", "understanding", "working", "work", "within",
}

SECTION_MARKERS = {
    "essential": "essential",
    "essential criteria": "essential",
    "desirable": "desirable",
    "desirable criteria": "desirable",
    "responsibilities": "responsibility",
    "duties": "responsibility",
    "values": "values",
}

CONCEPT_PATTERNS = {
    "degree_or_equivalent": [
        r"\bdegree\b",
        r"\bmsc\b|\bm\.sc\b|\bmaster'?s?\b",
        r"\bbsc\b|\bb\.sc\b|\bbachelor'?s?\b",
        r"\bphd\b|\bdoctorate\b",
        r"\beducat(?:ed|ion)\b",
        r"\buniversity\b",
    ],
    "quantitative_field": [
        r"\bdata\s+(?:science|analytics?|analysis|mining|visuali[sz]ation)\b",
        r"\bstatistics?\b|\bstatistical\b",
        r"\bmachine\s+learning\b|\bml\b",
        r"\bmathematics?\b|\bmaths?\b",
        r"\bphysics\b",
        r"\bquant(?:itative)?\b",
        r"\bcomputer\s+(?:science|engineering)\b",
        r"\bapplied\s+math(?:ematics?)?\b",
    ],
    "programming_python": [r"\bpython\b"],
    "programming_general": [
        r"\bprogramming\b",
        r"\bsoftware\b",
        r"\bsoftware\s+engineering\b",
        r"\bgit\b",
        r"\blinux\b",
        r"\bc\+\+\b",
        r"\brust\b",
        r"\btypescript\b|\bjavascript\b|\breact\b",
    ],
    "database_sql": [r"\bdatabase\b|\bdbms\b", r"\bsql\b"],
    "communication": [
        r"\bcommunicat(?:e|ed|ion)\b",
        r"\bpresent(?:ed|ation)?\b",
        r"\bwritten\b|\bverbal\b",
        r"\bnon-?technical\b",
        r"\baudience[s]?\b|\bstakeholder[s]?\b",
    ],
    "healthcare_context": [
        r"\bhealth(?:care)?\b",
        r"\bclinical\b",
        r"\bbiomedical\b",
        r"\bnhs\b",
        r"\bicb\b|\bics\b",
        r"\bprovider[s]?\b|\bcommissioning\b",
    ],
    "project_delivery": [
        r"\bproject\b|\bprogramme\b",
        r"\bdelivery\b",
        r"\bcollaborat(?:e|ed|ive|ion)\b",
        r"\bdebugging\b|\bbuild\b|\btooling\b",
    ],
    "professional_values": [
        r"\bcaring\b|\bconsiderate\b",
        r"\brespect(?:ful)?\b",
        r"\blisten(?:ed)?\b",
        r"\bopen(?:ness)?\b|\bhonest(?:y)?\b",
        r"\bapproachable\b",
    ],
    "finance_context": [
        r"\bfinance\b|\bfinancial\b",
        r"\binvestment\b",
        r"\btrading\b|\bquant\b",
    ],
}

CONCEPT_NAMES = set(CONCEPT_PATTERNS)


@dataclass
class Criterion:
    criterion_id: str
    section: str
    text: str
    keywords: List[str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class EvidenceItem:
    evidence_id: str
    text: str
    keywords: List[str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class EvidenceMatch:
    criterion_id: str
    criterion: str
    matched_evidence: List[Dict[str, object]]
    match_score: float
    coverage: str
    risk_note: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def extract_keywords(text: str, limit: int = 20) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", text or "")
    cleaned = []
    source = text or ""
    for word in words:
        w = word.lower().strip(".-")
        if w.endswith("ness") and len(w) > 6:
            w = w[:-4]
        if w.endswith("ly") and len(w) > 5:
            w = w[:-2]
        if w not in STOPWORDS and not w.isdigit() and len(w) > 2:
            cleaned.append(w)
    for concept, patterns in CONCEPT_PATTERNS.items():
        if any(re.search(pattern, source, flags=re.IGNORECASE) for pattern in patterns):
            cleaned.append(concept)
    seen = set()
    ordered = []
    for w in cleaned:
        if w not in seen:
            seen.add(w)
            ordered.append(w)
    return ordered[:limit]


def _split_lines(text: str) -> List[str]:
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        line = re.sub(r"^[\-*\d.)\s]+", "", line).strip()
        if line:
            lines.append(line)
    return lines


def parse_criteria(job_advert: str) -> List[Dict[str, object]]:
    """Extract a simple criteria list from a job advert or criteria block."""
    lines = _split_lines(job_advert)
    criteria: List[Criterion] = []
    section = "general"

    for line in lines:
        lower = line.lower().rstrip(":")
        if lower in SECTION_MARKERS:
            section = SECTION_MARKERS[lower]
            continue
        if len(line) < 12:
            continue
        looks_like_criterion = (
            any(
                token in lower
                for token in [
                    "experience",
                    "knowledge",
                    "ability",
                    "understanding",
                    "skill",
                    "must",
                    "able",
                    "degree",
                    "professional",
                    "respect",
                    "honest",
                    "communicat",
                    "data",
                    "analytics",
                    "machine",
                    "project",
                ]
            )
            or section != "general"
        )
        if looks_like_criterion:
            cid = f"C{len(criteria) + 1}"
            criteria.append(Criterion(cid, section, line, extract_keywords(line)))

    if not criteria and job_advert.strip():
        sentences = re.split(r"(?<=[.!?])\s+", job_advert.strip())
        for sentence in sentences[:8]:
            if len(sentence) >= 30:
                cid = f"C{len(criteria) + 1}"
                criteria.append(Criterion(cid, "general", sentence, extract_keywords(sentence)))

    return [c.to_dict() for c in criteria]


def parse_experience_bank(experience_bank: str) -> List[Dict[str, object]]:
    """Parse user-provided experience into evidence items."""
    lines = _split_lines(experience_bank)
    evidence: List[EvidenceItem] = []
    buffer: List[str] = []

    for line in lines:
        if len(line) < 8:
            continue
        if re.match(r"^(E\d+|Project|Role|Education|Experience|Skill|Achievement)\b", line, flags=re.IGNORECASE):
            if buffer:
                text = " ".join(buffer)
                evidence.append(EvidenceItem(f"E{len(evidence) + 1}", text, extract_keywords(text)))
                buffer = []
            buffer.append(line)
        else:
            if buffer:
                text = " ".join(buffer)
                evidence.append(EvidenceItem(f"E{len(evidence) + 1}", text, extract_keywords(text)))
                buffer = []
            evidence.append(EvidenceItem(f"E{len(evidence) + 1}", line, extract_keywords(line)))

    if buffer:
        text = " ".join(buffer)
        evidence.append(EvidenceItem(f"E{len(evidence) + 1}", text, extract_keywords(text)))

    return [e.to_dict() for e in evidence]


def _score_overlap(a: Iterable[str], b: Iterable[str]) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    overlap = set_a & set_b
    base_score = len(overlap) / max(1, len(set_a))
    concept_bonus = 0.12 * len(overlap & CONCEPT_NAMES)
    return round(min(1.0, base_score + concept_bonus), 3)


def _coverage_for_score(score: float, semantic: bool = False) -> Tuple[str, str]:
    if semantic:
        if score >= 0.55:
            return "strong", "Evidence appears directly relevant."
        if score >= 0.25:
            return "partial", "Evidence is semantically related. Use cautious wording and avoid overstating direct experience."
    else:
        if score >= 0.30:
            return "strong", "Evidence appears directly relevant."
        if score >= 0.10:
            return "partial", "Use cautious wording and avoid overstating direct experience."
    return "weak", "No clear evidence found. Flag as a gap rather than inventing experience."


def _local_scored_candidates(
    criterion: Dict[str, object],
    evidence: List[Dict[str, object]],
) -> Dict[str, Dict[str, object]]:
    candidates: Dict[str, Dict[str, object]] = {}
    for item in evidence:
        score = _score_overlap(criterion.get("keywords", []), item.get("keywords", []))
        if score > 0:
            evidence_id = str(item.get("evidence_id"))
            candidates[evidence_id] = {
                "score": score,
                "item": item,
                "local_score": score,
            }
    return candidates


def match_evidence_local(
    criteria: List[Dict[str, object]],
    evidence: List[Dict[str, object]],
    top_k: int = 3,
) -> List[Dict[str, object]]:
    """Match criteria to evidence using local keywords plus transparent semantic concepts."""
    matches: List[EvidenceMatch] = []
    for criterion in criteria:
        candidates = _local_scored_candidates(criterion, evidence)
        scored = sorted(candidates.values(), key=lambda x: float(x["score"]), reverse=True)
        selected = []
        for candidate in scored[:top_k]:
            item = candidate["item"]
            selected.append({**item, "score": candidate["score"], "local_score": candidate["local_score"]})
        top_score = float(selected[0]["score"]) if selected else 0.0
        coverage, risk_note = _coverage_for_score(top_score, semantic=False)
        matches.append(
            EvidenceMatch(
                criterion_id=str(criterion.get("criterion_id")),
                criterion=str(criterion.get("text")),
                matched_evidence=selected,
                match_score=float(top_score),
                coverage=coverage,
                risk_note=risk_note,
            )
        )
    return [m.to_dict() for m in matches]


def _extract_json_object(text: str) -> Dict[str, object]:
    source = (text or "").strip()
    if source.startswith("```"):
        source = re.sub(r"^```(?:json)?\s*", "", source)
        source = re.sub(r"\s*```$", "", source)
    try:
        return json.loads(source)
    except json.JSONDecodeError:
        start = source.find("{")
        end = source.rfind("}")
        if start >= 0 and end > start:
            return json.loads(source[start : end + 1])
        raise


def _semantic_match_prompt(criteria: List[Dict[str, object]], evidence: List[Dict[str, object]]) -> str:
    criteria_payload = [
        {
            "criterion_id": c.get("criterion_id"),
            "criterion": c.get("text"),
        }
        for c in criteria
    ]
    evidence_payload = [
        {
            "evidence_id": e.get("evidence_id"),
            "evidence": e.get("text"),
        }
        for e in evidence
    ]
    return (
        "You are an evidence-grounded job-application matching judge.\n"
        "Match job criteria to user-provided evidence. Do not invent experience.\n"
        "A match can be direct or transferable, but it must be supported by the evidence text.\n"
        "Score each relevant pair from 0.0 to 1.0:\n"
        "- 0.0 means no relationship.\n"
        "- 0.25 means weak/transferable relationship.\n"
        "- 0.55 means strong relevant evidence.\n"
        "- 0.80+ means very direct evidence.\n"
        "Return JSON only in this exact shape:\n"
        '{"matches":[{"criterion_id":"C1","evidence_id":"E1","score":0.0,"rationale":"short reason"}]}\n\n'
        f"Criteria:\n{json.dumps(criteria_payload, ensure_ascii=False, indent=2)}\n\n"
        f"Evidence:\n{json.dumps(evidence_payload, ensure_ascii=False, indent=2)}\n"
    )


def semantic_match_available() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY"))


def _call_gemini_semantic_matcher(
    criteria: List[Dict[str, object]],
    evidence: List[Dict[str, object]],
    model: str = DEFAULT_MATCH_MODEL,
) -> List[Dict[str, object]]:
    if not semantic_match_available():
        raise RuntimeError("GOOGLE_API_KEY is not set.")
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        raise RuntimeError("google-genai is not installed. Run `python -m pip install -r requirements.txt`.") from exc

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    response = client.models.generate_content(
        model=model,
        contents=_semantic_match_prompt(criteria, evidence),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    payload = _extract_json_object(response.text or "{}")
    matches = payload.get("matches", [])
    if not isinstance(matches, list):
        raise RuntimeError("Gemini semantic matcher returned an unexpected JSON shape.")
    cleaned = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        try:
            score = float(match.get("score", 0))
        except (TypeError, ValueError):
            continue
        cleaned.append(
            {
                "criterion_id": str(match.get("criterion_id", "")),
                "evidence_id": str(match.get("evidence_id", "")),
                "score": max(0.0, min(1.0, score)),
                "rationale": str(match.get("rationale", ""))[:240],
            }
        )
    return cleaned


def match_evidence_semantic(
    criteria: List[Dict[str, object]],
    evidence: List[Dict[str, object]],
    top_k: int = 3,
    model: str = DEFAULT_MATCH_MODEL,
) -> List[Dict[str, object]]:
    """Match criteria to evidence using Gemini semantic scoring plus local fallback scores."""
    semantic_rows = _call_gemini_semantic_matcher(criteria, evidence, model=model)
    semantic_by_criterion: Dict[str, Dict[str, Dict[str, object]]] = {}
    for row in semantic_rows:
        if row["score"] <= 0:
            continue
        semantic_by_criterion.setdefault(row["criterion_id"], {})[row["evidence_id"]] = row

    evidence_by_id = {str(item.get("evidence_id")): item for item in evidence}
    matches: List[EvidenceMatch] = []
    for criterion in criteria:
        criterion_id = str(criterion.get("criterion_id"))
        candidates = _local_scored_candidates(criterion, evidence)
        for evidence_id, semantic_row in semantic_by_criterion.get(criterion_id, {}).items():
            item = evidence_by_id.get(evidence_id)
            if not item:
                continue
            existing = candidates.get(evidence_id, {"item": item, "score": 0.0, "local_score": 0.0})
            semantic_score = float(semantic_row["score"])
            existing.update(
                {
                    "score": max(float(existing.get("score", 0.0)), semantic_score),
                    "semantic_score": semantic_score,
                    "semantic_rationale": semantic_row.get("rationale", ""),
                }
            )
            candidates[evidence_id] = existing

        scored = sorted(candidates.values(), key=lambda x: float(x["score"]), reverse=True)
        selected = []
        semantic_used = False
        for candidate in scored[:top_k]:
            item = candidate["item"]
            output = {
                **item,
                "score": round(float(candidate["score"]), 3),
                "local_score": round(float(candidate.get("local_score", 0.0)), 3),
            }
            if "semantic_score" in candidate:
                semantic_used = True
                output["semantic_score"] = round(float(candidate["semantic_score"]), 3)
                output["semantic_rationale"] = candidate.get("semantic_rationale", "")
            selected.append(output)

        top_score = float(selected[0]["score"]) if selected else 0.0
        coverage, risk_note = _coverage_for_score(top_score, semantic=semantic_used)
        matches.append(
            EvidenceMatch(
                criterion_id=criterion_id,
                criterion=str(criterion.get("text")),
                matched_evidence=selected,
                match_score=round(top_score, 3),
                coverage=coverage,
                risk_note=risk_note,
            )
        )
    return [m.to_dict() for m in matches]


def match_evidence(
    criteria: List[Dict[str, object]],
    evidence: List[Dict[str, object]],
    top_k: int = 3,
    matching_mode: str = "local",
    model: str = DEFAULT_MATCH_MODEL,
) -> List[Dict[str, object]]:
    """Match each criterion to evidence using local or Gemini semantic matching."""
    if matching_mode == "gemini":
        return match_evidence_semantic(criteria, evidence, top_k=top_k, model=model)
    return match_evidence_local(criteria, evidence, top_k=top_k)


def draft_answer_for_match(match: Dict[str, object], tone: str = "professional") -> str:
    evidence = match.get("matched_evidence", []) or []
    criterion = match.get("criterion", "this criterion")
    coverage = match.get("coverage", "weak")

    if coverage == "weak" or not evidence:
        return (
            f"For the criterion '{criterion}', I would not claim direct experience unless I can add more evidence. "
            "Based on the information provided, the safest response is to acknowledge transferable experience and identify this as a development area."
        )

    evidence_refs = "; ".join([f"{item['evidence_id']}: {item['text']}" for item in evidence])
    if tone == "concise":
        return (
            f"I meet this criterion through the following evidence: {evidence_refs}. "
            "These examples show relevant knowledge, practical application, and the ability to communicate outcomes clearly."
        )
    return (
        f"I meet the criterion '{criterion}' through evidence from {evidence_refs}. "
        "In these examples, I applied relevant skills in a practical setting, translated technical work into useful outcomes, "
        "and can build on this experience in the target role."
    )


def build_application_pack(
    job_advert: str,
    experience_bank: str,
    target_role: str = "Target role",
    tone: str = "professional",
    matching_mode: str = "local",
) -> Dict[str, object]:
    """End-to-end deterministic pipeline used as MCP tools and app backend."""
    redacted_job = redact_pii(job_advert)["redacted_text"]
    redacted_exp = redact_pii(experience_bank)["redacted_text"]

    criteria = parse_criteria(redacted_job)
    evidence = parse_experience_bank(redacted_exp)
    matching_info = {
        "requested_mode": matching_mode,
        "actual_mode": "local",
        "model": DEFAULT_MATCH_MODEL,
        "warning": "",
    }
    try:
        matches = match_evidence(criteria, evidence, matching_mode=matching_mode, model=DEFAULT_MATCH_MODEL)
        matching_info["actual_mode"] = matching_mode
    except Exception as exc:
        matches = match_evidence_local(criteria, evidence)
        matching_info["actual_mode"] = "local"
        matching_info["warning"] = f"Gemini semantic matching was unavailable; used local matching instead. {exc}"
    draft_answers = [
        {
            "criterion_id": m["criterion_id"],
            "criterion": m["criterion"],
            "coverage": m["coverage"],
            "answer": draft_answer_for_match(m, tone=tone),
        }
        for m in matches
    ]
    full_draft = "\n\n".join([d["answer"] for d in draft_answers])
    security = run_security_review(job_advert, experience_bank, full_draft)
    security["findings"].extend(detect_prompt_injection(full_draft))

    return {
        "project": "GroundedApply",
        "target_role": target_role,
        "criteria": criteria,
        "evidence": evidence,
        "evidence_matches": matches,
        "matching_info": matching_info,
        "draft_answers": draft_answers,
        "security_review": security,
    }


def application_pack_to_markdown(pack: Dict[str, object]) -> str:
    lines = []
    lines.append(f"# {pack.get('project', 'GroundedApply')} Application Pack")
    lines.append(f"\nTarget role: **{pack.get('target_role', 'Target role')}**\n")
    matching_info = pack.get("matching_info", {})
    if matching_info:
        lines.append(
            "Matching mode: "
            f"**{matching_info.get('actual_mode', 'local')}** "
            f"(requested: {matching_info.get('requested_mode', 'local')})\n"
        )

    lines.append("## 1. Extracted criteria")
    for c in pack.get("criteria", []):
        lines.append(f"- **{c['criterion_id']}** ({c['section']}): {c['text']}")

    lines.append("\n## 2. Evidence matching")
    for m in pack.get("evidence_matches", []):
        refs = ", ".join([f"{e['evidence_id']} ({e['score']})" for e in m.get("matched_evidence", [])])
        refs = refs or "No direct evidence found"
        lines.append(f"- **{m['criterion_id']}**: {m['coverage']} coverage - {refs}. {m['risk_note']}")

    lines.append("\n## 3. Draft answers")
    for d in pack.get("draft_answers", []):
        lines.append(f"### {d['criterion_id']}: {d['coverage']} coverage")
        lines.append(d["answer"])

    lines.append("\n## 4. Security review")
    sec = pack.get("security_review", {})
    lines.append(f"PII redaction counts: `{json.dumps(sec.get('pii_redaction_counts', {}))}`")
    findings = sec.get("findings", [])
    if findings:
        for f in findings:
            lines.append(f"- **{f['severity']} / {f['category']}**: {f['message']} Evidence: `{f.get('evidence', '')}`")
    else:
        lines.append("- No prompt-injection or unsupported-claim findings from deterministic checks.")

    return "\n".join(lines) + "\n"
