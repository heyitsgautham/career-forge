"""
LearnWeave Roadmap Generator
=============================
Generates a personalised project-based learning roadmap
from skill gap analysis results using Bedrock Claude.
"""

import json
from typing import Dict, Any, List, Optional
import structlog

from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service
from app.services.gap_analysis import get_cached_report


logger = structlog.get_logger()


# ─── Roadmap generation prompt ───────────────────────────────────────────────

ROADMAP_SYSTEM_PROMPT = """You are an expert coding mentor and technical career coach.
Your job is to create practical, project-based learning roadmaps
that help developers close specific skill gaps efficiently.

RULES:
1. Each week must have ONE concrete project that builds real skills.
2. Projects should be progressively challenging (Week 1 = foundations, Week 4 = advanced).
3. Tech stack must be specific and relevant to the skill gaps.
4. Resource links should be real, well-known documentation sites or tutorial platforms.
   Use ONLY these trusted domains for links:
   - docs.python.org, docs.djangoproject.com, fastapi.tiangolo.com
   - developer.mozilla.org (MDN), react.dev, nextjs.org
   - docs.aws.amazon.com, cloud.google.com/docs
   - kubernetes.io/docs, docker.com/docs
   - pytorch.org/docs, scikit-learn.org, tensorflow.org
   - github.com (official repos only)
   - freecodecamp.org, roadmap.sh
5. Estimated hours should be realistic (5–15 hours per week).
6. Return ONLY valid JSON, no markdown, no explanation."""


async def generate_roadmap(
    user_id: str,
    role_id: str,
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a 4-week project-based learning roadmap from gap analysis.

    Args:
        user_id: The user's ID
        role_id: The target role ID
        report_id: Optional specific report ID (uses latest if not provided)

    Returns:
        Roadmap dict with weeks, projects, and resources.
    """
    # 1. Get the gap report (use cached or latest)
    report = await get_cached_report(user_id, role_id=role_id)

    if not report:
        raise ValueError(
            "No gap analysis found. Please run a skill gap analysis first."
        )

    # 2. Build the prompt
    gaps = report.get("gaps", [])
    role_name = report.get("roleName", role_id)
    overall_fit = report.get("overallFitPercent", 0)

    # Focus on high/medium priority gaps
    priority_gaps = [g for g in gaps if g["priority"] in ("high", "medium")]
    if not priority_gaps:
        priority_gaps = gaps[:4]  # Take top 4 even if all "low"

    gaps_text = "\n".join(
        f"  - {g['domain']}: User={g['userScore']}, Required={g['requiredScore']}, "
        f"Gap={g['gap']} ({g['priority']} priority)"
        for g in priority_gaps
    )

    prompt = f"""Create a 4-week project-based learning roadmap for a developer
targeting the role of **{role_name}** (current overall fit: {overall_fit}%).

Their key skill gaps are:
{gaps_text}

For each week, provide:
1. A specific project to build
2. The tech stack needed
3. Estimated hours to complete
4. 3 curated learning resources (title + URL from trusted documentation sites)

Return a JSON object with this exact structure:
{{
  "weeks": [
    {{
      "week": 1,
      "projectTitle": "Build a REST API with Authentication",
      "description": "A brief description of the project and what skills it develops",
      "techStack": ["Python", "FastAPI", "PostgreSQL", "JWT"],
      "estimatedHours": 10,
      "resources": [
        {{"title": "FastAPI Official Tutorial", "url": "https://fastapi.tiangolo.com/tutorial/"}},
        {{"title": "PostgreSQL Documentation", "url": "https://www.postgresql.org/docs/"}},
        {{"title": "JWT Authentication Guide", "url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Authentication"}}
      ]
    }}
  ]
}}

Return ONLY the JSON object with exactly 4 weeks."""

    try:
        result = await bedrock_client.generate_json(
            prompt=prompt,
            system_instruction=ROADMAP_SYSTEM_PROMPT,
            temperature=0.3,
        )

        weeks = result.get("weeks", [])

        # Validate and normalize
        validated_weeks = []
        for w in weeks[:4]:
            validated_weeks.append({
                "week": w.get("week", len(validated_weeks) + 1),
                "projectTitle": w.get("projectTitle", "Untitled Project"),
                "description": w.get("description", ""),
                "techStack": w.get("techStack", []),
                "estimatedHours": w.get("estimatedHours", 10),
                "resources": [
                    {"title": r.get("title", "Resource"), "url": r.get("url", "#")}
                    for r in w.get("resources", [])[:3]
                ],
                "completedAt": None,
            })

    except Exception as e:
        logger.error("Roadmap generation via Claude failed", error=str(e))
        raise ValueError("Failed to generate learning roadmap. Please try again.")

    # 3. Build roadmap document
    roadmap_id = dynamo_service.generate_id()
    roadmap = {
        "roadmapId": roadmap_id,
        "userId": user_id,
        "roleId": role_id,
        "roleName": role_name,
        "reportId": report.get("reportId"),
        "overallFitPercent": overall_fit,
        "weeks": validated_weeks,
        "completedWeeks": 0,
        "totalWeeks": len(validated_weeks),
        "createdAt": dynamo_service.now_iso(),
    }

    # 4. Store in DynamoDB
    try:
        await dynamo_service.put_item("Roadmaps", roadmap)
        logger.info(
            "Roadmap generated and stored",
            roadmapId=roadmap_id,
            userId=user_id,
            roleId=role_id,
        )
    except Exception as e:
        logger.warning("Failed to store roadmap in DynamoDB", error=str(e))
        # Non-fatal — return the roadmap anyway

    return roadmap


async def get_roadmap(roadmap_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a specific roadmap by ID."""
    try:
        # Scan for the roadmap by ID (since we store by userId PK)
        from boto3.dynamodb.conditions import Attr
        results = await dynamo_service.scan(
            table="Roadmaps",
            filter_expression=Attr("roadmapId").eq(roadmap_id),
            limit=1,
        )
        return results[0] if results else None
    except Exception as e:
        logger.warning("Failed to fetch roadmap", error=str(e))
        return None


async def get_user_roadmaps(user_id: str) -> List[Dict[str, Any]]:
    """Fetch all roadmaps for a user."""
    try:
        roadmaps = await dynamo_service.query(
            table="Roadmaps",
            pk_name="userId",
            pk_value=user_id,
            scan_forward=False,
        )
        return roadmaps
    except Exception as e:
        logger.warning("Failed to fetch user roadmaps", error=str(e))
        return []


async def mark_milestone_complete(
    roadmap_id: str,
    week_number: int,
    user_id: str,
) -> Dict[str, Any]:
    """
    Mark a specific week/milestone as complete in a roadmap.

    Args:
        roadmap_id: The roadmap ID
        week_number: Week number (1-4)
        user_id: The user ID (for authorization)

    Returns:
        Updated roadmap dict
    """
    roadmap = await get_roadmap(roadmap_id)
    if not roadmap:
        raise ValueError("Roadmap not found")

    if roadmap.get("userId") != user_id:
        raise ValueError("Unauthorized: roadmap belongs to another user")

    weeks = roadmap.get("weeks", [])
    if week_number < 1 or week_number > len(weeks):
        raise ValueError(f"Invalid week number: {week_number}")

    # Update the week's completedAt timestamp
    week_idx = week_number - 1
    weeks[week_idx]["completedAt"] = dynamo_service.now_iso()

    # Count completed weeks
    completed_count = sum(1 for w in weeks if w.get("completedAt"))

    # Update in DynamoDB
    try:
        await dynamo_service.update_item(
            table="Roadmaps",
            key={"userId": user_id, "roadmapId": roadmap_id},
            updates={
                "weeks": weeks,
                "completedWeeks": completed_count,
            },
        )
        logger.info(
            "Milestone marked complete",
            roadmapId=roadmap_id,
            week=week_number,
            completed=completed_count,
        )
    except Exception as e:
        logger.warning("Failed to update milestone in DynamoDB", error=str(e))

    roadmap["weeks"] = weeks
    roadmap["completedWeeks"] = completed_count
    return roadmap
