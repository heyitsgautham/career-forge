"""
Job description analysis for saved job descriptions
===================================================
The three steps POST /api/jobs/{id}/analyze runs, shared by the DynamoDB and
SQLite code paths: parse the text into skills, store an embedding for later
matching, and rank the user's projects against the description.

Each step degrades instead of failing the request. A Bedrock outage falls back
to keyword skills, and a missing embedding or vector store yields no matches.
"""

from typing import List, Optional

import structlog

from app.schemas.jobs import ProjectMatch
from app.services.embedding_service import embedding_service
from app.services.matching_engine import matching_engine
from app.services.vector_store import VectorStoreService, vector_store

logger = structlog.get_logger()

#: Skills looked for by plain substring when the model is unavailable.
FALLBACK_SKILLS = [
    "python",
    "java",
    "javascript",
    "react",
    "node",
    "sql",
    "aws",
    "docker",
    "kubernetes",
    "git",
    "api",
    "rest",
    "graphql",
    "typescript",
]


def fallback_required_skills(raw_text: str) -> List[str]:
    """Up to ten FALLBACK_SKILLS that appear in the text."""
    text_lower = raw_text.lower()
    return [s for s in FALLBACK_SKILLS if s in text_lower][:10]


async def parse_requirements(raw_text: str) -> Optional[dict]:
    """The model's reading of the description, or None when it could not run."""
    try:
        return await matching_engine.analyze_job_description(raw_text)
    except Exception as e:
        logger.warning("jd_parse_failed_using_keywords", error=str(e))
        return None


async def store_embedding(user_id: str, title: str, company: str, raw_text: str) -> Optional[str]:
    """Embeds the description into the vector store and returns its id, or None on failure."""
    try:
        embedding = await embedding_service.embed_text(raw_text)
        embedding_id = vector_store.generate_embedding_id()
        await vector_store.add_embedding(
            collection_name=VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
            embedding_id=embedding_id,
            embedding=embedding,
            metadata={"user_id": user_id, "title": title, "company": company},
            document=raw_text,
        )
        return embedding_id
    except Exception as e:
        logger.warning("jd_embedding_failed", error=str(e))
        return None


async def match_projects(
    user_id: str,
    raw_text: str,
    embedding_id: Optional[str],
    parsed: Optional[dict],
    top_n: int,
) -> List[ProjectMatch]:
    """The user's projects ranked against the description, or [] when matching cannot run."""
    try:
        jd_embedding = None
        if embedding_id:
            stored = await vector_store.get_by_id(
                VectorStoreService.COLLECTION_JOB_DESCRIPTIONS, embedding_id
            )
            if stored:
                jd_embedding = stored.get("embedding")
        if not jd_embedding:
            jd_embedding = await embedding_service.embed_text(raw_text)

        matches = await matching_engine.match_projects(
            user_id=user_id,
            jd_text=raw_text,
            jd_embedding=jd_embedding,
            parsed_jd=parsed,
            top_n=top_n,
        )
    except Exception as e:
        logger.warning("jd_matching_failed", error=str(e))
        return []
    return [
        ProjectMatch(
            project_id=m.project_id,
            total_score=m.total_score,
            semantic_score=m.semantic_score,
            tech_overlap_score=m.tech_overlap_score,
            keyword_score=m.keyword_score,
            match_explanation=m.match_explanation,
        )
        for m in matches
    ]
