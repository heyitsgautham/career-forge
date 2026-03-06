"""
Match Scorer Service
====================
Scores job listings against a user's skill profile using a blend of
vector similarity (Titan embeddings) and keyword overlap.
"""

import math
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
import structlog

from app.services.embedding_service import embedding_service
from app.services.dynamo_service import dynamo_service

logger = structlog.get_logger()


@dataclass
class JobMatchScore:
    """Detailed match score for a user-job pair."""
    job_id: str
    total_score: float  # 0-100 percentage
    vector_score: float  # 0-1 cosine similarity
    keyword_score: float  # 0-1 overlap ratio
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    explanation: str = ""


class MatchScorer:
    """
    Match scoring engine for job-user fit.

    Score = (WEIGHT_VECTOR * vector_similarity + WEIGHT_KEYWORD * keyword_overlap) * 100

    Signals:
    1. Vector similarity: embed JD required skills → compare vs. user skill profile vector
    2. Keyword overlap: count matching skills between user skills and JD required skills
    """

    WEIGHT_VECTOR = 0.55
    WEIGHT_KEYWORD = 0.45

    async def compute_match(
        self,
        user_skills: List[str],
        user_skill_embedding: Optional[List[float]],
        job: Dict[str, Any],
    ) -> JobMatchScore:
        """
        Compute match score for a single user-job pair.

        Args:
            user_skills: List of user's skills (strings)
            user_skill_embedding: Pre-computed embedding of user's skill profile
            job: Job dict from DynamoDB (must have requiredSkills, description)

        Returns:
            JobMatchScore with detailed breakdown
        """
        job_id = job.get("jobId", "")
        required_skills = job.get("requiredSkills", [])
        preferred_skills = job.get("preferredSkills", [])
        description = job.get("description", "")

        # Combine required + preferred for full skill set
        all_job_skills = required_skills + preferred_skills

        # 1. Keyword overlap score
        keyword_score, matched, missing = self._keyword_overlap(
            user_skills, required_skills
        )

        # 2. Vector similarity score
        vector_score = 0.5  # default
        if user_skill_embedding and (all_job_skills or description):
            try:
                # Build text to embed for the job
                job_text = ", ".join(all_job_skills) if all_job_skills else description[:2000]
                job_embedding = await embedding_service.embed_text(job_text)
                vector_score = self._cosine_similarity(user_skill_embedding, job_embedding)
            except Exception as e:
                logger.warning(f"Embedding comparison failed for job {job_id}: {e}")

        # Weighted blend → percentage
        raw_score = (
            self.WEIGHT_VECTOR * vector_score
            + self.WEIGHT_KEYWORD * keyword_score
        )
        total_pct = round(min(raw_score * 100, 100), 1)

        explanation = self._build_explanation(
            vector_score, keyword_score, matched, missing
        )

        return JobMatchScore(
            job_id=job_id,
            total_score=total_pct,
            vector_score=round(vector_score, 3),
            keyword_score=round(keyword_score, 3),
            matched_skills=matched,
            missing_skills=missing,
            explanation=explanation,
        )

    async def score_all_jobs(
        self,
        user_id: str,
        user_skills: List[str],
        jobs: List[Dict[str, Any]],
    ) -> List[JobMatchScore]:
        """
        Score all jobs against a user's profile and store results.

        Args:
            user_id: User ID for storage
            user_skills: User's skill list
            jobs: List of job dicts from DynamoDB

        Returns:
            List of JobMatchScore sorted by total_score descending
        """
        if not user_skills:
            logger.warning(f"No user skills for {user_id}, scores will be low")
            user_skills = []

        # Pre-compute user skill embedding
        user_skill_embedding = None
        if user_skills:
            try:
                skill_text = ", ".join(user_skills)
                user_skill_embedding = await embedding_service.embed_text(skill_text)
            except Exception as e:
                logger.warning(f"User skill embedding failed: {e}")

        # Score each job
        scores = []
        for job in jobs:
            score = await self.compute_match(
                user_skills=user_skills,
                user_skill_embedding=user_skill_embedding,
                job=job,
            )
            scores.append(score)

        # Sort descending
        scores.sort(key=lambda s: s.total_score, reverse=True)

        # Store scores in DynamoDB
        for score in scores:
            try:
                updates = {
                    "matchScore": score.total_score,
                    "matchBreakdown": {
                        "vectorScore": score.vector_score,
                        "keywordScore": score.keyword_score,
                        "matchedSkills": score.matched_skills,
                        "explanation": score.explanation,
                    },
                    "missingSkills": score.missing_skills,
                    "updatedAt": dynamo_service.now_iso(),
                }
                await dynamo_service.update_item(
                    "Jobs", {"jobId": score.job_id}, updates
                )
            except Exception as e:
                logger.error(f"Failed to store match score for {score.job_id}: {e}")

        logger.info(
            f"Scored {len(scores)} jobs for user {user_id}",
            top_score=scores[0].total_score if scores else 0,
        )
        return scores

    def _keyword_overlap(
        self,
        user_skills: List[str],
        required_skills: List[str],
    ) -> tuple:
        """
        Calculate keyword overlap between user skills and job required skills.

        Returns:
            (score: float, matched: list, missing: list)
        """
        if not required_skills:
            return 0.5, [], []  # neutral when no skills specified

        user_set = set(s.lower().strip() for s in user_skills)
        required_set = set(s.lower().strip() for s in required_skills)

        matched = [s for s in required_skills if s.lower().strip() in user_set]
        missing = [s for s in required_skills if s.lower().strip() not in user_set]

        # Also check partial matches (e.g., "React" in user matches "React.js" in JD)
        still_missing = []
        for skill in missing:
            skill_lower = skill.lower()
            if any(
                skill_lower in us or us in skill_lower
                for us in user_set
            ):
                matched.append(skill)
            else:
                still_missing.append(skill)

        score = len(matched) / len(required_set) if required_set else 0.5
        return min(score, 1.0), matched, still_missing

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = dot / (norm_a * norm_b)
        # Clamp to [0, 1]
        return max(0.0, min(1.0, similarity))

    @staticmethod
    def _build_explanation(
        vector_score: float,
        keyword_score: float,
        matched: List[str],
        missing: List[str],
    ) -> str:
        """Build human-readable match explanation."""
        parts = []

        if keyword_score >= 0.8:
            parts.append("Excellent skill match")
        elif keyword_score >= 0.5:
            parts.append("Good skill overlap")
        elif keyword_score >= 0.3:
            parts.append("Partial skill match")
        else:
            parts.append("Limited skill overlap")

        if matched:
            parts.append(f"Matching: {', '.join(matched[:5])}")

        if missing:
            parts.append(f"To learn: {', '.join(missing[:3])}")

        if vector_score >= 0.8:
            parts.append("Strong semantic match")
        elif vector_score >= 0.6:
            parts.append("Good semantic relevance")

        return " · ".join(parts)


# Global instance
match_scorer = MatchScorer()
