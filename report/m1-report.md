# M1 — Core Migration: Completion Report

**Status:** ✅ Complete  
**Date:** 5 March 2026  
**Milestone:** [M1-core-migration.md](../milestones/M1-core-migration.md)

---

## Summary

All GCP/local dependencies have been replaced with AWS equivalents. The backend now runs entirely on AWS services with a `USE_DYNAMO=true` flag for the DynamoDB path (SQLite fallback preserved). Every task in M1 has been implemented, tested, and verified.

---

## Services Implemented

| Component | Before | After | File(s) |
|---|---|---|---|
| **LLM** | Gemini Pro | Amazon Nova Lite via Bedrock Converse API | `app/services/bedrock_client.py` |
| **Embeddings** | Gemini `text-embedding-004` | Titan Embed Text v2 (1024-dim) | `app/services/embedding_service.py` |
| **Database** | SQLite + SQLAlchemy | DynamoDB (6 tables) | `app/services/dynamo_service.py` + all routes |
| **File Storage** | Local filesystem | S3 (`careerforge-pdfs-602664593597`) | `app/services/s3_service.py`, `app/services/latex_service.py` |
| **Auth** | SQLite user records | DynamoDB Users table | `app/api/routes/auth.py`, `app/api/deps.py` |

---

## Task Breakdown

### 1.1 — Bedrock LLM Client (replaces Gemini Pro)

- Created `app/services/bedrock_client.py` with `BedrockClient` class
- Uses **Converse API** (model-agnostic) instead of model-specific invoke_model
- Model ID: `amazon.nova-lite-v1:0`
- Methods: `generate()`, `generate_content()`, `generate_json()`, `generate_embedding()`, `generate_embeddings_batch()`
- Retry logic only on transient errors (throttling, service unavailable)
- All `gemini_client` imports replaced across 8+ files

### 1.2 — Bedrock Embeddings (replaces Gemini text-embedding-004)

- Updated `app/services/embedding_service.py` to use Titan Embed Text v2
- Model ID: `amazon.titan-embed-text-v2:0`
- Output: 1024-dimensional float vectors
- ChromaDB collection compatible with new dimensions

### 1.3 — DynamoDB Data Layer (replaces SQLite + SQLAlchemy)

- Created `app/services/dynamo_service.py` — generic CRUD wrapper with `put_item`, `get_item`, `query`, `delete_item`, `update_item`, `scan`
- Migrated all route files to conditional DynamoDB/SQLAlchemy paths
- `DynamoUser` wrapper class in `deps.py` for attribute-style access
- `get_db()` yields `None` when `USE_DYNAMO=True`
- SQLite fallback preserved via `USE_DYNAMO` env flag

### 1.4 — S3 File Storage (replaces local filesystem)

- Created `app/services/s3_service.py` with `upload_file`, `get_presigned_url`, `delete_file`
- Updated `latex_service.py` to upload compiled PDFs to S3
- Key pattern: `{userId}/{resumeId}.pdf` and `{userId}/{resumeId}.tex`
- Presigned URLs with 1-hour expiry for frontend download

### 1.5 — GitHub OAuth + Auth Flow

- Rewrote `app/api/routes/auth.py` with full DynamoDB support
- GitHub OAuth flow writes user records to DynamoDB Users table
- GitHub/LinkedIn access tokens stored as user attributes
- Custom JWT auth preserved (no Cognito migration needed for hackathon)

### 1.6 — Repo Ingestion Pipeline

- `github_service.py` GitHub API calls preserved as-is
- Summariser calls: Gemini → Bedrock client
- Embedding calls: Gemini → Bedrock Titan (1024 dims)
- Storage: SQLite → DynamoDB Projects table
- Vector storage: ChromaDB with Titan embeddings

---

## Routes Migrated

| Route File | DynamoDB Support | Key Changes |
|---|---|---|
| `app/api/routes/auth.py` | ✅ | GitHub OAuth + JWT, DynamoDB user creation |
| `app/api/routes/projects.py` | ✅ | Project CRUD + GitHub repo ingestion |
| `app/api/routes/resumes.py` | ✅ | Resume CRUD + generation with S3 storage |
| `app/api/routes/jobs.py` | ✅ | Job description CRUD + Bedrock analysis |
| `app/api/routes/templates.py` | ✅ | File-based template serving in DynamoDB mode |

---

## DynamoDB Tables

All tables are **ACTIVE** in `us-east-1`:

| Table | Partition Key | Sort Key | Notes |
|---|---|---|---|
| Users | `userId` (S) | — | User profiles, OAuth tokens |
| Projects | `userId` (S) | `projectId` (S) | GitHub repos, skills, embeddings |
| Resumes | `userId` (S) | `resumeId` (S) | LaTeX content, PDF URLs |
| Jobs | `jobId` (S) | — | Job descriptions, userId as attribute |
| Applications | `userId` (S) | `applicationId` (S) | Future: job applications |
| Roadmaps | `userId` (S) | `roadmapId` (S) | Future: learning roadmaps |

---

## Test Results

**5/5 tests passed** (`scripts/test_full_stack.py`):

| # | Test | Result |
|---|---|---|
| 1 | LLM text generation (Nova Lite via Converse API) | ✅ PASS |
| 2 | LLM JSON generation (structured output with cleanup) | ✅ PASS |
| 3 | Titan embeddings (1024-dimensional float vectors) | ✅ PASS |
| 4 | DynamoDB CRUD (put → get → query → delete) | ✅ PASS |
| 5 | S3 lifecycle (upload → presigned URL → delete) | ✅ PASS |

---

## Key Decisions

### Amazon Nova Lite over Claude

Claude 3 Haiku and Claude 3.5 Haiku require submitting the **Anthropic use case form** in the Bedrock console. This form has not been submitted. Amazon Nova Lite works immediately without any approval process.

**To switch to Claude later:** Submit the use case form in Bedrock console, then change `BEDROCK_MODEL_ID` in `app/core/config.py`.

### Converse API over Invoke Model

The Bedrock **Converse API** is model-agnostic — it works with any Bedrock model (Anthropic, Amazon, Meta, etc.) using the same request/response format. This makes future model switches trivial: just change the model ID string.

### SQLAlchemy Version Bump

SQLAlchemy 2.0.23 was incompatible with Python 3.13 (`__static_attributes__` assertion error). Upgraded to `>=2.0.36` (installed 2.0.48).

### DynamoUser Wrapper

Created a `DynamoUser` wrapper class in `deps.py` that provides attribute-style access (`.id`, `.username`, `.email`) over DynamoDB dict records. This maintains compatibility with existing route code that expected SQLAlchemy model instances.

---

## Infrastructure

- **AWS Account:** 602664593597
- **Region:** us-east-1
- **Bedrock Model:** `amazon.nova-lite-v1:0` (Converse API)
- **Embedding Model:** `amazon.titan-embed-text-v2:0` (1024-dim)
- **S3 Bucket:** `careerforge-pdfs-602664593597`
- **Python:** 3.13.8 (venv at `project/backend/venv`)

---

## Files Changed

### New Files
- `app/services/bedrock_client.py` — Bedrock LLM client (Converse API)
- `app/services/dynamo_service.py` — DynamoDB CRUD wrapper
- `app/services/s3_service.py` — S3 file operations
- `scripts/test_full_stack.py` — End-to-end AWS test suite
- `scripts/test_aws_services.py` — Basic AWS connectivity tests

### Modified Files
- `app/services/embedding_service.py` — Gemini → Titan embeddings
- `app/services/latex_service.py` — Local filesystem → S3 upload
- `app/core/config.py` — Added AWS settings, model IDs
- `app/core/database.py` — Conditional `get_db()` (None when USE_DYNAMO)
- `app/api/deps.py` — DynamoUser wrapper, dual-backend `get_current_user`
- `app/api/routes/auth.py` — Full DynamoDB auth flow
- `app/api/routes/projects.py` — DynamoDB project CRUD + ingestion
- `app/api/routes/resumes.py` — DynamoDB resume CRUD + S3 storage
- `app/api/routes/jobs.py` — DynamoDB job CRUD + Bedrock analysis
- `app/api/routes/templates.py` — File-based template serving
- `app/services/__init__.py` — Updated imports
- `app/main.py` — Updated lifespan for AWS services
- `requirements.txt` — Added boto3, bumped sqlalchemy

### Imports Replaced
All `gemini_client` and `google.cloud` / `google.generativeai` imports replaced with `bedrock_client`. The old `gemini_client.py` file still exists but has **zero active imports** — safe to delete.

---

## Remaining Notes

- **Anthropic Use Case Form:** Submit via AWS Bedrock console if you want to use Claude models in the future.
- **`gemini_client.py`:** Can be deleted at any time — nothing imports from it.
- **Applications & Roadmaps tables:** Created and active but not yet used (M4/M5 milestones).
- **Local development:** Set `USE_DYNAMO=false` to fall back to SQLite for offline work.
