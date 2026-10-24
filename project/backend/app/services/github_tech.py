"""
GitHub repo analysis helpers
============================
Pure functions used by the GitHub ingestion service: mapping dependency
manifests to technology names, parsing repo URLs, and rendering the project
summary Markdown. No network or AWS calls.
"""

import json
import re
from typing import Any, Dict, List

# Mapping of package names to canonical technology names
TECH_MAPPING = {
    # JavaScript/TypeScript
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "nuxt": "Nuxt.js",
    "angular": "Angular",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "express": "Express.js",
    "fastify": "Fastify",
    "nestjs": "NestJS",
    "@nestjs/core": "NestJS",
    "typescript": "TypeScript",
    "tailwindcss": "Tailwind CSS",
    "prisma": "Prisma",
    "@prisma/client": "Prisma",
    "mongoose": "MongoDB",
    "sequelize": "Sequelize",
    "graphql": "GraphQL",
    "apollo-server": "Apollo GraphQL",
    "socket.io": "Socket.IO",
    "redis": "Redis",
    "webpack": "Webpack",
    "vite": "Vite",
    "jest": "Jest",
    "mocha": "Mocha",
    "cypress": "Cypress",
    "playwright": "Playwright",
    # Python
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "sqlalchemy": "SQLAlchemy",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "keras": "Keras",
    "celery": "Celery",
    "pytest": "Pytest",
    "pydantic": "Pydantic",
    "alembic": "Alembic",
    "beautifulsoup4": "Beautiful Soup",
    "scrapy": "Scrapy",
    "requests": "Requests",
    "httpx": "HTTPX",
    "aiohttp": "aiohttp",
    # Java
    "spring-boot": "Spring Boot",
    "spring-framework": "Spring Framework",
    "hibernate": "Hibernate",
    # Databases
    "pg": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "pymongo": "MongoDB",
    "sqlite3": "SQLite",
    # Cloud/DevOps
    "aws-sdk": "AWS",
    "boto3": "AWS",
    "@aws-sdk": "AWS",
    "google-cloud": "Google Cloud",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
}


# Characters that end the package name in a requirements.txt line (PEP 508)
_REQUIREMENT_NAME_END = re.compile(r"[<>=!~;\[\s@]")


def parse_package_json(content: str) -> List[str]:
    """Parse package.json and extract technologies."""
    technologies = []
    try:
        data = json.loads(content)
        deps = {
            **data.get("dependencies", {}),
            **data.get("devDependencies", {}),
        }

        for pkg_name in deps.keys():
            canonical = TECH_MAPPING.get(pkg_name.lower())
            if canonical:
                technologies.append(canonical)

        # Add Node.js/JavaScript by default
        technologies.append("Node.js")
        technologies.append("JavaScript")

    except json.JSONDecodeError:
        pass

    return list(set(technologies))


def parse_requirements_txt(content: str) -> List[str]:
    """Parse requirements.txt and extract technologies."""
    technologies = ["Python"]

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Package name is everything before a version specifier, extra, marker or URL
        pkg_name = _REQUIREMENT_NAME_END.split(line, maxsplit=1)[0].strip()
        canonical = TECH_MAPPING.get(pkg_name.lower())
        if canonical:
            technologies.append(canonical)

    return list(set(technologies))


def parse_pyproject_toml(content: str) -> List[str]:
    """Parse pyproject.toml and extract technologies."""
    technologies = ["Python"]

    # Simple parsing - look for known package names
    content_lower = content.lower()
    for pkg_name, canonical in TECH_MAPPING.items():
        if pkg_name in content_lower:
            technologies.append(canonical)

    return list(set(technologies))


def parse_repo_url(url: str) -> str:
    """Parse GitHub URL to get full_name (owner/repo)."""
    url = url.rstrip("/")
    if "github.com" in url:
        parts = url.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1].replace('.git', '')}"
    raise ValueError(f"Invalid GitHub URL: {url}")


def render_summary_md(name: str, summary: Dict[str, Any]) -> str:
    """Render the structured dict into the academia-sync.md format."""
    lines = [
        f"# {name}",
        "",
        "## 1. High-Level Pitch",
        f"- **One-Liner:** {summary.get('oneLiner', '')}",
        f"- **Problem Type:** {summary.get('problemType', '')}",
        f"- **Domain/Context:** {summary.get('domain', '')}",
        "",
        '## 2. Technical Implementation (The "How")',
        f"- **Languages:** {', '.join(summary.get('languages', []))}",
        f"- **Frameworks:** {', '.join(summary.get('frameworks', []))}",
        f"- **Infrastructure/Tools:** {', '.join(summary.get('infrastructure', []))}",
        f"- **Key Algorithms/Techniques:** {', '.join(summary.get('keyTechniques', []))}",
        "",
        "## 3. Specialized Capabilities (For JD Matching)",
    ]
    for cap in summary.get("capabilities", []):
        lines.append(f"- {cap}")
    lines += [
        "",
        "## 4. Impact & Metrics (CRITICAL)",
    ]
    for h in summary.get("highlights", []):
        lines.append(f"- {h}")
    return "\n".join(lines)
