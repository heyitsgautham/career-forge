"""
Project-Based Learning Roadmap Generator
==========================================
Two-step flow:
  1. suggest_projects() → 3 medium/hard project ideas for a domain
  2. generate_day_plan() → 7-day roadmap for the chosen project

Uses Bedrock Claude for AI generation, DynamoDB for persistence.
"""

import json
from typing import Dict, Any, List, Optional
import structlog

from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service


logger = structlog.get_logger()


# ─── Prompts ─────────────────────────────────────────────────────────────────

SUGGEST_SYSTEM = """You are an expert coding mentor. You suggest real-world projects
that teach practical skills through hands-on building.

RULES:
1. Suggest exactly 3 projects — a mix of medium and hard difficulty.
2. Each project must be a COMPLETE, buildable application — not a toy exercise.
3. Projects should be achievable within 7-8 days at the specified hours/week.
4. Tech stacks must be specific and industry-relevant.
5. Return ONLY valid JSON, no markdown, no explanation."""


PLAN_SYSTEM = """You are an expert coding mentor who creates detailed day-by-day project plans.
You break complex projects into clear daily phases so a learner can build the full project in 7 days.

RULES:
1. Create exactly 7 day-phases (Day 1 through Day 7).
2. Day 1 should cover setup, architecture design, and initial scaffolding.
3. Days 2-5 should be core implementation phases.
4. Day 6 should be integration, polishing, and testing.
5. Day 7 should be deployment, documentation, and final review.
6. Each day must have a clear title, description, tasks, tech details, and architecture notes.
7. Resource links should be from well-known docs sites only:
   - developer.mozilla.org, react.dev, nextjs.org, vuejs.org, angular.dev
   - docs.python.org, fastapi.tiangolo.com, docs.djangoproject.com
   - docs.aws.amazon.com, cloud.google.com/docs, kubernetes.io/docs
   - pytorch.org/docs, scikit-learn.org, tensorflow.org, huggingface.co/docs
   - github.com, roadmap.sh, freecodecamp.org
   - go.dev/doc, rust-lang.org/learn, typescriptlang.org/docs
8. Return ONLY valid JSON, no markdown, no explanation."""


# ─── Step 1: Suggest 3 Projects ─────────────────────────────────────────────

async def suggest_projects(
    domain: str,
) -> Dict[str, Any]:
    """
    Generate 3 project suggestions (medium/hard) for a domain.

    Returns dict with a `projects` list of 3 items.
    """
    prompt = f"""Suggest 3 real-world coding projects for someone learning **{domain}**.
They want to finish each project in about 7 days.

For each project provide:
1. A clear project title
2. Difficulty: "medium" or "hard"
3. A 2-3 sentence description of the project and what it teaches
4. The tech stack (list of technologies)
5. Key skills they'll gain (3-4 items)
6. Estimated total hours to complete

Return JSON:
{{
  "domain": "{domain}",
  "projects": [
    {{
      "id": 1,
      "title": "Real-time Chat Application",
      "difficulty": "medium",
      "description": "Build a full-stack real-time chat app with rooms, typing indicators, and message persistence.",
      "techStack": ["React", "Node.js", "Socket.IO", "MongoDB"],
      "keySkills": ["WebSocket communication", "Real-time state sync", "Database design", "Authentication"],
      "estimatedHours": 14
    }}
  ]
}}"""

    try:
        result = await bedrock_client.generate_json(
            prompt=prompt,
            system_instruction=SUGGEST_SYSTEM,
            temperature=0.5,
        )

        projects = result.get("projects", [])[:3]
        validated = []
        for i, p in enumerate(projects):
            validated.append({
                "id": i + 1,
                "title": p.get("title", f"Project {i+1}"),
                "difficulty": p.get("difficulty", "medium"),
                "description": p.get("description", ""),
                "techStack": p.get("techStack", []),
                "keySkills": p.get("keySkills", []),
                "estimatedHours": p.get("estimatedHours", 14),
            })

        return {"domain": domain, "projects": validated}

    except Exception as e:
        logger.error("Project suggestion failed", error=str(e))
        raise ValueError("Failed to suggest projects. Please try again.")


# ─── Step 2: Generate 7-Day Plan ────────────────────────────────────────────

async def generate_day_plan(
    user_id: str,
    domain: str,
    project_title: str,
    project_description: str,
    tech_stack: List[str],
) -> Dict[str, Any]:
    """
    Generate a 7-day build plan for a chosen project, then store in DynamoDB.
    """
    tech_str = ", ".join(tech_stack) if tech_stack else "appropriate technologies"

    prompt = f"""Create a detailed 7-day build plan for this project:

**Project**: {project_title}
**Description**: {project_description}
**Tech Stack**: {tech_str}
**Domain**: {domain}

For each of the 7 days, provide:
1. **title** — a short phase name (e.g., "Architecture & Setup")
2. **description** — 2-3 sentences about what to accomplish
3. **tasks** — an array of 3-5 specific tasks for the day
4. **techDetails** — what specific technologies/tools to use and how
5. **architecture** — architecture or design notes relevant to this day's work
6. **resources** — 2-3 learning resources (title + url) for the day's topics
7. **estimatedHours** — hours for this day

Return JSON:
{{
  "projectTitle": "{project_title}",
  "projectDescription": "{project_description}",
  "techStack": {json.dumps(tech_stack)},
  "days": [
    {{
      "day": 1,
      "title": "Architecture & Project Setup",
      "description": "Design the system architecture and set up the development environment.",
      "tasks": [
        "Set up project repository with Git",
        "Initialize project with chosen framework",
        "Design database schema and API endpoints",
        "Set up development tools and linting"
      ],
      "techDetails": "Use Create React App or Vite for frontend scaffolding. Set up Express.js with TypeScript for the backend. Configure ESLint and Prettier.",
      "architecture": "Monorepo with /client and /server folders. REST API with JWT auth. PostgreSQL with Prisma ORM.",
      "resources": [
        {{"title": "React Documentation", "url": "https://react.dev/learn"}},
        {{"title": "Express.js Guide", "url": "https://developer.mozilla.org/en-US/docs/Learn/Server-side/Express_Nodejs"}}
      ],
      "estimatedHours": 2
    }}
  ]
}}"""

    try:
        result = await bedrock_client.generate_json(
            prompt=prompt,
            system_instruction=PLAN_SYSTEM,
            temperature=0.3,
        )

        days = result.get("days", [])[:7]
        validated_days = []
        for i, d in enumerate(days):
            validated_days.append({
                "day": i + 1,
                "title": d.get("title", f"Day {i+1}"),
                "description": d.get("description", ""),
                "tasks": d.get("tasks", [])[:6],
                "techDetails": d.get("techDetails", ""),
                "architecture": d.get("architecture", ""),
                "resources": [
                    {"title": r.get("title", "Resource"), "url": r.get("url", "#")}
                    for r in d.get("resources", [])[:3]
                ],
                "estimatedHours": d.get("estimatedHours", 1),
                "completedAt": None,
            })

    except Exception as e:
        logger.error("Day plan generation failed", error=str(e))
        raise ValueError("Failed to generate project plan. Please try again.")

    # Build and store roadmap
    roadmap_id = dynamo_service.generate_id()
    total_hours = sum(d["estimatedHours"] for d in validated_days)

    roadmap = {
        "projectRoadmapId": roadmap_id,
        "userId": user_id,
        "domain": domain,
        "projectTitle": project_title,
        "projectDescription": project_description,
        "techStack": tech_stack,
        "totalHours": total_hours,
        "days": validated_days,
        "completedDays": 0,
        "totalDays": len(validated_days),
        "unlockedAll": False,
        "createdAt": dynamo_service.now_iso(),
    }

    try:
        await dynamo_service.put_item("ProjectRoadmaps", roadmap)
        logger.info(
            "Project day plan generated",
            roadmapId=roadmap_id,
            userId=user_id,
            project=project_title,
        )
    except Exception as e:
        logger.warning("Failed to store project roadmap in DynamoDB", error=str(e))

    return roadmap


# ─── Fetch / List / Complete ─────────────────────────────────────────────────

async def get_project_roadmap(roadmap_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a specific project roadmap by ID."""
    try:
        from boto3.dynamodb.conditions import Attr
        results = await dynamo_service.scan(
            table="ProjectRoadmaps",
            filter_expression=Attr("projectRoadmapId").eq(roadmap_id),
            limit=1,
        )
        return results[0] if results else None
    except Exception as e:
        logger.warning("Failed to fetch project roadmap", error=str(e))
        return None


async def get_user_project_roadmaps(user_id: str) -> List[Dict[str, Any]]:
    """Fetch all project roadmaps for a user."""
    try:
        roadmaps = await dynamo_service.query(
            table="ProjectRoadmaps",
            pk_name="userId",
            pk_value=user_id,
            scan_forward=False,
        )
        return roadmaps
    except Exception as e:
        logger.warning("Failed to fetch user project roadmaps", error=str(e))
        return []


async def mark_day_complete(
    roadmap_id: str,
    day_number: int,
    user_id: str,
) -> Dict[str, Any]:
    """Mark a day in the roadmap as complete."""
    roadmap = await get_project_roadmap(roadmap_id)
    if not roadmap:
        raise ValueError("Project roadmap not found")

    if roadmap.get("userId") != user_id:
        raise ValueError("Unauthorized: roadmap belongs to another user")

    days = roadmap.get("days", [])
    if day_number < 1 or day_number > len(days):
        raise ValueError(f"Invalid day number: {day_number}")

    idx = day_number - 1

    # Enforce sequential completion: all previous days must be done
    for i in range(idx):
        if not days[i].get("completedAt"):
            raise ValueError(f"Cannot complete day {day_number}: day {i + 1} is not yet completed")

    if days[idx].get("completedAt"):
        raise ValueError(f"Day {day_number} is already completed")

    days[idx]["completedAt"] = dynamo_service.now_iso()
    completed_count = sum(1 for d in days if d.get("completedAt"))

    try:
        await dynamo_service.update_item(
            table="ProjectRoadmaps",
            key={"userId": user_id, "projectRoadmapId": roadmap_id},
            updates={
                "days": days,
                "completedDays": completed_count,
            },
        )
        logger.info("Day marked complete", roadmapId=roadmap_id, day=day_number)
    except Exception as e:
        logger.warning("Failed to update day completion", error=str(e))

    roadmap["days"] = days
    roadmap["completedDays"] = completed_count
    return roadmap


async def unlock_all_days(
    roadmap_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Set the unlockedAll flag so all days are accessible."""
    roadmap = await get_project_roadmap(roadmap_id)
    if not roadmap:
        raise ValueError("Project roadmap not found")

    if roadmap.get("userId") != user_id:
        raise ValueError("Unauthorized: roadmap belongs to another user")

    try:
        await dynamo_service.update_item(
            table="ProjectRoadmaps",
            key={"userId": user_id, "projectRoadmapId": roadmap_id},
            updates={"unlockedAll": True},
        )
        logger.info("All days unlocked", roadmapId=roadmap_id)
    except Exception as e:
        logger.warning("Failed to unlock all days", error=str(e))

    roadmap["unlockedAll"] = True
    return roadmap


async def delete_project_roadmap(
    roadmap_id: str,
    user_id: str,
) -> None:
    """Delete a project roadmap."""
    roadmap = await get_project_roadmap(roadmap_id)
    if not roadmap:
        raise ValueError("Project roadmap not found")

    if roadmap.get("userId") != user_id:
        raise ValueError("Unauthorized: roadmap belongs to another user")

    try:
        await dynamo_service.delete_item(
            table="ProjectRoadmaps",
            key={"userId": user_id, "projectRoadmapId": roadmap_id},
        )
        logger.info("Project roadmap deleted", roadmapId=roadmap_id, userId=user_id)
    except Exception as e:
        logger.warning("Failed to delete project roadmap", error=str(e))
        raise ValueError("Failed to delete roadmap")
