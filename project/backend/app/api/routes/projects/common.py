"""Router and DynamoDB mapping shared by the project route modules."""

from fastapi import APIRouter

router = APIRouter()


def _dynamo_to_response(p: dict) -> dict:
    """Normalise a DynamoDB project item to frontend-expected shape."""
    return {
        "id": p.get("projectId") or p.get("id", ""),
        "title": p.get("name") or p.get("title", ""),
        "description": p.get("description", ""),
        "technologies": p.get("technologies") or [],
        "highlights": p.get("highlights") or [],
        "url": p.get("repoUrl") or p.get("url") or p.get("demo_url"),
        "demo_url": p.get("demo_url"),
        "source_type": p.get("sourceType", "github"),
        "is_private": p.get("isPrivate", False),
        "is_verified": True,
        "is_featured": p.get("isFeatured", False),
        "start_date": p.get("start_date"),
        "end_date": p.get("end_date"),
        "created_at": p.get("createdAt", ""),
    }
