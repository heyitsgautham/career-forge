"""
GitHub Ingestion Service
========================
Fetches and processes GitHub repositories.
Uses GitHub App installation tokens for repo access
and Bedrock for structured project summaries.

Reading from GitHub lives in GitHubRepoClient (github_repos.py). This module
adds the Bedrock summary and the S3 and DynamoDB writes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import settings
from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service
from app.services.github_repos import GitHubRepoClient
from app.services.github_tech import render_summary_md
from app.services.s3_service import s3_service

logger = structlog.get_logger()


class GitHubIngestionService(GitHubRepoClient):
    """
    Service for ingesting GitHub repositories.
    Extracts metadata, README, and tech stack.
    Uses GitHub App installation tokens for scoped repo access.
    """

    async def create_project_from_repo(
        self,
        repo_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create project data from repository data.
        Uses Bedrock to generate a structured summary matching the academia-sync.md schema.

        Args:
            repo_data: Repository data dict

        Returns:
            Project data with structured summary, md content, technologies, highlights
        """
        name = repo_data["name"]
        logger.info(
            "create_project_from_repo: calling _generate_structured_summary",
            repo=name,
            languages=list(repo_data.get("languages", {}).keys()),
            readme_len=len(repo_data.get("readme_content") or ""),
            dep_tech=repo_data.get("extracted_tech", []),
        )
        try:
            summary = await self._generate_structured_summary(
                name=name,
                description=repo_data.get("description", ""),
                languages=repo_data.get("languages", {}),
                topics=repo_data.get("topics", []),
                stars=repo_data.get("stars", 0),
                readme=repo_data.get("readme_content"),
                root_dirs=repo_data.get("root_dirs", []),
                dep_tech=repo_data.get("extracted_tech", []),
            )
            logger.info(
                "create_project_from_repo: Bedrock summary OK",
                repo=name,
                oneLiner=summary.get("oneLiner", "")[:80],
                highlights_count=len(summary.get("highlights", [])),
            )
        except Exception as e:
            logger.error(
                "create_project_from_repo: Bedrock summary FAILED", repo=name, error=str(e)
            )
            raise
        md_content = render_summary_md(name, summary)
        return {
            "summary": summary,
            "summaryMd": md_content,
            "technologies": summary.get("languages", [])
            + summary.get("frameworks", [])
            + summary.get("infrastructure", []),
            "highlights": summary.get("highlights", []),
            "description": repo_data.get("description") or summary.get("oneLiner", ""),
        }

    async def _generate_structured_summary(
        self,
        name: str,
        description: str,
        languages: Dict[str, int],
        topics: List[str],
        stars: int,
        readme: Optional[str],
        root_dirs: List[str],
        dep_tech: List[str],
    ) -> Dict[str, Any]:
        """Generate a structured project summary using Bedrock."""
        context = f"""REPO NAME: {name}
GITHUB DESCRIPTION: {description or 'N/A'}
LANGUAGES (by bytes): {', '.join(languages.keys()) or 'N/A'}
DETECTED TECHNOLOGIES: {', '.join(dep_tech) or 'N/A'}
TOPICS: {', '.join(topics) or 'N/A'}
STARS: {stars}
ROOT FOLDERS: {', '.join(root_dirs) or 'N/A'}
README (first 3000 chars):
{readme[:3000] if readme else 'No README available.'}"""

        prompt = f"""{context}

Based ONLY on the above, produce a JSON object with these exact keys:
{{
  "oneLiner": "One sentence describing what this project does and who it's for.",
  "problemType": "e.g. Full Stack Web App / CLI Tool / ML Model / API Service / DevOps Tool",
  "domain": "e.g. EdTech / FinTech / DevTools / Healthcare",
  "languages": ["TypeScript", "Python"],
  "frameworks": ["Next.js", "FastAPI"],
  "infrastructure": ["Docker", "AWS", "Terraform"],
  "keyTechniques": ["JWT auth with refresh tokens", "Role-Based Access Control"],
  "capabilities": [
    "2-4 specialized capabilities useful for JD matching — what this project uniquely demonstrates"
  ],
  "highlights": [
    "2-4 resume bullet points starting with action verbs, grounded in the content above"
  ]
}}

RULES:
1. ONLY use information from the content above — never invent metrics or features
2. If information is absent, use an empty list [] — never guess
3. Return ONLY the JSON object, no markdown fences"""

        try:
            logger.info("_generate_structured_summary: calling Bedrock generate_json", repo=name)
            result = await bedrock_client.generate_json(
                prompt=prompt,
                system_instruction="You are a technical resume analyst. Produce accurate, grounded project summaries. Never invent information.",
                temperature=0.2,
            )
            if isinstance(result, dict):
                logger.info(
                    "_generate_structured_summary: Bedrock OK", repo=name, keys=list(result.keys())
                )
                return result
            else:
                logger.warning(
                    "_generate_structured_summary: Bedrock returned non-dict",
                    repo=name,
                    type=type(result).__name__,
                    value=str(result)[:200],
                )
        except Exception as e:
            logger.error(
                f"_generate_structured_summary: Bedrock FAILED for {name}: {type(e).__name__}: {e}"
            )

        # Fallback: minimal summary
        return {
            "oneLiner": description or f"GitHub project: {name}",
            "problemType": "Software Project",
            "domain": "General",
            "languages": list(languages.keys()),
            "frameworks": [],
            "infrastructure": [],
            "keyTechniques": [],
            "capabilities": [],
            "highlights": [f"Developed {name} using {', '.join(list(languages.keys())[:3])}"],
        }

    async def ingest_and_embed_repo(
        self,
        repo_data: Dict[str, Any],
        project_data: Dict[str, Any],
        user_id: str,
        project_id: str,
    ) -> str:
        """
        Upload .md summary to S3 and store structured project item in DynamoDB.

        Args:
            repo_data: Raw GitHub repository data
            project_data: Output of create_project_from_repo()
            user_id: User ID
            project_id: Generated project UUID

        Returns:
            Project ID
        """
        name = repo_data["name"]
        md_content = project_data["summaryMd"]

        # 1. Upload .md summary to S3
        s3_key = f"{user_id}/{name}-summary.md"
        logger.info("ingest_and_embed_repo: uploading to S3", repo=name, s3_key=s3_key)
        try:
            await s3_service.upload_file(
                key=s3_key,
                data=md_content.encode("utf-8"),
                content_type="text/markdown",
            )
            logger.info("ingest_and_embed_repo: S3 upload OK", repo=name, s3_key=s3_key)
        except Exception as e:
            logger.error(
                "ingest_and_embed_repo: S3 upload FAILED", repo=name, s3_key=s3_key, error=str(e)
            )
            raise

        # 2. Write structured item to DynamoDB
        summary = project_data["summary"]
        now = datetime.utcnow().isoformat()
        project_item = {
            "userId": user_id,
            "projectId": project_id,
            "name": name,
            "description": project_data["description"],
            "oneLiner": summary.get("oneLiner", ""),
            "problemType": summary.get("problemType", ""),
            "domain": summary.get("domain", ""),
            "technologies": project_data["technologies"],
            "languages": repo_data.get("languages", {}),
            "frameworks": summary.get("frameworks", []),
            "infrastructure": summary.get("infrastructure", []),
            "capabilities": summary.get("capabilities", []),
            "highlights": project_data["highlights"],
            "topics": repo_data.get("topics", []),
            "repoUrl": repo_data.get("url", ""),
            "stars": repo_data.get("stars", 0),
            "isFork": repo_data.get("is_fork", False),
            "isPrivate": repo_data.get("is_private", False),
            "pushedAt": repo_data.get("pushed_at"),
            "sourceType": "github",
            "githubId": repo_data.get("github_id"),
            "summaryS3Key": s3_key,
            "createdAt": now,
            "updatedAt": now,
        }
        logger.info(
            "ingest_and_embed_repo: writing to DynamoDB",
            repo=name,
            project_id=project_id,
            technologies=project_data["technologies"],
            highlights_count=len(project_data["highlights"]),
        )
        try:
            await dynamo_service.put_item(
                table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
                item=project_item,
            )
            logger.info(
                "ingest_and_embed_repo: DynamoDB write OK", repo=name, project_id=project_id
            )
        except Exception as e:
            logger.error(
                "ingest_and_embed_repo: DynamoDB write FAILED",
                repo=name,
                project_id=project_id,
                error=str(e),
            )
            raise

        logger.info("Ingested repo to DynamoDB + S3", repo=name, project_id=project_id)
        return project_id


# Global instance
github_service = GitHubIngestionService()
