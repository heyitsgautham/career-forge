"""
Matching Engine
===============
Ranks projects against job descriptions using multi-signal scoring.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date
import re
import structlog

from app.services.gemini_client import gemini_client
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, VectorStoreService


logger = structlog.get_logger()


@dataclass
class MatchScore:
    """Detailed match score breakdown."""
    project_id: str
    total_score: float
    semantic_score: float
    tech_overlap_score: float
    keyword_score: float
    recency_score: float
    match_explanation: str


class MatchingEngine:
    """
    Multi-signal matching engine for ranking projects against job descriptions.
    
    Scoring formula:
    FINAL_SCORE = (
        0.50 × semantic_similarity +
        0.30 × tech_overlap_score +
        0.15 × keyword_match_score +
        0.05 × recency_bonus
    )
    """
    
    # Scoring weights
    WEIGHT_SEMANTIC = 0.50
    WEIGHT_TECH = 0.30
    WEIGHT_KEYWORD = 0.15
    WEIGHT_RECENCY = 0.05
    
    # Minimum score threshold
    MIN_SCORE_THRESHOLD = 0.30
    
    def __init__(self):
        pass
    
    async def analyze_job_description(self, jd_text: str) -> Dict[str, Any]:
        """
        Analyze job description and extract structured requirements.
        
        Args:
            jd_text: Raw job description text
            
        Returns:
            Parsed JD data with skills, keywords, requirements
        """
        prompt = f"""Analyze this job description and extract structured information.

JOB DESCRIPTION:
{jd_text[:6000]}

Extract:
1. required_skills: List of explicitly required technical skills
2. preferred_skills: List of nice-to-have skills
3. keywords: Important technical keywords and concepts
4. experience_years: Min/max years if mentioned
5. responsibilities: Key job responsibilities
6. title: Job title
7. company: Company name if mentioned

Return as JSON object."""

        try:
            result = await gemini_client.generate_json(
                prompt=prompt,
                system_instruction="You are a job description analyzer. Extract accurate, structured information.",
                temperature=0.1,
            )
            return result
        except Exception as e:
            logger.error(f"JD analysis failed: {e}")
            return {
                "required_skills": [],
                "preferred_skills": [],
                "keywords": [],
                "experience_years": None,
                "responsibilities": [],
                "title": "",
                "company": "",
            }
    
    async def match_projects(
        self,
        user_id: str,
        jd_text: str,
        jd_embedding: Optional[List[float]] = None,
        parsed_jd: Optional[Dict[str, Any]] = None,
        top_n: int = 10,
    ) -> List[MatchScore]:
        """
        Match user's projects against a job description.
        
        Args:
            user_id: User ID to filter projects
            jd_text: Job description text
            jd_embedding: Pre-computed JD embedding (optional)
            parsed_jd: Pre-parsed JD data (optional)
            top_n: Number of top matches to return
            
        Returns:
            List of MatchScore objects, sorted by total_score descending
        """
        # Get JD embedding
        if jd_embedding is None:
            jd_embedding = await embedding_service.embed_text(jd_text)
        
        # Parse JD if not provided
        if parsed_jd is None:
            parsed_jd = await self.analyze_job_description(jd_text)
        
        # Get semantic matches from vector store
        semantic_results = await vector_store.search_similar(
            collection_name=VectorStoreService.COLLECTION_PROJECTS,
            query_embedding=jd_embedding,
            n_results=top_n * 2,  # Get more for filtering
            where={"user_id": user_id},
        )
        
        if not semantic_results:
            return []
        
        # Calculate detailed scores for each project
        scores = []
        jd_skills = set(s.lower() for s in (parsed_jd.get("required_skills", []) + parsed_jd.get("preferred_skills", [])))
        jd_keywords = set(k.lower() for k in parsed_jd.get("keywords", []))
        
        for result in semantic_results:
            project_id = result["id"]
            semantic_score = result.get("similarity", 0.5)
            
            # Parse project technologies from metadata
            tech_str = result.get("metadata", {}).get("technologies", "")
            project_tech = set(t.lower().strip() for t in tech_str.split(",") if t.strip())
            
            # Calculate tech overlap
            tech_overlap_score = self._calculate_tech_overlap(
                project_tech=project_tech,
                required_skills=set(s.lower() for s in parsed_jd.get("required_skills", [])),
                preferred_skills=set(s.lower() for s in parsed_jd.get("preferred_skills", [])),
            )
            
            # Calculate keyword match
            project_doc = result.get("document", "").lower()
            keyword_score = self._calculate_keyword_match(project_doc, jd_keywords)
            
            # Recency score (would need actual dates - using placeholder)
            recency_score = 0.5  # Default middle score without date info
            
            # Calculate final score
            total_score = (
                self.WEIGHT_SEMANTIC * semantic_score +
                self.WEIGHT_TECH * tech_overlap_score +
                self.WEIGHT_KEYWORD * keyword_score +
                self.WEIGHT_RECENCY * recency_score
            )
            
            # Generate explanation
            explanation = self._generate_match_explanation(
                semantic_score, tech_overlap_score, keyword_score, project_tech, jd_skills
            )
            
            scores.append(MatchScore(
                project_id=project_id,
                total_score=round(total_score, 3),
                semantic_score=round(semantic_score, 3),
                tech_overlap_score=round(tech_overlap_score, 3),
                keyword_score=round(keyword_score, 3),
                recency_score=round(recency_score, 3),
                match_explanation=explanation,
            ))
        
        # Sort by total score and filter
        scores.sort(key=lambda x: x.total_score, reverse=True)
        scores = [s for s in scores if s.total_score >= self.MIN_SCORE_THRESHOLD]
        
        # Ensure diversity (limit projects with very similar tech stacks)
        scores = self._ensure_diversity(scores, max_similar=2)
        
        return scores[:top_n]
    
    def _calculate_tech_overlap(
        self,
        project_tech: set,
        required_skills: set,
        preferred_skills: set,
    ) -> float:
        """Calculate technology overlap score."""
        if not required_skills and not preferred_skills:
            return 0.5  # Neutral if no skills specified
        
        # Required skills match (primary)
        required_matches = len(project_tech & required_skills)
        required_total = len(required_skills) or 1
        required_score = required_matches / required_total
        
        # Preferred skills match (bonus)
        preferred_matches = len(project_tech & preferred_skills)
        preferred_total = len(preferred_skills) or 1
        preferred_bonus = 0.2 * (preferred_matches / preferred_total)
        
        return min(required_score + preferred_bonus, 1.0)
    
    def _calculate_keyword_match(self, document: str, keywords: set) -> float:
        """Calculate keyword match score using simple matching."""
        if not keywords:
            return 0.5
        
        matched = sum(1 for kw in keywords if kw in document)
        return matched / len(keywords)
    
    def _generate_match_explanation(
        self,
        semantic: float,
        tech: float,
        keyword: float,
        project_tech: set,
        jd_skills: set,
    ) -> str:
        """Generate human-readable match explanation."""
        parts = []
        
        if semantic >= 0.7:
            parts.append("Strong semantic relevance")
        elif semantic >= 0.5:
            parts.append("Moderate semantic relevance")
        
        matched_tech = project_tech & jd_skills
        if matched_tech:
            parts.append(f"Matching skills: {', '.join(list(matched_tech)[:5])}")
        
        if tech >= 0.7:
            parts.append("Excellent tech stack match")
        elif tech >= 0.4:
            parts.append("Good tech stack overlap")
        
        return "; ".join(parts) if parts else "Potential match based on content"
    
    def _ensure_diversity(
        self,
        scores: List[MatchScore],
        max_similar: int = 2,
    ) -> List[MatchScore]:
        """
        Ensure diversity in results by limiting projects with very similar scores.
        """
        # Simple implementation: just return as-is for now
        # A more sophisticated version would compare tech stacks
        return scores
    
    async def select_top_projects(
        self,
        scores: List[MatchScore],
        min_projects: int = 3,
        max_projects: int = 6,
    ) -> List[MatchScore]:
        """
        Select top projects for resume based on scores.
        
        Args:
            scores: List of MatchScore objects
            min_projects: Minimum projects to include
            max_projects: Maximum projects to include
            
        Returns:
            Selected projects for resume
        """
        if len(scores) <= min_projects:
            return scores
        
        # Always include projects scoring above 0.6
        high_scoring = [s for s in scores if s.total_score >= 0.6]
        
        # Add more if needed up to max
        result = high_scoring[:max_projects]
        
        # If we don't have enough high-scoring, add lower ones
        if len(result) < min_projects:
            remaining = [s for s in scores if s not in result]
            result.extend(remaining[:min_projects - len(result)])
        
        return result


# Global instance
matching_engine = MatchingEngine()
