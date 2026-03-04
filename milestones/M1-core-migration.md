# M1 — Core AWS Migration

> **Dependencies:** M0 (AWS Setup complete, all services provisioned)
> **Unlocks:** M2 (Resume Generator), M3 (Skill Gap + LearnWeave), M4 (Job Scout) — all in parallel
> **Estimated effort:** 6–8 hours
> **Target:** March 4 evening – March 5

---

## Goal

Replace all GCP/local dependencies with AWS equivalents. After this milestone, the backend can talk to Bedrock (LLM + embeddings), read/write DynamoDB, and store files in S3. This is the **critical path** — everything else depends on it.

---

## Tasks

### 1.1 — Bedrock LLM Client (replaces `gemini_client.py`)

- [ ] Create `app/services/bedrock_client.py`
- [ ] Mirror the exact interface of `gemini_client.py`:
  ```python
  async def generate(prompt: str, system_prompt: str = None) -> str
  ```
- [ ] Implementation: `boto3.client('bedrock-runtime').invoke_model()` with Claude 3 Haiku
- [ ] Handle Bedrock message format (Messages API with `anthropic_version`)
- [ ] Add retry logic (3 attempts, exponential backoff) for throttling
- [ ] Add `BEDROCK_MODEL_ID` env var for easy model swapping
- [ ] Find-and-replace all imports:
  ```
  from app.services.gemini_client import gemini_client
  →
  from app.services.bedrock_client import bedrock_client
  ```
- [ ] Test: call `bedrock_client.generate("Summarise this project: ...")` → valid response

### 1.2 — Bedrock Embeddings (replaces Gemini `text-embedding-004`)

- [ ] Update `app/services/embedding_service.py`
- [ ] Replace Gemini embed call with Bedrock Titan v2:
  ```python
  async def embed(text: str) -> list[float]  # returns 1024-dim vector
  ```
- [ ] Model ID: `amazon.titan-embed-text-v2:0`
- [ ] Confirm ChromaDB can accept 1024-dim vectors (may need to recreate collection)
- [ ] If using OpenSearch Serverless instead, create index with knn vector field (1024 dims)
- [ ] Test: embed a project description → confirm 1024-length float list returned

### 1.3 — DynamoDB Data Layer (replaces SQLite + SQLAlchemy)

- [ ] Create `app/services/dynamo_service.py` — generic CRUD wrapper:
  ```python
  class DynamoService:
      async def put_item(table: str, item: dict)
      async def get_item(table: str, key: dict) -> dict | None
      async def query(table: str, pk_name: str, pk_value: str) -> list[dict]
      async def delete_item(table: str, key: dict)
      async def update_item(table: str, key: dict, updates: dict)
  ```
- [ ] Add `DYNAMO_TABLE_PREFIX` env var (e.g., `careerforge-`) for namespacing
- [ ] Migrate model-by-model:
  - [ ] `User` model → `Users` table (userId, username, email, avatar, githubToken, createdAt)
  - [ ] `Project` model → `Projects` table (userId, projectId, name, description, skills, embedding, repoUrl)
  - [ ] `Resume` model → `Resumes` table (userId, resumeId, texContent, pdfUrl, jobDescriptionId, createdAt)
- [ ] Replace all `async_session` / SQLAlchemy calls in routes with `dynamo_service` calls
- [ ] Keep SQLite as local fallback with `USE_DYNAMO=true` env flag
- [ ] Test: create user → fetch user → confirm data round-trips correctly

### 1.4 — S3 File Storage (replaces local filesystem)

- [ ] Create `app/services/s3_service.py`:
  ```python
  class S3Service:
      async def upload_file(key: str, data: bytes, content_type: str) -> str  # returns S3 URI
      async def get_presigned_url(key: str, expires_in: int = 3600) -> str
      async def delete_file(key: str)
  ```
- [ ] Update `latex_service.py`: after PDF compiled, upload to S3
- [ ] Key pattern: `{userId}/{resumeId}.pdf` and `{userId}/{resumeId}.tex`
- [ ] Return presigned URL (1 hr expiry) for frontend download
- [ ] Test: upload a dummy PDF → get presigned URL → download in browser → file matches

### 1.5 — GitHub OAuth + Auth Flow

- [ ] Verify existing GitHub OAuth still works (client ID/secret in new env)
- [ ] Keep custom JWT auth (already functional — no point migrating to Cognito for hackathon)
- [ ] Update user creation to write to DynamoDB instead of SQLite
- [ ] Store GitHub access token encrypted in DynamoDB `Users` table
- [ ] Test: full OAuth flow → token issued → user record in DynamoDB

### 1.6 — Repo Ingestion Pipeline

- [ ] Port `github_service.py` — keep GitHub API calls as-is
- [ ] Update summariser calls: Gemini → Bedrock client
- [ ] Update embedding calls: Gemini → Bedrock Titan
- [ ] Update storage: SQLite project records → DynamoDB `Projects` table
- [ ] Update vector storage: re-embed with Titan (1024 dims) into ChromaDB / OpenSearch
- [ ] Test: OAuth login → fetch repos → summarise 1 repo → skill profile stored in DynamoDB + vectors in store

---

## Verification Checklist

- [ ] `bedrock_client.generate()` returns coherent text
- [ ] `embedding_service.embed()` returns 1024-dim vector
- [ ] DynamoDB CRUD works for Users, Projects, Resumes tables
- [ ] S3 upload + presigned download works end-to-end
- [ ] GitHub OAuth → DynamoDB user creation works
- [ ] Repo fetch → LLM summarise → embed → store works for at least 1 repo
- [ ] No remaining imports of `gemini_client` or `google.cloud` in backend

---

## Notes

- This milestone is the **longest and most critical**. Everything downstream (M2–M5) depends on these clients working.
- Work sequentially: Bedrock client first (1.1) → Embeddings (1.2) → DynamoDB (1.3) → S3 (1.4) → Auth (1.5) → Pipeline (1.6).
- 1.1 and 1.2 are the riskiest — if Bedrock behaves differently from Gemini, debug here first.
- DynamoDB is schemaless — don't over-model. Store JSON documents as-is.
