# Career-Forge Codebase Audit Report

> **Scope:** `ref-repos/latex-agent/` and `ref-repos/job-scrapper/`
> **Date:** Auto-generated
> **Purpose:** Map all GCP/Google dependencies, data models, and environment variables for AWS migration planning

---

## Table of Contents

1. [Category 1: Gemini Client Imports (latex-agent)](#1-gemini-client-imports-latex-agent)
2. [Category 2: Gemini Embedding Calls (latex-agent)](#2-gemini-embedding-calls-latex-agent)
3. [Category 3: Firestore / GCP Calls (job-scrapper)](#3-firestore--gcp-calls-job-scrapper)
4. [Category 4: SQLAlchemy Models (latex-agent)](#4-sqlalchemy-models-latex-agent)
5. [Category 5: Environment Variables (Both Projects)](#5-environment-variables)
6. [AWS Migration Summary](#aws-migration-summary)

---

## 1. Gemini Client Imports (latex-agent)

### Primary Client — `app/services/gemini_client.py` (311 lines)

| Line | Code | Purpose |
|------|------|---------|
| L13 | `import google.generativeai as genai` | Core Gemini SDK |
| L14 | `from google.generativeai.types import HarmCategory, HarmBlockThreshold` | Safety settings |
| L33 | `class GeminiClient` | Client with API-key rotation (up to 6 keys) |
| L63 | reads `settings.gemini_api_keys` | Key pool from config |
| L107 | `genai.configure(api_key=...)` | SDK configuration |
| L150 | `genai.GenerativeModel(model_name=settings.GEMINI_MODEL, ...)` | Model instantiation |
| L228 | `genai.embed_content(model=settings.GEMINI_EMBEDDING_MODEL, ...)` | Embedding call |
| L266 | `generate_embeddings_batch(texts, batch_size)` | Batch embedding |
| L311 | `gemini_client = GeminiClient()` | Singleton instance |

### Files Importing `gemini_client`

| File | Line(s) | Import | Usage |
|------|---------|--------|-------|
| `app/services/document_parser.py` | L12 | `from app.services.gemini_client import gemini_client` | L131, L173, L207 → `generate_json()` for doc classification/parsing |
| `app/services/embedding_service.py` | L10 | `from app.services.gemini_client import gemini_client` | L41 → `generate_embedding()`, L54 → `generate_embeddings_batch()` |
| `app/services/resume_agent.py` | L11 | `from app.services.gemini_client import gemini_client` | L125 → `generate_content()` for LaTeX resume gen; L710 → `generate_json()` |
| `app/services/matching_engine.py` | L13 | `from app.services.gemini_client import gemini_client` | L85 → `generate_json()` for job-resume matching |
| `app/services/github_service.py` | L16 | `from app.services.gemini_client import gemini_client` | L560 → `generate_json()` for bullet points; L589-603 → embedding via `embedding_service` |
| `app/services/__init__.py` | L3-4 | `from app.services.gemini_client import GeminiClient, gemini_client` | Module re-export |
| `app/api/routes/auth.py` | L28 | `from app.services.gemini_client import gemini_client` | L430 → `initialize()`, L434 → `generate_json()` for resume parsing |
| `app/api/routes/resumes.py` | L35 | `from app.services.gemini_client import gemini_client` | Conditional import |
| `app/api/routes/projects.py` | L131 | `from app.services.gemini_client import gemini_client` | L145 → `generate_content()` for description gen |
| `app/api/routes/health.py` | L41 | `from app.services.gemini_client import gemini_client` | L51-52 → Gemini health check |

### Distinct Gemini Operations Used

| Method | Callsites | AWS Equivalent |
|--------|-----------|----------------|
| `generate_content(prompt)` | resume_agent, projects route | Bedrock `InvokeModel` |
| `generate_json(prompt, response_schema)` | document_parser, matching_engine, github_service, auth route, resume_agent | Bedrock `InvokeModel` with JSON mode |
| `generate_embedding(text)` | embedding_service | Bedrock Titan Embeddings / Cohere Embed |
| `generate_embeddings_batch(texts)` | embedding_service | Bedrock batch embedding |

---

## 2. Gemini Embedding Calls (latex-agent)

### Embedding Pipeline

```
gemini_client.py → embedding_service.py → vector_store.py (ChromaDB)
                                         → github_service.py (adds repo embeddings)
```

### `app/services/embedding_service.py`

| Line | Detail |
|------|--------|
| L10 | `from app.services.gemini_client import gemini_client` |
| L16 | `class EmbeddingService` |
| L23 | `self.dimension = 768` — hardcoded for `text-embedding-004` |
| L41 | `embed_text(text)` → delegates to `gemini_client.generate_embedding(text)` |
| L54 | `embed_texts_batch(texts, batch_size)` → delegates to `gemini_client.generate_embeddings_batch()` |
| L56 | `combine_texts_for_embedding()` — helper to concatenate fields |
| L89 | `embedding_service = EmbeddingService()` — singleton |

### `app/services/vector_store.py` (ChromaDB)

| Line | Method | Detail |
|------|--------|--------|
| L66 | `add_embedding(id, embedding, metadata)` | Inserts into ChromaDB collection |
| L102 | `update_embedding(id, embedding, metadata)` | Updates existing vector |
| L121 | `delete_embedding(id)` | Removes vector |
| L127 | `search_similar(query_embedding, n_results, filter)` | Cosine similarity search |
| L207 | `generate_embedding_id(type, user_id, item_id)` | Deterministic ID generation |

**Config:** `CHROMA_HOST=localhost`, `CHROMA_PORT=8001`, `CHROMA_PERSIST_DIRECTORY=./chroma_data`

### `app/services/github_service.py` — Embedding Integration

| Line | Detail |
|------|--------|
| L17 | `from app.services.embedding_service import embedding_service` |
| L579-603 | Creates embeddings for GitHub repos via `embedding_service.embed_text()` → stores in `vector_store.add_embedding()` |

### Migration Impact

| Component | Current | AWS Target |
|-----------|---------|------------|
| Embedding model | `text-embedding-004` (768-dim) | Amazon Titan Embeddings v2 (1024-dim) or Cohere Embed v3 (1024-dim) |
| Vector store | ChromaDB (local/persistent) | Amazon OpenSearch Serverless (vector engine) or pgvector on Aurora |
| Embedding dimension | `768` hardcoded | Will need to change to match new model |

---

## 3. Firestore / GCP Calls (job-scrapper)

### `backend/firestore_db.py` — Central Database Module (379 lines)

| Line | Detail |
|------|--------|
| L13 | `from google.cloud import firestore` |
| L20 | `_db: Optional[firestore.Client] = None` — lazy singleton |
| L23 | `get_firestore_client()` — reads `FIRESTORE_PROJECT_ID` or `GCP_PROJECT_ID` from env |

**Firestore Collections:**

| Collection | Functions | Purpose |
|------------|-----------|---------|
| `jobs` | `store_job()`, `get_recent_jobs()`, `delete_job()`, `delete_jobs_batch()` | Job listing storage |
| `scrape_logs` | `log_scraping_activity()` | Scraper run history |
| `blacklisted_companies` | `get_blacklisted_companies()`, `add_blacklisted_company()`, `remove_blacklisted_company()` | Company filters |
| `email_settings` | `get_email_settings()`, `save_email_settings()` | Email config stored in Firestore |
| `status_checks` | (referenced in get_stats) | Health check data |
| `users` | `create_user()`, `get_user_by_username()`, `verify_user_password()`, `update_user_password()` | Admin auth |

### Files Consuming Firestore Functions

| File | Line | Imports | Firestore Operations |
|------|------|---------|---------------------|
| `server.py` | L20 | `from firestore_db import (store_job, get_recent_jobs, get_stats, log_scraping_activity, get_blacklisted_companies, add_blacklisted_company, remove_blacklisted_company, get_email_settings, save_email_settings, delete_job, delete_jobs_batch, create_user, get_user_by_username, verify_user_password, update_user_password, init_database)` | Full CRUD — ~15 functions |
| `scraper.py` | L11 | `from firestore_db import (store_job, get_blacklisted_companies, ...)` | L370 → store jobs, L504 → update salaries |
| `email_notifier.py` | L10 | `from firestore_db import get_email_settings, save_email_settings` | Read/write email config |
| `scheduler.py` | L7-8 | Imports scraper + email_notifier (indirect Firestore via those modules) | Orchestrates scrape + email cycle |

### `backend/ai_analyzer.py` — Vertex AI Gemini (296 lines)

| Line | Detail |
|------|--------|
| L4 | `from google import genai` — **Different SDK** than latex-agent (`google-genai` vs `google-generativeai`) |
| L5 | `from google.genai import types` |
| L26 | `class GeminiJobAnalyzer` — uses **Vertex AI** (not API key) |
| L31 | `os.getenv('GCP_PROJECT_ID')` |
| L32 | `os.getenv('GCP_LOCATION', 'us-central1')` |
| L41-43 | Sets `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=True` |
| L46 | `self.client = genai.Client()` — Vertex AI client |
| L50 | Model: `gemini-3-flash-preview` (fallback: `gemini-2.5-flash`) |

### GCP Authentication

| File | Line | Mechanism |
|------|------|-----------|
| `Dockerfile` | L28 | `ENV GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/j-scrapper-8277935f574b.json` |
| `Dockerfile` | L31 | `ENV FIRESTORE_PROJECT_ID=j-scrapper` |
| `.env.example` | - | `GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json` |

### Migration Impact

| Component | Current | AWS Target |
|-----------|---------|------------|
| Firestore | `google.cloud.firestore` (6 collections) | DynamoDB (6 tables) |
| Vertex AI Gemini | `google.genai` + Vertex AI | Bedrock (Claude / Nova) |
| GCP Service Account | `GOOGLE_APPLICATION_CREDENTIALS` JSON | IAM Roles (no key files) |
| GCP Project config | `GCP_PROJECT_ID`, `GCP_LOCATION` | `AWS_REGION`, `AWS_ACCOUNT_ID` |

---

## 4. SQLAlchemy Models (latex-agent)

### Database Core — `app/core/database.py`

| Line | Detail |
|------|--------|
| L7 | `from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker` |
| L8 | `from sqlalchemy.orm import DeclarativeBase` |
| L26 | `class Base(DeclarativeBase)` — base class for all models |
| L32 | `get_async_database_url()` — converts `sqlite://` → `sqlite+aiosqlite://` or `postgresql://` → `postgresql+asyncpg://` |
| L44 | `engine = create_async_engine(get_async_database_url(), ...)` |
| L50 | `AsyncSessionLocal = async_sessionmaker(...)` |
| L59 | `init_db()` — creates all tables |
| L67 | `get_db()` — FastAPI dependency yielding `AsyncSession` |

### Portable Types — `app/core/db_types.py`

- `PortableUUID` — PostgreSQL native UUID vs CHAR(32) for SQLite
- `PortableJSON` — PostgreSQL JSONB vs Text with JSON encoding for SQLite

### Model Registry — `app/models/__init__.py`

```python
from app.models.user import User, GithubConnection
from app.models.project import Project, GithubRepo
from app.models.document import Document
from app.models.template import Template
from app.models.resume import Resume
from app.models.job_description import JobDescription
```

### Model Details

#### `User` — `app/models/user.py:L18` → table `users`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `email` | String(255) | unique, indexed |
| `name` | String(255) | required |
| `avatar_url` | String(500) | nullable |
| `hashed_password` | String(255) | nullable |
| `headline` | String(255) | nullable |
| `summary` | Text | nullable |
| `location` | String(255) | nullable |
| `phone` | String(50) | nullable |
| `website` | String(500) | nullable |
| `linkedin_url` | String(500) | nullable |
| `address_line1/2` | String(255) | nullable |
| `city` | String(100) | nullable |
| `state` | String(100) | nullable |
| `zip_code` | String(20) | nullable |
| `country` | String(100) | nullable |
| `institution` | String(255) | nullable |
| `degree` | String(255) | nullable |
| `field_of_study` | String(255) | nullable |
| `graduation_year` | String(10) | nullable |
| `experience` | JSON (list) | nullable |
| `education` | JSON (list) | nullable |
| `skills` | JSON (list) | nullable |
| `certifications` | JSON (list) | nullable |
| `is_active` | Boolean | default True |
| `is_verified` | Boolean | default False |
| `created_at` | DateTime | auto |
| `updated_at` | DateTime | auto |

**Relationships:** `github_connections` (1:M), `linkedin_connections` (1:M), `projects` (1:M), `documents` (1:M), `templates` (1:M), `resumes` (1:M), `job_descriptions` (1:M)

#### `LinkedInConnection` — `app/models/user.py:L120` → table `linkedin_connections`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users |
| `linkedin_user_id` | String(255) unique |
| `linkedin_email` | String(255) nullable |
| `encrypted_token` | Text |
| `scopes` | JSON nullable |
| `connected_at` | DateTime |
| `token_updated_at` | DateTime |

#### `GithubConnection` — `app/models/user.py:L154` → table `github_connections`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users |
| `github_user_id` | Integer unique |
| `github_username` | String(255) |
| `github_avatar_url` | String(500) nullable |
| `encrypted_token` | Text |
| `is_primary` | Boolean |
| `scopes` | JSON nullable |
| `connected_at` | DateTime |
| `token_updated_at` | DateTime |

**Relationships:** `user` (M:1→User), `repos` (1:M→GithubRepo)

#### `Project` — `app/models/project.py:L26` → table `projects`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users |
| `source_type` | Enum(ProjectSourceType) — GITHUB/MANUAL/LINKEDIN |
| `source_id` | String(255) nullable |
| `title` | String(255) |
| `description` | Text |
| `technologies` | JSON (list) |
| `highlights` | JSON (list) |
| `start_date` | Date nullable |
| `end_date` | Date nullable |
| `is_current` | Boolean |
| `url` | String(500) nullable |
| `demo_url` | String(500) nullable |
| `is_verified` | Boolean |
| `is_public` | Boolean |
| `is_featured` | Boolean |
| `raw_content` | Text nullable |
| `embedding_id` | String(255) nullable |
| `created_at` | DateTime |
| `updated_at` | DateTime |

**Relationships:** `user` (M:1→User), `github_repo` (1:1→GithubRepo)

#### `GithubRepo` — `app/models/project.py:L100` → table `github_repos`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `github_connection_id` | UUID FK→github_connections |
| `project_id` | UUID FK→projects nullable |
| `github_id` | Integer unique |
| `full_name` | String(255) — owner/repo |
| `name` | String(255) |
| `description` | Text nullable |
| `readme_content` | Text nullable |
| `languages` | JSON (dict) |
| `topics` | JSON (list) |
| `stars` | Integer |
| `forks` | Integer |
| `watchers` | Integer |
| `open_issues` | Integer |
| `commits_count` | Integer |
| `created_at_github` | DateTime nullable |
| `pushed_at` | DateTime nullable |
| `last_commit_at` | DateTime nullable |
| `is_fork` | Boolean |
| `is_private` | Boolean |
| `is_archived` | Boolean |
| `extracted_tech` | JSON (list) |
| `ingested_at` | DateTime |
| `last_synced_at` | DateTime |

**Relationships:** `github_connection` (M:1→GithubConnection), `project` (1:1→Project)

#### `Document` — `app/models/document.py:L37` → table `documents`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users |
| `filename` | String(255) |
| `file_type` | Enum |
| `file_path` | String(500) |
| `file_size` | Integer |
| `file_hash` | String(64) |
| `extracted_text` | Text nullable |
| `doc_type` | Enum |
| `doc_metadata` | JSON nullable |
| `embedding_id` | String(255) nullable |
| `is_processed` | Boolean |
| `processing_error` | Text nullable |
| `uploaded_at` | DateTime |
| `processed_at` | DateTime nullable |

#### `Template` — `app/models/template.py:L18` → table `templates`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users nullable |
| `name` | String(255) |
| `description` | Text nullable |
| `latex_content` | Text |
| `placeholders` | JSON nullable |
| `preview_image_path` | String(500) nullable |
| `is_system` | Boolean |
| `is_ats_tested` | Boolean |
| `is_public` | Boolean |
| `category` | String(50) nullable |
| `use_count` | Integer |
| `created_at` | DateTime |
| `updated_at` | DateTime |

#### `Resume` — `app/models/resume.py:L29` → table `resumes`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users |
| `template_id` | UUID FK→templates |
| `job_description_id` | UUID FK→job_descriptions nullable |
| `name` | String(255) |
| `version` | Integer |
| `latex_content` | Text nullable |
| `pdf_path` | String(500) nullable |
| `selected_project_ids` | JSON (list) |
| `generation_params` | JSON nullable |
| `status` | Enum |
| `error_message` | Text nullable |
| `compilation_log` | Text nullable |
| `compilation_warnings` | JSON nullable |
| `locale` | String(10) |
| `created_at` | DateTime |
| `updated_at` | DateTime |
| `generated_at` | DateTime nullable |
| `compiled_at` | DateTime nullable |

#### `JobDescription` — `app/models/job_description.py:L18` → table `job_descriptions`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `user_id` | UUID FK→users |
| `title` | String(255) |
| `company` | String(255) nullable |
| `location` | String(255) nullable |
| `raw_text` | Text |
| `source_url` | String(500) nullable |
| `parsed_requirements` | JSON nullable |
| `required_skills` | JSON (list) |
| `preferred_skills` | JSON (list) |
| `keywords` | JSON (list) |
| `embedding_id` | String(255) nullable |
| `is_analyzed` | Boolean |
| `created_at` | DateTime |
| `analyzed_at` | DateTime nullable |

### Routes Using `get_db()` (AsyncSession injection)

| Route File | Lines with `Depends(get_db)` |
|------------|------------------------------|
| `app/api/routes/resumes.py` | L104, L136, L197, L231, L431, L540, L569, L596 |
| `app/api/routes/projects.py` | L89, L124, L228, L263, L328, L359, L511, L552 |
| `app/api/routes/templates.py` | L75, L123, L157, L193, L234, L259 |
| `app/api/routes/jobs.py` | L69, L100, L133, L165, L285 |
| `app/api/routes/health.py` | L29 |

---

## 5. Environment Variables

### latex-agent — `app/core/config.py` (pydantic `BaseSettings`)

| Variable | Default | Category |
|----------|---------|----------|
| `APP_NAME` | `"latex-resume-agent"` | App |
| `APP_ENV` | `"development"` | App |
| `DEBUG` | `True` | App |
| `SECRET_KEY` | `"change-me-in-production"` | Security |
| `API_HOST` | `"0.0.0.0"` | Server |
| `API_PORT` | `8000` | Server |
| `DATABASE_URL` | `"sqlite+aiosqlite:///./latex_agent.db"` | Database |
| `REDIS_URL` | `"redis://localhost:6379/0"` | Cache/Queue |
| `CHROMA_HOST` | `"localhost"` | Vector Store |
| `CHROMA_PORT` | `8001` | Vector Store |
| `CHROMA_PERSIST_DIRECTORY` | `"./chroma_data"` | Vector Store |
| `GEMINI_API_KEY_1` | `None` | AI (required) |
| `GEMINI_API_KEY_2` | `None` | AI |
| `GEMINI_API_KEY_3` | `None` | AI |
| `GEMINI_API_KEY_4` | `None` | AI |
| `GEMINI_API_KEY_5` | `None` | AI |
| `GEMINI_API_KEY_6` | `None` | AI |
| `GEMINI_MODEL` | `"gemini-2.0-flash-lite"` | AI |
| `GEMINI_EMBEDDING_MODEL` | `"text-embedding-004"` | AI |
| `GEMINI_TEMPERATURE` | `0.2` | AI |
| `GEMINI_MAX_TOKENS` | `8192` | AI |
| `GITHUB_CLIENT_ID` | `None` | OAuth |
| `GITHUB_CLIENT_SECRET` | `None` | OAuth |
| `GITHUB_CALLBACK_URL` | `"http://localhost:3000/auth/github/callback"` | OAuth |
| `LINKEDIN_CLIENT_ID` | `None` | OAuth |
| `LINKEDIN_CLIENT_SECRET` | `None` | OAuth |
| `LINKEDIN_CALLBACK_URL` | `"http://localhost:3000/auth/linkedin/callback"` | OAuth |
| `JWT_SECRET_KEY` | `"change-me-in-production"` | Auth |
| `JWT_ALGORITHM` | `"HS256"` | Auth |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Auth |
| `UPLOAD_DIR` | `"./uploads"` | Storage |
| `MAX_UPLOAD_SIZE_MB` | `10` | Storage |
| `LATEX_COMPILER_TIMEOUT` | `30` | LaTeX |
| `LATEX_COMPILER_MEMORY_LIMIT` | `"256m"` | LaTeX |

### job-scrapper — `backend/.env.example` + inline `os.environ.get()` calls

| Variable | Source File(s) | Default | Category |
|----------|---------------|---------|----------|
| `GCP_PROJECT_ID` | `.env.example`, `firestore_db.py:L27`, `ai_analyzer.py:L31` | — | GCP |
| `GCP_LOCATION` | `.env.example`, `ai_analyzer.py:L32` | `us-central1` | GCP |
| `GOOGLE_APPLICATION_CREDENTIALS` | `.env.example`, `Dockerfile:L28` | — | GCP Auth |
| `FIRESTORE_PROJECT_ID` | `Dockerfile:L31`, `firestore_db.py:L27` | — | GCP |
| `GOOGLE_CLOUD_PROJECT` | `ai_analyzer.py:L41` (set at runtime) | — | GCP |
| `GOOGLE_CLOUD_LOCATION` | `ai_analyzer.py:L42` (set at runtime) | — | GCP |
| `GOOGLE_GENAI_USE_VERTEXAI` | `ai_analyzer.py:L43` (set at runtime) | `True` | GCP |
| `CORS_ORIGINS` | `.env.example`, `server.py:L654` | `*` | Server |
| `ADMIN_USERNAME` | `server.py:L41` | `admin` | Auth |
| `ADMIN_PASSWORD_HASH` | `server.py:L42` | `""` | Auth |
| `JWT_SECRET` | `server.py:L43` | `change-this-secret-key` | Auth |
| `SMTP_HOST` | `.env.example`, `server.py:L47`, `scheduler.py:L47` | `smtp.gmail.com` | Email |
| `SMTP_PORT` | `.env.example`, `server.py:L48`, `scheduler.py:L48` | `587` | Email |
| `SMTP_USER` | `.env.example`, `server.py:L49`, `scheduler.py:L49` | `""` | Email |
| `SMTP_PASSWORD` | `.env.example`, `server.py:L50`, `scheduler.py:L50` | `""` | Email |
| `SMTP_FROM_EMAIL` | `.env.example` | — | Email |
| `SMTP_FROM_NAME` | `.env.example` | — | Email |
| `DEFAULT_RECIPIENT_EMAILS` | `server.py:L516,L669` | `""` | Email |
| `NODE_ENV` | `.env.example` | — | App |
| `SCHEDULER_INTERVAL_HOURS` | `.env.example` | — | Scheduler |
| `MAX_JOBS_PER_EMAIL` | `.env.example` | — | Scheduler |
| `MONGO_URL` | `.env.example` | — | Legacy (unused) |
| `DB_NAME` | `.env.example` | — | Legacy (unused) |

---

## AWS Migration Summary

### High-Impact Changes (Architectural)

| # | Current (GCP) | AWS Target | Affected Files | Effort |
|---|---------------|------------|----------------|--------|
| 1 | **Google Gemini API** (`google.generativeai`) | **Amazon Bedrock** (Claude Sonnet / Nova) | `gemini_client.py`, all 10 consumers | High — rewrite client, change prompt formats |
| 2 | **Vertex AI Gemini** (`google.genai` + Vertex) | **Amazon Bedrock** | `ai_analyzer.py` | Medium — different SDK + auth model |
| 3 | **Gemini Embeddings** (`text-embedding-004`, 768-dim) | **Titan Embeddings v2** (1024-dim) or **Cohere Embed v3** | `gemini_client.py`, `embedding_service.py` | Medium — dimension change ripples to ChromaDB |
| 4 | **ChromaDB** (local vector store) | **OpenSearch Serverless** (vector engine) or **pgvector on Aurora** | `vector_store.py`, `github_service.py` | Medium — rewrite vector store adapter |
| 5 | **Google Cloud Firestore** (6 collections) | **Amazon DynamoDB** (6 tables) | `firestore_db.py` (379 lines), `server.py`, `scraper.py`, `email_notifier.py` | High — rewrite all DB operations, design partition keys |
| 6 | **GCP Service Account** (JSON key file) | **IAM Roles** (no key files) | `Dockerfile`, `.env.example`, `ai_analyzer.py` | Low — remove credential files, use IAM |
| 7 | **SQLite/PostgreSQL** (SQLAlchemy async) | **Aurora PostgreSQL** (SQLAlchemy async — no change) | `database.py`, `config.py` | **Low — just change connection string** |

### No-Change Components

| Component | Current | Notes |
|-----------|---------|-------|
| SQLAlchemy ORM | async + alembic | Works with Aurora PostgreSQL as-is |
| Redis | `redis://` | Swap to ElastiCache Redis — connection string only |
| JWT Auth | `python-jose` + bcrypt | No cloud dependency |
| SMTP Email | Generic SMTP | Can keep or switch to SES |
| LaTeX Compiler | Local Docker | Move to Lambda container or ECS task |
| GitHub/LinkedIn OAuth | Standard OAuth2 | No cloud dependency |

### Migration Priority Order

1. **Phase 1 — Database:** Firestore → DynamoDB (blocks everything else)
2. **Phase 2 — AI Client:** Gemini → Bedrock (biggest code change, well-isolated behind `gemini_client.py`)
3. **Phase 3 — Embeddings + Vector Store:** Gemini Embeddings + ChromaDB → Titan/Cohere + OpenSearch/pgvector
4. **Phase 4 — Auth & Infra:** GCP credentials → IAM roles, SQLite → Aurora, Redis → ElastiCache
5. **Phase 5 — Email:** SMTP → Amazon SES (optional, SMTP still works)

### Key Observations

- **latex-agent has excellent abstraction**: All Gemini calls go through a single `GeminiClient` class — swapping to Bedrock only requires rewriting one file + keeping the same interface
- **job-scrapper Firestore is tightly coupled**: `firestore_db.py` is a clean abstraction layer, but uses Firestore-specific query patterns (collection refs, document snapshots) that need complete rewrite for DynamoDB
- **Two different Gemini SDKs**: latex-agent uses `google-generativeai` (API key auth), job-scrapper uses `google-genai` (Vertex AI / service account auth) — both need Bedrock migration but with different approaches
- **Embedding dimension change**: Moving from 768 → 1024 dims means **all existing embeddings must be regenerated** — plan for a migration script
- **Environment variables are well-organized**: latex-agent uses pydantic `BaseSettings` (easy to swap), job-scrapper uses raw `os.environ.get()` (should be unified during migration)
