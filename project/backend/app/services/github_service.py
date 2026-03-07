"""
GitHub Ingestion Service
========================
Fetches and processes GitHub repositories.
Uses GitHub App installation tokens for repo access
and Bedrock for structured project summaries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import base64
import time
import uuid
import structlog
from github import Github, GithubException
from github.Repository import Repository
import httpx
import jwt as pyjwt

from app.core.config import settings
from app.core.security import token_encryptor
from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service
from app.services.s3_service import s3_service


logger = structlog.get_logger()


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
    "redis": "Redis",
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


class GitHubIngestionService:
    """
    Service for ingesting GitHub repositories.
    Extracts metadata, README, and tech stack.
    Uses GitHub App installation tokens for scoped repo access.
    """
    
    def __init__(self):
        self._cached_pem: Optional[str] = None
    
    def _get_github_client(self, encrypted_token: str) -> Github:
        """Create GitHub client with decrypted token."""
        token = token_encryptor.decrypt(encrypted_token)
        return Github(token)
    
    async def get_installation_token(self, installation_id: int) -> str:
        """Generate an installation access token scoped to repos the user selected."""
        import boto3
        
        # Load private key from Secrets Manager (cache for session)
        if not self._cached_pem:
            try:
                sm = boto3.client("secretsmanager", region_name=settings.AWS_REGION)
                self._cached_pem = sm.get_secret_value(
                    SecretId=settings.GITHUB_APP_PRIVATE_KEY_SECRET
                )["SecretString"]
            except Exception as e:
                logger.error("Failed to load GitHub App private key from Secrets Manager", error=str(e))
                raise
        
        # Sign a 10-min JWT as the GitHub App
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 540, "iss": settings.GITHUB_APP_ID}
        app_jwt = pyjwt.encode(payload, self._cached_pem, algorithm="RS256")
        
        # Exchange for an installation access token
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            r.raise_for_status()
            return r.json()["token"]  # short-lived token, valid 1hr
    
    async def fetch_user_repos_fast(
        self,
        encrypted_token: str,
        installation_id: Optional[int] = None,
        include_forks: bool = True,
        include_private: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL repositories using direct GitHub API (faster, async).
        If installation_id is provided, uses GitHub App installation token
        and fetches only user-selected repos.
        
        Args:
            encrypted_token: Encrypted GitHub access token (fallback for OAuth)
            installation_id: GitHub App installation ID (preferred)
            include_forks: Include forked repositories
            include_private: Include private repositories
            
        Returns:
            List of all repository metadata dicts
        """
        all_repos = []
        page = 1
        per_page = 100
        
        # Determine token and URL based on installation_id
        if installation_id:
            try:
                token = await self.get_installation_token(installation_id)
                use_installation_api = True
                logger.info("Using GitHub App installation token", installation_id=installation_id)
            except Exception as e:
                logger.warning("Installation token failed, falling back to OAuth", error=str(e))
                token = token_encryptor.decrypt(encrypted_token)
                use_installation_api = False
        else:
            token = token_encryptor.decrypt(encrypted_token)
            use_installation_api = False
        
        async with httpx.AsyncClient() as client:
            while True:
                if use_installation_api:
                    # /installation/repositories returns ONLY user-selected repos
                    response = await client.get(
                        "https://api.github.com/installation/repositories",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        params={
                            "per_page": per_page,
                            "page": page,
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    repos_data = data.get("repositories", [])
                else:
                    response = await client.get(
                        "https://api.github.com/user/repos",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        params={
                            "affiliation": "owner",
                            "sort": "updated",
                            "direction": "desc",
                            "per_page": per_page,
                            "page": page,
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    repos_data = response.json()
                
                # No more repos to fetch
                if not repos_data:
                    break
                
                for repo in repos_data:
                    # Apply filters
                    if not include_forks and repo.get("fork", False):
                        continue
                    if not include_private and repo.get("private", False):
                        continue
                    
                    all_repos.append({
                        "github_id": repo["id"],
                        "full_name": repo["full_name"],
                        "name": repo["name"],
                        "description": repo.get("description") or "",
                        "url": repo["html_url"],
                        "homepage": repo.get("homepage"),
                        "languages": {},
                        "topics": repo.get("topics", []),
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "watchers": repo.get("watchers_count", 0),
                        "open_issues": repo.get("open_issues_count", 0),
                        "is_fork": repo.get("fork", False),
                        "is_private": repo.get("private", False),
                        "is_archived": repo.get("archived", False),
                        "created_at": repo.get("created_at"),
                        "pushed_at": repo.get("pushed_at"),
                        "default_branch": repo.get("default_branch"),
                        "language": repo.get("language"),
                    })
                
                # If we got less than per_page, we've reached the end
                if len(repos_data) < per_page:
                    break
                    
                page += 1
        
        logger.info(f"Fetched {len(all_repos)} total repositories via direct API")
        return all_repos
    
    async def fetch_user_repos(
        self,
        encrypted_token: str,
        include_forks: bool = False,
        include_private: bool = True,
        min_stars: int = 0,
        page: int = 1,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch repositories for the authenticated user with pagination.
        
        Args:
            encrypted_token: Encrypted GitHub access token
            include_forks: Include forked repositories
            include_private: Include private repositories
            min_stars: Minimum star count filter
            page: Page number (1-indexed)
            per_page: Number of results per page (max 100)
            
        Returns:
            List of repository metadata dicts
        """
        gh = self._get_github_client(encrypted_token)
        user = gh.get_user()
        repos = []
        
        # PyGithub uses 0-based indexing internally but we use 1-based for API consistency
        # Get all repos first, then paginate (PyGithub handles this efficiently)
        all_repos = user.get_repos(affiliation="owner", sort="updated", direction="desc")
        
        # Calculate pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        count = 0
        for repo in all_repos:
            # Apply filters
            if not include_forks and repo.fork:
                continue
            if not include_private and repo.private:
                continue
            if repo.stargazers_count < min_stars:
                continue
            
            # Apply pagination
            if count >= start_idx and count < end_idx:
                repos.append(self._repo_to_dict(repo))
            
            count += 1
            
            # Stop if we've collected enough for this page
            if len(repos) >= per_page:
                break
        
        logger.info(f"Fetched {len(repos)} repositories (page {page}) for user {user.login}")
        return repos
    
    async def fetch_repo_by_url(
        self,
        repo_url: str,
        encrypted_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a single repository by URL.
        
        Args:
            repo_url: GitHub repository URL
            encrypted_token: Optional encrypted token for private repos
            
        Returns:
            Repository metadata dict
        """
        # Parse repo URL
        full_name = self._parse_repo_url(repo_url)
        
        if encrypted_token:
            gh = self._get_github_client(encrypted_token)
        else:
            gh = Github()  # Unauthenticated for public repos
        
        repo = gh.get_repo(full_name)
        return self._repo_to_dict(repo)
    
    async def fetch_repo_details(
        self,
        full_name: str,
        encrypted_token: str,
    ) -> Dict[str, Any]:
        """
        Fetch detailed repository information including README and tech stack.
        
        Args:
            full_name: Repository full name (owner/repo)
            encrypted_token: Encrypted GitHub access token
            
        Returns:
            Detailed repository data
        """
        logger.info("fetch_repo_details start", full_name=full_name)
        try:
            gh = self._get_github_client(encrypted_token)
            logger.info("fetch_repo_details: PyGithub client created", full_name=full_name)
            repo = gh.get_repo(full_name)
            logger.info(
                "fetch_repo_details: repo object retrieved",
                full_name=full_name,
                private=repo.private,
                fork=repo.fork,
                archived=repo.archived,
                default_branch=repo.default_branch,
                language=repo.language,
            )
        except Exception as e:
            logger.error(
                "fetch_repo_details: FAILED to get repo object",
                full_name=full_name,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise
        
        # Get basic info
        try:
            data = self._repo_to_dict(repo)
            logger.info("fetch_repo_details: _repo_to_dict OK", full_name=full_name)
        except Exception as e:
            logger.error("fetch_repo_details: _repo_to_dict FAILED", full_name=full_name, error=str(e))
            raise
        
        # Fetch README
        try:
            data["readme_content"] = await self._fetch_readme(repo)
            logger.info(
                "fetch_repo_details: README fetched",
                full_name=full_name,
                readme_len=len(data["readme_content"] or ""),
            )
        except Exception as e:
            logger.warning("fetch_repo_details: README fetch failed (non-fatal)", full_name=full_name, error=str(e))
            data["readme_content"] = None
        
        # Extract tech stack from dependency files
        try:
            data["extracted_tech"] = await self._extract_tech_stack(repo)
            logger.info("fetch_repo_details: tech stack extracted", full_name=full_name, tech=data["extracted_tech"])
        except Exception as e:
            logger.warning("fetch_repo_details: tech stack extraction failed (non-fatal)", full_name=full_name, error=str(e))
            data["extracted_tech"] = []
        
        # Fetch root dirs as fallback when no README
        data["root_dirs"] = []
        if not data["readme_content"]:
            try:
                data["root_dirs"] = await self._fetch_root_dirs(repo)
                logger.info("fetch_repo_details: root_dirs fetched (no README fallback)", full_name=full_name, dirs=data["root_dirs"])
            except Exception as e:
                logger.warning("fetch_repo_details: root_dirs fetch failed (non-fatal)", full_name=full_name, error=str(e))
        
        logger.info("fetch_repo_details done", full_name=full_name)
        return data
    
    def _repo_to_dict(self, repo: Repository) -> Dict[str, Any]:
        """Convert GitHub repository to dict."""
        return {
            "github_id": repo.id,
            "full_name": repo.full_name,
            "name": repo.name,
            "description": repo.description or "",
            "url": repo.html_url,
            "homepage": repo.homepage,
            "languages": dict(repo.get_languages()) if repo.get_languages() else {},
            "topics": repo.get_topics() if hasattr(repo, "get_topics") else [],
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "watchers": repo.watchers_count,
            "open_issues": repo.open_issues_count,
            "is_fork": repo.fork,
            "is_private": repo.private,
            "is_archived": repo.archived,
            "created_at": repo.created_at.isoformat() if repo.created_at else None,
            "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
            "default_branch": repo.default_branch,
        }
    
    async def _fetch_readme(self, repo: Repository) -> Optional[str]:
        """Fetch README content from repository."""
        readme_names = ["README.md", "readme.md", "README", "README.rst", "README.txt"]
        
        for name in readme_names:
            try:
                readme = repo.get_contents(name)
                if readme.encoding == "base64":
                    return base64.b64decode(readme.content).decode("utf-8")
                return readme.decoded_content.decode("utf-8")
            except GithubException:
                continue
        
        return None
    
    async def _fetch_root_dirs(self, repo: Repository) -> List[str]:
        """Fetch top-level folder names — cheap README fallback for structure signal."""
        try:
            contents = repo.get_contents("")
            return [f.name for f in contents if f.type == "dir"]  # folders only
        except GithubException:
            return []
    
    async def _extract_tech_stack(self, repo: Repository) -> List[str]:
        """Extract technology stack from dependency files."""
        technologies = set()
        
        # Check package.json (Node.js/JavaScript)
        try:
            package_json = repo.get_contents("package.json")
            content = base64.b64decode(package_json.content).decode("utf-8")
            technologies.update(self._parse_package_json(content))
        except GithubException:
            pass
        
        # Check requirements.txt (Python)
        try:
            requirements = repo.get_contents("requirements.txt")
            content = base64.b64decode(requirements.content).decode("utf-8")
            technologies.update(self._parse_requirements_txt(content))
        except GithubException:
            pass
        
        # Check pyproject.toml (Python)
        try:
            pyproject = repo.get_contents("pyproject.toml")
            content = base64.b64decode(pyproject.content).decode("utf-8")
            technologies.update(self._parse_pyproject_toml(content))
        except GithubException:
            pass
        
        # Check Cargo.toml (Rust)
        try:
            cargo = repo.get_contents("Cargo.toml")
            content = base64.b64decode(cargo.content).decode("utf-8")
            technologies.add("Rust")
        except GithubException:
            pass
        
        # Check go.mod (Go)
        try:
            go_mod = repo.get_contents("go.mod")
            technologies.add("Go")
        except GithubException:
            pass
        
        # Add languages from GitHub
        languages = repo.get_languages()
        for lang in languages.keys():
            technologies.add(lang)
        
        return list(technologies)
    
    def _parse_package_json(self, content: str) -> List[str]:
        """Parse package.json and extract technologies."""
        import json
        
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
    
    def _parse_requirements_txt(self, content: str) -> List[str]:
        """Parse requirements.txt and extract technologies."""
        technologies = ["Python"]
        
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Extract package name (before ==, >=, etc.)
            pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
            canonical = TECH_MAPPING.get(pkg_name.lower())
            if canonical:
                technologies.append(canonical)
        
        return list(set(technologies))
    
    def _parse_pyproject_toml(self, content: str) -> List[str]:
        """Parse pyproject.toml and extract technologies."""
        technologies = ["Python"]
        
        # Simple parsing - look for known package names
        content_lower = content.lower()
        for pkg_name, canonical in TECH_MAPPING.items():
            if pkg_name in content_lower:
                technologies.append(canonical)
        
        return list(set(technologies))
    
    def _parse_repo_url(self, url: str) -> str:
        """Parse GitHub URL to get full_name (owner/repo)."""
        url = url.rstrip("/")
        if "github.com" in url:
            parts = url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1].replace('.git', '')}"
        raise ValueError(f"Invalid GitHub URL: {url}")
    
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
            logger.error("create_project_from_repo: Bedrock summary FAILED", repo=name, error=str(e))
            raise
        md_content = self._render_summary_md(name, summary)
        return {
            "summary":        summary,
            "summaryMd":      md_content,
            "technologies":   summary.get("languages", []) + summary.get("frameworks", []) + summary.get("infrastructure", []),
            "highlights":     summary.get("highlights", []),
            "description":    repo_data.get("description") or summary.get("oneLiner", ""),
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
                logger.info("_generate_structured_summary: Bedrock OK", repo=name, keys=list(result.keys()))
                return result
            else:
                logger.warning("_generate_structured_summary: Bedrock returned non-dict", repo=name, type=type(result).__name__, value=str(result)[:200])
        except Exception as e:
            logger.error(f"_generate_structured_summary: Bedrock FAILED for {name}: {type(e).__name__}: {e}")
        
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
    
    def _render_summary_md(self, name: str, summary: Dict[str, Any]) -> str:
        """Render the structured dict into the academia-sync.md format."""
        lines = [
            f"# {name}",
            "",
            "## 1. High-Level Pitch",
            f"- **One-Liner:** {summary.get('oneLiner', '')}",
            f"- **Problem Type:** {summary.get('problemType', '')}",
            f"- **Domain/Context:** {summary.get('domain', '')}",
            "",
            "## 2. Technical Implementation (The \"How\")",
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
            logger.error("ingest_and_embed_repo: S3 upload FAILED", repo=name, s3_key=s3_key, error=str(e))
            raise

        # 2. Write structured item to DynamoDB
        summary = project_data["summary"]
        now = datetime.utcnow().isoformat()
        project_item = {
            "userId":         user_id,
            "projectId":      project_id,
            "name":           name,
            "description":    project_data["description"],
            "oneLiner":       summary.get("oneLiner", ""),
            "problemType":    summary.get("problemType", ""),
            "domain":         summary.get("domain", ""),
            "technologies":   project_data["technologies"],
            "languages":      repo_data.get("languages", {}),
            "frameworks":     summary.get("frameworks", []),
            "infrastructure": summary.get("infrastructure", []),
            "capabilities":   summary.get("capabilities", []),
            "highlights":     project_data["highlights"],
            "topics":         repo_data.get("topics", []),
            "repoUrl":        repo_data.get("url", ""),
            "stars":          repo_data.get("stars", 0),
            "isFork":         repo_data.get("is_fork", False),
            "isPrivate":      repo_data.get("is_private", False),
            "pushedAt":       repo_data.get("pushed_at"),
            "sourceType":     "github",
            "githubId":       repo_data.get("github_id"),
            "summaryS3Key":   s3_key,
            "createdAt":      now,
            "updatedAt":      now,
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
            logger.info("ingest_and_embed_repo: DynamoDB write OK", repo=name, project_id=project_id)
        except Exception as e:
            logger.error("ingest_and_embed_repo: DynamoDB write FAILED", repo=name, project_id=project_id, error=str(e))
            raise

        logger.info("Ingested repo to DynamoDB + S3", repo=name, project_id=project_id)
        return project_id


# Global instance
github_service = GitHubIngestionService()
