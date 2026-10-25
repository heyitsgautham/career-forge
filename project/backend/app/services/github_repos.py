"""
GitHub repo client
==================
Reads repositories from GitHub: the user's repo list through the REST API
(with a GitHub App installation token when there is one), and README, folder
and dependency details through PyGithub.
"""

import base64
import time
from typing import Any, Dict, List, Optional

import httpx
import jwt as pyjwt
import structlog
from github import Github, GithubException
from github.Repository import Repository

from app.core.config import settings
from app.core.security import token_encryptor
from app.services.github_tech import (
    parse_package_json,
    parse_pyproject_toml,
    parse_repo_url,
    parse_requirements_txt,
)

logger = structlog.get_logger()


class GitHubRepoClient:
    """Fetches repository metadata, README content and tech stack from GitHub."""

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
                logger.error(
                    "Failed to load GitHub App private key from Secrets Manager", error=str(e)
                )
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

                    all_repos.append(
                        {
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
                        }
                    )

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
        full_name = parse_repo_url(repo_url)

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
            logger.error(
                "fetch_repo_details: _repo_to_dict FAILED", full_name=full_name, error=str(e)
            )
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
            logger.warning(
                "fetch_repo_details: README fetch failed (non-fatal)",
                full_name=full_name,
                error=str(e),
            )
            data["readme_content"] = None

        # Extract tech stack from dependency files
        try:
            data["extracted_tech"] = await self._extract_tech_stack(repo)
            logger.info(
                "fetch_repo_details: tech stack extracted",
                full_name=full_name,
                tech=data["extracted_tech"],
            )
        except Exception as e:
            logger.warning(
                "fetch_repo_details: tech stack extraction failed (non-fatal)",
                full_name=full_name,
                error=str(e),
            )
            data["extracted_tech"] = []

        # Fetch root dirs as fallback when no README
        data["root_dirs"] = []
        if not data["readme_content"]:
            try:
                data["root_dirs"] = await self._fetch_root_dirs(repo)
                logger.info(
                    "fetch_repo_details: root_dirs fetched (no README fallback)",
                    full_name=full_name,
                    dirs=data["root_dirs"],
                )
            except Exception as e:
                logger.warning(
                    "fetch_repo_details: root_dirs fetch failed (non-fatal)",
                    full_name=full_name,
                    error=str(e),
                )

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
            technologies.update(parse_package_json(content))
        except GithubException:
            pass

        # Check requirements.txt (Python)
        try:
            requirements = repo.get_contents("requirements.txt")
            content = base64.b64decode(requirements.content).decode("utf-8")
            technologies.update(parse_requirements_txt(content))
        except GithubException:
            pass

        # Check pyproject.toml (Python)
        try:
            pyproject = repo.get_contents("pyproject.toml")
            content = base64.b64decode(pyproject.content).decode("utf-8")
            technologies.update(parse_pyproject_toml(content))
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
            repo.get_contents("go.mod")
            technologies.add("Go")
        except GithubException:
            pass

        # Add languages from GitHub
        languages = repo.get_languages()
        for lang in languages.keys():
            technologies.add(lang)

        return list(technologies)
