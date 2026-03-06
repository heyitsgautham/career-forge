"""
JD Analyzer Service
===================
Analyzes job descriptions using AWS Bedrock (Claude/Nova).
Extracts structured data: skills, category, experience level, ATS keywords.
Replaces the old Vertex AI / Gemini-based analyzer.
"""

import asyncio
from typing import List, Dict, Any, Optional
import structlog

from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service

logger = structlog.get_logger()


class JDAnalyzer:
    """
    AI-powered job description analyzer.
    Uses Bedrock to extract structured information from raw JD text.
    """

    ANALYSIS_PROMPT = """Analyze this job description and extract structured information.

JOB DESCRIPTION:
{jd_text}

Extract the following fields and return as a JSON object:
{{
  "category": "The job category (e.g., 'Backend SDE', 'Frontend Developer', 'DevOps Engineer', 'Full Stack', 'ML Engineer', 'Data Engineer', 'SRE', 'Cloud Architect')",
  "requiredSkills": ["List of explicitly required technical skills — be specific, e.g. 'Python', 'FastAPI', 'PostgreSQL', 'Docker'"],
  "preferredSkills": ["Nice-to-have skills mentioned"],
  "experienceLevel": "Entry / 0-2 years, Mid / 2-5 years, or Senior / 5+ years — infer from the JD",
  "salary": "Salary range if mentioned, else null",
  "atsKeywords": ["Important ATS keywords and phrases from the JD that a resume should include"],
  "isPaid": true,
  "keyResponsibilities": ["Top 3-5 key responsibilities"],
  "companySize": "Startup / Mid / Enterprise — infer if possible, else null"
}}

Rules:
- Extract ONLY skills explicitly mentioned or strongly implied
- Keep skill names normalized (e.g., "JavaScript" not "JS", "PostgreSQL" not "postgres")
- ATS keywords should be distinct from skills — focus on concepts, methodologies, domain terms
- If salary is not mentioned, set to null
- isPaid should be false only for clearly unpaid internships

Return ONLY valid JSON, no markdown, no code blocks, no explanation."""

    async def analyze_single(self, jd_text: str) -> Dict[str, Any]:
        """
        Analyze a single job description.

        Args:
            jd_text: Raw job description text

        Returns:
            Structured analysis dict
        """
        if not jd_text or len(jd_text.strip()) < 20:
            return self._empty_analysis()

        try:
            result = await bedrock_client.generate_json(
                prompt=self.ANALYSIS_PROMPT.format(jd_text=jd_text[:6000]),
                system_instruction=(
                    "You are an expert job description analyzer for tech roles. "
                    "Extract accurate, structured information. Return valid JSON only."
                ),
                temperature=0.1,
            )

            # Normalize the result
            return self._normalize_analysis(result)

        except Exception as e:
            logger.error("JD analysis failed, using fallback", error=str(e))
            return self._fallback_analysis(jd_text)

    async def analyze_batch(
        self,
        jobs: List[Dict[str, Any]],
        concurrency: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple job descriptions concurrently.

        Args:
            jobs: List of job dicts (must have 'description' field)
            concurrency: Max concurrent Bedrock calls

        Returns:
            List of analysis results (same order as input)
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _analyze_one(job: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                description = job.get("description", "")
                analysis = await self.analyze_single(description)
                return {**analysis, "jobId": job.get("jobId")}

        results = await asyncio.gather(
            *[_analyze_one(job) for job in jobs],
            return_exceptions=True,
        )

        # Handle exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch analysis failed for job {i}", error=str(result))
                processed.append({
                    **self._empty_analysis(),
                    "jobId": jobs[i].get("jobId"),
                })
            else:
                processed.append(result)

        return processed

    async def analyze_and_store(
        self,
        jobs: List[Dict[str, Any]],
    ) -> int:
        """
        Analyze jobs and update their DynamoDB records with enriched data.

        Args:
            jobs: List of job dicts from DynamoDB (must have jobId)

        Returns:
            Number of successfully analyzed jobs
        """
        # Filter to only unanalyzed jobs
        unanalyzed = [j for j in jobs if not j.get("isAnalyzed")]

        if not unanalyzed:
            logger.info("All jobs already analyzed")
            return 0

        logger.info(f"Analyzing {len(unanalyzed)} jobs with Bedrock")
        analyses = await self.analyze_batch(unanalyzed)

        success_count = 0
        for job, analysis in zip(unanalyzed, analyses):
            job_id = job["jobId"]
            try:
                updates = {
                    "category": analysis.get("category"),
                    "requiredSkills": analysis.get("requiredSkills", []),
                    "preferredSkills": analysis.get("preferredSkills", []),
                    "experienceLevel": analysis.get("experienceLevel"),
                    "salary": analysis.get("salary") or job.get("salary"),
                    "atsKeywords": analysis.get("atsKeywords", []),
                    "isPaid": analysis.get("isPaid", True),
                    "keyResponsibilities": analysis.get("keyResponsibilities", []),
                    "isAnalyzed": True,
                    "updatedAt": dynamo_service.now_iso(),
                }
                await dynamo_service.update_item("Jobs", {"jobId": job_id}, updates)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to store analysis for job {job_id}", error=str(e))

        logger.info(f"Analyzed {success_count}/{len(unanalyzed)} jobs")
        return success_count

    def _normalize_analysis(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize analysis result to ensure consistent structure."""
        return {
            "category": raw.get("category", "Unknown"),
            "requiredSkills": self._ensure_list(raw.get("requiredSkills", [])),
            "preferredSkills": self._ensure_list(raw.get("preferredSkills", [])),
            "experienceLevel": raw.get("experienceLevel", "Unknown"),
            "salary": raw.get("salary"),
            "atsKeywords": self._ensure_list(raw.get("atsKeywords", [])),
            "isPaid": raw.get("isPaid", True),
            "keyResponsibilities": self._ensure_list(raw.get("keyResponsibilities", [])),
            "companySize": raw.get("companySize"),
        }

    def _fallback_analysis(self, jd_text: str) -> Dict[str, Any]:
        """Keyword-based fallback when AI analysis fails."""
        text_lower = jd_text.lower()

        SKILL_KEYWORDS = {
            "python": "Python", "java": "Java", "javascript": "JavaScript",
            "typescript": "TypeScript", "react": "React", "next.js": "Next.js",
            "node.js": "Node.js", "node": "Node.js", "fastapi": "FastAPI",
            "django": "Django", "flask": "Flask", "spring": "Spring Boot",
            "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
            "mysql": "MySQL", "mongodb": "MongoDB", "redis": "Redis",
            "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
            "aws": "AWS", "gcp": "GCP", "azure": "Azure",
            "terraform": "Terraform", "ci/cd": "CI/CD", "git": "Git",
            "graphql": "GraphQL", "rest api": "REST API", "microservices": "Microservices",
            "sql": "SQL", "linux": "Linux", "kafka": "Kafka",
            "machine learning": "Machine Learning", "tensorflow": "TensorFlow",
            "pytorch": "PyTorch",
        }

        found_skills = []
        for keyword, skill_name in SKILL_KEYWORDS.items():
            if keyword in text_lower and skill_name not in found_skills:
                found_skills.append(skill_name)

        # Infer category
        category = "Software Engineer"
        if any(k in text_lower for k in ["backend", "server-side", "api"]):
            category = "Backend SDE"
        elif any(k in text_lower for k in ["frontend", "front-end", "ui", "react"]):
            category = "Frontend Developer"
        elif any(k in text_lower for k in ["full stack", "fullstack"]):
            category = "Full Stack"
        elif any(k in text_lower for k in ["devops", "sre", "reliability"]):
            category = "DevOps/SRE"
        elif any(k in text_lower for k in ["machine learning", "ml", "data science", "ai"]):
            category = "ML Engineer"
        elif any(k in text_lower for k in ["data engineer", "etl", "pipeline"]):
            category = "Data Engineer"

        # Infer experience level
        experience = "Entry / 0-2 years"
        if any(k in text_lower for k in ["senior", "5+ years", "7+ years", "lead"]):
            experience = "Senior / 5+ years"
        elif any(k in text_lower for k in ["mid", "3+ years", "2-5 years", "3-5 years"]):
            experience = "Mid / 2-5 years"

        return {
            "category": category,
            "requiredSkills": found_skills[:10],
            "preferredSkills": [],
            "experienceLevel": experience,
            "salary": None,
            "atsKeywords": found_skills[:5],
            "isPaid": "unpaid" not in text_lower,
            "keyResponsibilities": [],
            "companySize": None,
        }

    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis structure."""
        return {
            "category": "Unknown",
            "requiredSkills": [],
            "preferredSkills": [],
            "experienceLevel": "Unknown",
            "salary": None,
            "atsKeywords": [],
            "isPaid": True,
            "keyResponsibilities": [],
            "companySize": None,
        }

    @staticmethod
    def _ensure_list(val) -> list:
        """Ensure value is a list."""
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return []


# Global instance
jd_analyzer = JDAnalyzer()
