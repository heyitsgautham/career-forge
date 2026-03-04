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

- [ ] Create AWS account (or use Academy Learner Lab credentials)
- [ ] Set region to **us-east-1** (best Bedrock model availability)
- [ ] Enable billing alerts at $10, $30, $45 thresholds
- [ ] Create IAM user `careerforge-dev` with programmatic access
- [ ] Download `credentials.csv` and run `aws configure` locally
- [ ] Verify CLI works: `aws sts get-caller-identity`

### 0.2 — Enable Bedrock Model Access ⚠️ CRITICAL — DO FIRST

- [ ] Console → Amazon Bedrock → Model Access → Request:
  - `anthropic.claude-3-haiku-20240307-v1:0` (primary LLM)
  - `amazon.titan-embed-text-v2:0` (embeddings)
- [ ] Wait for approval (1–5 min, but can take longer)
- [ ] Verify with quick boto3 test:
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
- [ ] Verify Titan embeddings:
  ```python
  resp = client.invoke_model(
      modelId="amazon.titan-embed-text-v2:0",
      body=json.dumps({"inputText": "test embedding"})
  )
  print(len(json.loads(resp["body"].read())["embedding"]))  # should be 1024
  ```

### 0.3 — Provision AWS Resources

- [ ] **S3:** Create bucket `careerforge-pdfs-{account-id}` in us-east-1
  - Enable versioning
  - Block all public access
- [ ] **DynamoDB:** Create tables (on-demand billing):
  - `Users` — PK: `userId` (String)
  - `Projects` — PK: `userId` (String), SK: `projectId` (String)
  - `Resumes` — PK: `userId` (String), SK: `resumeId` (String)
  - `Jobs` — PK: `jobId` (String)
  - `Applications` — PK: `userId` (String), SK: `applicationId` (String)
  - `Roadmaps` — PK: `userId` (String), SK: `roadmapId` (String)
- [ ] **EC2:** Don't launch yet — just confirm `t3.micro` is available in us-east-1
- [ ] **Amplify:** Don't connect yet — just verify the service is accessible

### 0.4 — Codebase Audit

- [ ] Map all `gemini_client` imports across `latex-agent/backend/app/`
- [ ] Map all Gemini embedding calls in `latex-agent/backend/app/services/embedding_service.py`
- [ ] List all Firestore/GCP calls in `job-scrapper/backend/`
- [ ] List all SQLite/SQLAlchemy models in `latex-agent/backend/app/`
- [ ] Confirm `latex.ytotech.com` API is still responding
- [ ] Test `jobspy` scrape locally — confirm LinkedIn data comes through
- [ ] Document all env vars needed across both projects

### 0.5 — Scaffold New Repo

- [ ] Create `project/` directory structure:
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
- [ ] Copy `latex-agent/backend` as starting point for `project/backend/`
- [ ] Copy `latex-agent/frontend` as starting point for `project/frontend/`
- [ ] Create `.env.aws.example` with all required keys:
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

- [ ] `aws sts get-caller-identity` returns valid account
- [ ] Bedrock Claude invoke returns a response (not access denied)
- [ ] Bedrock Titan embed returns 1024-dim vector
- [ ] S3 bucket exists and `aws s3 ls` shows it
- [ ] All 6 DynamoDB tables visible in console
- [ ] `project/backend/` has copied latex-agent code
- [ ] `project/frontend/` has copied latex-agent frontend
- [ ] Codebase audit notes saved (list of files to change)

---

## Notes

- Bedrock model access approval is the #1 blocker. Request it before doing anything else.
- Don't over-engineer IAM policies for a hackathon — admin access is fine for now.
- us-east-1 is mandatory — other regions may not have Claude 3 Haiku.
