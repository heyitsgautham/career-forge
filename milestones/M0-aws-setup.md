# M0 — AWS Setup & Codebase Audit

> **Dependencies:** None (this is the root milestone)
> **Unlocks:** M1 (Core Migration)
> **Estimated effort:** 3–4 hours
> **Target:** March 4 (Day 1 morning)

---

## Goal

AWS account fully configured, all required services enabled and verified, codebase audited for migration scope, and new project repo scaffolded.

---

## Tasks

### 0.1 — AWS Account & IAM

- [x] Create AWS account (or use Academy Learner Lab credentials)
- [x] Set region to **us-east-1** (best Bedrock model availability)
- [x] Enable billing alerts at $10, $30, $45 thresholds
- [x] Create IAM user `careerforge-dev` with programmatic access
- [x] Download `credentials.csv` and run `aws configure` locally
- [x] Verify CLI works: `aws sts get-caller-identity`

### 0.2 — Enable Bedrock Model Access ⚠️ CRITICAL — DO FIRST

- [x] Console → Amazon Bedrock → Model Access → Request:
  - `anthropic.claude-3-haiku-20240307-v1:0` (primary LLM)
  - `amazon.titan-embed-text-v2:0` (embeddings)
- [x] Wait for approval (1–5 min, but can take longer)
- [x] Verify with quick boto3 test:
  ```python
  import boto3, json
  client = boto3.client("bedrock-runtime", region_name="us-east-1")
  resp = client.invoke_model(
      modelId="anthropic.claude-3-haiku-20240307-v1:0",
      body=json.dumps({
          "anthropic_version": "bedrock-2023-05-31",
          "max_tokens": 64,
          "messages": [{"role": "user", "content": "Say hello"}]
      })
  )
  print(json.loads(resp["body"].read()))
  ```
- [x] Verify Titan embeddings:
  ```python
  resp = client.invoke_model(
      modelId="amazon.titan-embed-text-v2:0",
      body=json.dumps({"inputText": "test embedding"})
  )
  print(len(json.loads(resp["body"].read())["embedding"]))  # should be 1024
  ```

### 0.3 — Provision AWS Resources

- [x] **S3:** Create bucket `careerforge-pdfs-{account-id}` in us-east-1
  - Enable versioning
  - Block all public access
- [x] **DynamoDB:** Create tables (on-demand billing):
  - `Users` — PK: `userId` (String)
  - `Projects` — PK: `userId` (String), SK: `projectId` (String)
  - `Resumes` — PK: `userId` (String), SK: `resumeId` (String)
  - `Jobs` — PK: `jobId` (String)
  - `Applications` — PK: `userId` (String), SK: `applicationId` (String)
  - `Roadmaps` — PK: `userId` (String), SK: `roadmapId` (String)
- [x] **EC2:** Don't launch yet — just confirm `t3.micro` is available in us-east-1
- [x] **Amplify:** Don't connect yet — just verify the service is accessible

### 0.4 — Codebase Audit

- [x] Map all `gemini_client` imports across `latex-agent/backend/app/`
- [x] Map all Gemini embedding calls in `latex-agent/backend/app/services/embedding_service.py`
- [x] List all Firestore/GCP calls in `job-scrapper/backend/`
- [x] List all SQLite/SQLAlchemy models in `latex-agent/backend/app/`
- [x] Confirm `latex.ytotech.com` API is still responding
- [x] Test `jobspy` scrape locally — confirm LinkedIn data comes through
- [x] Document all env vars needed across both projects

### 0.5 — Scaffold New Repo

- [x] Create `project/` directory structure:
  ```
  project/
    backend/
      app/
        services/       # bedrock_client, s3_service, dynamo_service
        routes/         # auth, projects, resumes, jobs, gap, roadmap
        models/         # DynamoDB schemas
      requirements.txt
      .env.example
    frontend/
      src/
      package.json
    lambda/
      job-scout/        # scraper Lambda
  ```
- [x] Copy `latex-agent/backend` as starting point for `project/backend/`
- [x] Copy `latex-agent/frontend` as starting point for `project/frontend/`
- [x] Create `.env.aws.example` with all required keys:
  ```
  AWS_REGION=us-east-1
  AWS_ACCESS_KEY_ID=
  AWS_SECRET_ACCESS_KEY=
  S3_BUCKET=careerforge-pdfs-xxxxx
  DYNAMO_TABLE_PREFIX=careerforge-
  BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
  BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
  GITHUB_CLIENT_ID=
  GITHUB_CLIENT_SECRET=
  JWT_SECRET=
  ```

---

## Verification Checklist

- [x] `aws sts get-caller-identity` returns valid account
- [x] Bedrock Claude invoke returns a response (not access denied)
- [x] Bedrock Titan embed returns 1024-dim vector
- [x] S3 bucket exists and `aws s3 ls` shows it
- [x] All 6 DynamoDB tables visible in console
- [x] `project/backend/` has copied latex-agent code
- [x] `project/frontend/` has copied latex-agent frontend
- [x] Codebase audit notes saved (list of files to change)

---

## Notes

- Bedrock model access approval is the #1 blocker. Request it before doing anything else.
- Don't over-engineer IAM policies for a hackathon — admin access is fine for now.
- us-east-1 is mandatory — other regions may not have Claude 3 Haiku.
