"""
Legacy resume agent
===================
The M1 template-fill flow, kept for POST /api/resumes/{id}/generate. It asks
Claude to fill a LaTeX template directly instead of returning JSON.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from app.services.bedrock_client import bedrock_client

logger = structlog.get_logger()


@dataclass
class GenerationResult:
    """Result of legacy template-fill resume generation."""

    latex_content: str
    warnings: List[str]
    changes_made: List[str]
    tokens_used: int


# ──────────────────────────────────────────────────────────────────────────────
# Legacy M1 compatibility — kept for /{resume_id}/generate route
# ──────────────────────────────────────────────────────────────────────────────

_LEGACY_SYSTEM_PROMPT = r"""You are a professional resume LaTeX formatter. Your ONLY job is to fill a LaTeX template with provided user data.

CRITICAL RULES:
1. ONLY use information from <user_data>. NEVER invent facts.
2. If data is missing, omit that section entirely.
3. Resume MUST fit on ONE PAGE. Each project: EXACTLY 3 bullet points (80-100 chars each).
4. Use ONLY \textbf{}, \textit{}, \texttt{} for fonts. Never old-style commands.
5. Every { must have matching }. Escape special chars: & % $ # _ { } ~ ^
6. Return ONLY valid LaTeX code."""


class ResumeGenerationAgent:
    """Legacy agent for M1 template-fill flow. Kept for backward compatibility."""

    def __init__(self):
        pass

    async def generate_resume(
        self,
        template_latex: str,
        user_data: Dict[str, Any],
        jd_context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
    ) -> GenerationResult:
        user_data_str = self._format_user_data(user_data)

        jd_str = ""
        if jd_context:
            jd_str = (
                f"\n<jd_context>\nTarget Role: {jd_context.get('title', 'N/A')}\n"
                f"Company: {jd_context.get('company', 'N/A')}\n"
                f"Key Requirements: {', '.join(jd_context.get('required_skills', [])[:10])}\n"
                f"</jd_context>\n"
            )

        prompt = (
            f"Fill this LaTeX resume template with the provided user data.\n\n"
            f"<template>\n{template_latex}\n</template>\n\n"
            f"<user_data>\n{user_data_str}\n</user_data>\n\n"
            f"{jd_str}\n"
            f"Return ONLY the filled LaTeX code."
        )

        try:
            response = await bedrock_client.generate_content(
                prompt=prompt,
                system_instruction=_LEGACY_SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=8192,
            )

            latex_content = response.strip()
            if latex_content.startswith("```latex"):
                latex_content = latex_content[8:]
            elif latex_content.startswith("```"):
                latex_content = latex_content[3:]
            if latex_content.endswith("```"):
                latex_content = latex_content[:-3]
            latex_content = latex_content.strip()

            return GenerationResult(
                latex_content=latex_content,
                warnings=[],
                changes_made=["Filled template with user data"],
                tokens_used=len(response.split()),
            )
        except Exception as e:
            logger.error(f"Legacy resume generation failed: {e}")
            raise

    def _format_user_data(self, user_data: Dict[str, Any]) -> str:
        parts = []
        if "personal" in user_data:
            parts.append("PERSONAL INFORMATION:")
            for key, value in user_data["personal"].items():
                parts.append(f"  {key}: {value}")
        if "skills" in user_data:
            parts.append(f"\nSKILLS: {', '.join(user_data['skills'])}")
        if "projects" in user_data:
            parts.append("\nPROJECTS:")
            for i, proj in enumerate(user_data["projects"], 1):
                parts.append(f"\n  Project {i}:")
                parts.append(f"    Title: {proj.get('title', 'N/A')}")
                parts.append(f"    Description: {proj.get('description', 'N/A')}")
                if proj.get("technologies"):
                    parts.append(f"    Technologies: {', '.join(proj['technologies'])}")
                if proj.get("highlights"):
                    parts.append("    Achievements:")
                    for h in proj["highlights"]:
                        parts.append(f"      - {h}")
                if proj.get("url"):
                    parts.append(f"    URL: {proj['url']}")
        if "experience" in user_data and user_data["experience"]:
            parts.append("\nWORK EXPERIENCE:")
            for i, exp in enumerate(user_data["experience"], 1):
                parts.append(f"\n  Experience {i}:")
                parts.append(f"    Company: {exp.get('company', 'N/A')}")
                parts.append(f"    Title: {exp.get('title', 'N/A')}")
                parts.append(f"    Dates: {exp.get('dates', 'N/A')}")
                if exp.get("highlights"):
                    parts.append("    Responsibilities:")
                    for h in exp["highlights"]:
                        parts.append(f"      - {h}")
        if "education" in user_data and user_data["education"]:
            parts.append("\nEDUCATION:")
            for i, edu in enumerate(user_data["education"], 1):
                parts.append(f"\n  Education {i}:")
                parts.append(f"    School: {edu.get('school', 'N/A')}")
                parts.append(f"    Degree: {edu.get('degree', 'N/A')}")
                if edu.get("field"):
                    parts.append(f"    Field: {edu.get('field')}")
                parts.append(f"    Dates: {edu.get('dates', 'N/A')}")
                if edu.get("gpa"):
                    parts.append(f"    GPA: {edu.get('gpa')}")
        if "certifications" in user_data and user_data["certifications"]:
            parts.append("\nCERTIFICATIONS:")
            for cert in user_data["certifications"]:
                parts.append(f"  - {cert.get('name', 'N/A')} ({cert.get('issuer', '')})")
        return "\n".join(parts)


# Global instance (for legacy route compatibility)
resume_agent = ResumeGenerationAgent()
