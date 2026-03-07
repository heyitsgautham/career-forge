"""
Skill Gap Analysis Engine
=========================
Computes skill gap between a user's GitHub-grounded profile
and a target career role using Bedrock Claude for scoring.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
import structlog

from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service


logger = structlog.get_logger()

# ─── Load role benchmarks from JSON ──────────────────────────────────────────

_BENCHMARKS_PATH = Path(__file__).parent.parent / "data" / "role_benchmarks.json"

def _load_benchmarks() -> Dict[str, Any]:
    """Load role benchmarks from the static JSON file."""
    with open(_BENCHMARKS_PATH, "r") as f:
        data = json.load(f)
    return {role["roleId"]: role for role in data["roles"]}


ROLE_BENCHMARKS = _load_benchmarks()


def get_all_roles() -> List[Dict[str, Any]]:
    """Return list of available career roles (for the frontend picker)."""
    return [
        {
            "roleId": r["roleId"],
            "role": r["role"],
            "icon": r["icon"],
            "description": r["description"],
            "skillDomains": list(r["skills"].keys()),
        }
        for r in ROLE_BENCHMARKS.values()
    ]


def get_role_benchmark(role_id: str) -> Optional[Dict[str, Any]]:
    """Return the full benchmark for a role, or None."""
    return ROLE_BENCHMARKS.get(role_id)


# ─── Skill scoring via Claude ────────────────────────────────────────────────

SCORING_SYSTEM_PROMPT = """You are an expert technical recruiter and engineering manager.
Your job is to objectively assess a developer's proficiency across
specific skill domains based SOLELY on their GitHub project portfolio.

RULES:
1. Only use evidence from the provided project summaries.
2. Score each domain 0–100 where:
   - 0 = no evidence at all
   - 20 = minimal/trivial evidence
   - 40 = basic usage, simple projects
   - 60 = intermediate projects, multiple examples
   - 80 = strong evidence, complex production-quality work
   - 100 = expert-level, deep mastery across multiple projects
3. Be calibrated — most developers score 30–70 on most domains.
4. If no projects relate to a domain, score it 0–10.
5. Return ONLY valid JSON, no markdown, no explanation."""


async def score_user_skills(
    project_summaries: List[Dict[str, Any]],
    skill_domains: List[str],
) -> Dict[str, int]:
    """
    Use Claude to score a user's proficiency in each skill domain
    based on their GitHub project summaries.

    Args:
        project_summaries: List of project dicts with keys like
            name, description, technologies, highlights, etc.
        skill_domains: List of skill domain names to score.

    Returns:
        Dict mapping skill domain → score (0–100)
    """
    # Build concise project descriptions
    projects_text = ""
    for i, proj in enumerate(project_summaries, 1):
        name = proj.get("name") or proj.get("title", "Untitled")
        desc = proj.get("description", "")
        techs = proj.get("technologies") or proj.get("skills", [])
        highlights = proj.get("highlights", [])

        projects_text += f"\n### Project {i}: {name}\n"
        projects_text += f"Description: {desc}\n"
        if techs:
            projects_text += f"Technologies: {', '.join(techs)}\n"
        if highlights:
            projects_text += f"Highlights:\n"
            for h in highlights[:5]:
                projects_text += f"  - {h}\n"

    domains_str = "\n".join(f"  - {d}" for d in skill_domains)

    prompt = f"""Based on the following GitHub project portfolio, score this developer's
proficiency in each of the listed skill domains (0–100).

<projects>
{projects_text}
</projects>

<skill_domains>
{domains_str}
</skill_domains>

Return a JSON object mapping each domain name to an integer score (0–100).
Example: {{"Programming Languages": 72, "System Design": 45, ...}}

Return ONLY the JSON object."""

    try:
        result = await bedrock_client.generate_json(
            prompt=prompt,
            system_instruction=SCORING_SYSTEM_PROMPT,
            temperature=0.1,
        )
        # Ensure all domains are present and scores are ints
        scores = {}
        for domain in skill_domains:
            raw = result.get(domain, 0)
            scores[domain] = max(0, min(100, int(raw)))
        return scores
    except Exception as e:
        logger.error("Skill scoring failed", error=str(e))
        # Return zero scores as fallback
        return {domain: 0 for domain in skill_domains}


# ─── Gap computation ─────────────────────────────────────────────────────────

def compute_gaps(
    user_scores: Dict[str, int],
    benchmark_scores: Dict[str, int],
) -> List[Dict[str, Any]]:
    """
    Compute the gap between user scores and role benchmarks.

    Returns list of gap dicts sorted by gap size (desc).
    """
    gaps = []
    for domain, required in benchmark_scores.items():
        user_score = user_scores.get(domain, 0)
        gap = max(0, required - user_score)

        if gap > 30:
            priority = "high"
        elif gap > 15:
            priority = "medium"
        else:
            priority = "low"

        gaps.append({
            "domain": domain,
            "userScore": user_score,
            "requiredScore": required,
            "gap": gap,
            "priority": priority,
        })

    # Sort by gap descending
    gaps.sort(key=lambda g: g["gap"], reverse=True)
    return gaps


def compute_overall_fit(
    user_scores: Dict[str, int],
    benchmark_scores: Dict[str, int],
) -> int:
    """
    Compute overall fit percentage (0–100).
    Weighted average of how close user scores are to benchmarks.
    """
    if not benchmark_scores:
        return 0

    total_weight = sum(benchmark_scores.values())
    if total_weight == 0:
        return 0

    weighted_score = 0
    for domain, required in benchmark_scores.items():
        user_score = user_scores.get(domain, 0)
        # Cap at 100% per domain (user can exceed benchmark)
        ratio = min(user_score / max(required, 1), 1.0)
        weighted_score += ratio * required

    return round((weighted_score / total_weight) * 100)


# ─── Full analysis pipeline ─────────────────────────────────────────────────

async def run_gap_analysis(
    user_id: str,
    role_id: str,
) -> Dict[str, Any]:
    """
    Run the full skill gap analysis pipeline:
    1. Load user's projects from DynamoDB
    2. Get role benchmark
    3. Score user via Claude
    4. Compute gaps
    5. Cache result in DynamoDB

    Returns:
        Full gap analysis report dict
    """
    # 1. Get role benchmark
    benchmark = get_role_benchmark(role_id)
    if not benchmark:
        raise ValueError(f"Unknown role: {role_id}")

    benchmark_scores = benchmark["skills"]
    skill_domains = list(benchmark_scores.keys())

    # 2. Load user's projects from DynamoDB
    projects = await dynamo_service.query(
        table="Projects",
        pk_name="userId",
        pk_value=user_id,
    )

    if not projects:
        logger.warning("No projects found for user", userId=user_id)
        # Return zero scores
        user_scores = {domain: 0 for domain in skill_domains}
    else:
        # 3. Score user skills via Claude
        user_scores = await score_user_skills(projects, skill_domains)

    # 4. Compute gaps
    gaps = compute_gaps(user_scores, benchmark_scores)
    overall_fit = compute_overall_fit(user_scores, benchmark_scores)

    # 5. Build report
    report_id = dynamo_service.generate_id()
    report = {
        "reportId": report_id,
        "userId": user_id,
        "roleId": role_id,
        "roleName": benchmark["role"],
        "userScores": user_scores,
        "benchmarkScores": benchmark_scores,
        "gaps": gaps,
        "overallFitPercent": overall_fit,
        "projectCount": len(projects),
        "createdAt": dynamo_service.now_iso(),
    }

    # 6. Cache to DynamoDB
    try:
        await dynamo_service.put_item("SkillGapReports", report)
        logger.info(
            "Gap analysis cached",
            reportId=report_id,
            userId=user_id,
            roleId=role_id,
            fit=overall_fit,
        )
    except Exception as e:
        logger.warning("Failed to cache gap analysis", error=str(e))
        # Non-fatal — return the report anyway

    return report


async def get_cached_report(user_id: str, role_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch the most recent cached gap report for a user (optionally filtered by role)."""
    try:
        reports = await dynamo_service.query(
            table="SkillGapReports",
            pk_name="userId",
            pk_value=user_id,
            scan_forward=False,
            limit=10,
        )
        if not reports:
            return None

        if role_id:
            reports = [r for r in reports if r.get("roleId") == role_id]

        return reports[0] if reports else None
    except Exception as e:
        logger.warning("Failed to fetch cached gap report", error=str(e))
        return None
