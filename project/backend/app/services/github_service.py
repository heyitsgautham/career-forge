"""
GitHub Ingestion Service
========================
Fetches and processes GitHub repositories.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import base64
import structlog
from github import Github, GithubException
from github.Repository import Repository
import httpx

from app.core.security import token_encryptor
from app.services.gemini_client import gemini_client
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, VectorStoreService


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
    """
    
    def __init__(self):
        pass
    
    def _get_github_client(self, encrypted_token: str) -> Github:
        """Create GitHub client with decrypted token."""
        token = token_encryptor.decrypt(encrypted_token)
        return Github(token)
    
    async def fetch_user_repos_fast(
        self,
        encrypted_token: str,
        include_forks: bool = True,
        include_private: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL repositories using direct GitHub API (faster, async).
        Handles pagination automatically to get all repos.
        
        Args:
            encrypted_token: Encrypted GitHub access token
            include_forks: Include forked repositories
            include_private: Include private repositories
            
        Returns:
            List of all repository metadata dicts
        """
        token = token_encryptor.decrypt(encrypted_token)
        all_repos = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub API
        
        async with httpx.AsyncClient() as client:
            while True:
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
        gh = self._get_github_client(encrypted_token)
        repo = gh.get_repo(full_name)
        
        # Get basic info
        data = self._repo_to_dict(repo)
        
        # Fetch README
        data["readme_content"] = await self._fetch_readme(repo)
        
        # Extract tech stack from dependency files
        data["extracted_tech"] = await self._extract_tech_stack(repo)
        
        # Get commit count
        try:
            commits = repo.get_commits()
            data["commits_count"] = commits.totalCount
        except GithubException:
            data["commits_count"] = 0
        
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
        Uses Gemini to generate highlights if README exists.
        
        Args:
            repo_data: Repository data dict
            
        Returns:
            Project data ready for database insertion
        """
        # Build description
        description = repo_data.get("description") or ""
        if repo_data.get("readme_content"):
            # Use first 2000 chars of README for context
            readme_excerpt = repo_data["readme_content"][:2000]
            description = f"{description}\n\n{readme_excerpt}" if description else readme_excerpt
        
        # Extract technologies
        technologies = list(set(
            repo_data.get("extracted_tech", []) + 
            list(repo_data.get("languages", {}).keys()) +
            repo_data.get("topics", [])
        ))
        
        # Generate highlights using Gemini
        highlights = await self._generate_highlights(
            title=repo_data["name"],
            description=description,
            technologies=technologies,
            stars=repo_data.get("stars", 0),
            readme=repo_data.get("readme_content"),
        )
        
        return {
            "title": repo_data["name"],
            "description": repo_data.get("description") or f"GitHub project: {repo_data['name']}",
            "technologies": technologies,
            "highlights": highlights,
            "url": repo_data.get("url"),
            "raw_content": description,
            "source_type": "github",
            "source_id": str(repo_data["github_id"]),
        }
    
    async def _generate_highlights(
        self,
        title: str,
        description: str,
        technologies: List[str],
        stars: int,
        readme: Optional[str],
    ) -> List[str]:
        """
        Generate resume-friendly bullet points using Gemini.
        Strictly grounded to provided content.
        """
        if not description and not readme:
            return [f"Developed {title} using {', '.join(technologies[:5])}"]
        
        prompt = f"""Analyze this GitHub project and generate 2-4 resume bullet points.

PROJECT TITLE: {title}
TECHNOLOGIES: {', '.join(technologies)}
STARS: {stars}
DESCRIPTION: {description[:1000] if description else 'N/A'}

README EXCERPT:
{readme[:2000] if readme else 'N/A'}

RULES:
1. ONLY use information from the provided content above
2. DO NOT invent features, metrics, or achievements not mentioned
3. Use action verbs (Built, Developed, Implemented, Designed)
4. Focus on technical achievements and features
5. If information is limited, create fewer but accurate points
6. Format as a JSON array of strings

Return ONLY a JSON array like: ["Built X using Y", "Implemented Z feature"]"""

        try:
            result = await gemini_client.generate_json(
                prompt=prompt,
                system_instruction="You are a technical resume writer. Generate accurate, grounded bullet points. Never invent information.",
                temperature=0.2,
            )
            if isinstance(result, list):
                return result[:4]  # Max 4 highlights
        except Exception as e:
            logger.error(f"Failed to generate highlights: {e}")
        
        # Fallback
        return [f"Developed {title} using {', '.join(technologies[:3])}"]
    
    async def ingest_and_embed_repo(
        self,
        repo_data: Dict[str, Any],
        user_id: str,
    ) -> str:
        """
        Create embedding for repository and store in vector store.
        
        Args:
            repo_data: Repository data dict
            user_id: User ID for filtering
            
        Returns:
            Embedding ID
        """
        # Combine text for embedding
        text = embedding_service.combine_texts_for_embedding(
            title=repo_data.get("name", ""),
            description=repo_data.get("description", "") + "\n" + (repo_data.get("readme_content", "") or "")[:1500],
            technologies=repo_data.get("extracted_tech", []) + list(repo_data.get("languages", {}).keys()),
        )
        
        # Generate embedding
        embedding = await embedding_service.embed_text(text)
        
        # Store in vector store
        embedding_id = vector_store.generate_embedding_id()
        await vector_store.add_embedding(
            collection_name=VectorStoreService.COLLECTION_PROJECTS,
            embedding_id=embedding_id,
            embedding=embedding,
            metadata={
                "user_id": user_id,
                "source_type": "github",
                "github_id": repo_data.get("github_id"),
                "name": repo_data.get("name", ""),
                "technologies": repo_data.get("extracted_tech", []),
            },
            document=text,
        )
        
        return embedding_id


# Global instance
github_service = GitHubIngestionService()
