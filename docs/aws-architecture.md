# AWS Architecture — Career Forge

1. aws dynamo db
2. aws s3
3. aws lambda
4. aws bedrock
5. aws kms
6. aws secrets manager
7. aws cloudwatch
8. aws sns
9. aws eventbridge
10. aws congnito
11. aws titan embeddings

---

## 1. AWS DynamoDB

**What**
Serverless NoSQL key-value and document database. Schema-flexible, single-digit millisecond reads at any scale.

**When**
Every request that touches user data — login, resume save, job scrape result, match score write, history fetch.

**Where**
- `project/backend/app/services/dynamodb_service.py` — shared DynamoDB client and helpers
- Tables: `Users` (auth + profiles), `Resumes` (generated + tailored), `Jobs` (scraped + AI-analyzed + scored)
- Region: `us-east-1`

**Why over alternatives**
| Alternative | Why not |
|---|---|
| RDS / PostgreSQL | Requires a running DB server (cost + ops), overkill for the flexible document shapes (resume JSON, job AI output) |
| Firestore | Google Cloud — exits the AWS ecosystem; requires separate auth/billing |
| MongoDB Atlas | Third-party vendor, extra credential surface, no native IAM |

DynamoDB integrates with IAM roles out of the box, auto-scales to zero when idle, and fits the app's partition-by-`userId` access pattern perfectly.

**How**
- Partition key: `userId` on all tables; sort key: `resumeId` / `jobId` as appropriate
- `boto3` client with IAM role auth (no hardcoded keys)
- On-demand billing mode — zero cost when no traffic
- `Resumes` table stores full LaTeX + PDF S3 key; `Jobs` table stores raw JD + AI fields + `matchScore`/`matchBreakdown`

---

## 2. AWS S3

**What**
Object storage for arbitrary binary blobs — PDFs, LaTeX source files, uploaded documents. Unlimited capacity, 11-nines durability.

**When**
- Resume generation completes → compiled PDF uploaded to S3
- User requests PDF download → signed URL generated (time-limited, no public exposure)
- User uploads existing resume PDF for parsing

**Where**
- `project/backend/app/services/s3_service.py` — `upload_file()`, `list_objects()`, `download_file()`, `generate_presigned_url()`
- Bucket: `careerforge-pdfs-602664593597` (`us-east-1`)
- API routes: `GET /resumes/{id}/pdf` returns the presigned S3 URL

**Why over alternatives**
| Alternative | Why not |
|---|---|
| Local disk (`uploads/pdfs/`) | Lost on container restart, can't scale across instances, not CDN-ready |
| EFS | Heavier, more expensive, designed for mount-point access not HTTP delivery |
| CloudFront-only hosting | Still needs an origin — S3 is that origin |

Presigned URLs mean the FastAPI server never proxies binary payloads; the browser fetches directly from S3.

**How**
- PDFs stored at key pattern `{userId}/{resumeId}.pdf`
- LaTeX source at `{userId}/{resumeId}.tex`
- `generate_presigned_url(expiry=3600)` — 1-hour download links returned to the frontend
- Bucket policy: all objects private; access only via presigned URLs or service IAM role

---

## 3. AWS Lambda

**What**
Serverless compute that runs code in response to events. Zero infra management, scales from 0 to N concurrently, billed per 100ms of execution.

**When**
- **Daily job digest** — fires once per day on a schedule to scrape, score, and notify
- **Job scout pipeline** — event-driven scraping triggered by EventBridge or direct invoke

**Where**
- `project/lambda/daily-job-digest/` — daily digest function
- `project/lambda/job-scout/` — scraping + analysis pipeline function

**Why over alternatives**
| Alternative | Why not |
|---|---|
| EC2 cron job | Requires an always-on server paying ~$0.012/hr even when idle |
| ECS Fargate task | More config (task definition, cluster, VPC), slower cold start for short jobs |
| FastAPI background task | Tied to server lifecycle, drops if server restarts mid-job |

Lambda + EventBridge is the idiomatic AWS pattern for periodic batch jobs — zero cost between runs.

**How**
- Runtime: Python 3.11
- Handler pattern: `handler(event, context)` with structured JSON event payload
- IAM execution role grants: DynamoDB read/write, S3 put, Bedrock invoke, SNS publish, CloudWatch logs
- Deployment: zip artifact or container image pushed to Lambda
- Memory: 512 MB; timeout: 5 min for scrape pipeline

---

## 4. AWS Bedrock

**What**
Managed foundation model inference service. Access dozens of FMs (Amazon Nova, Titan, Claude, Llama, Mistral, etc.) via a single unified API — no GPU provisioning.

**When**
- **Resume generation** — `RESUME_JSON_PROMPT` sent to Nova Pro, returns structured JSON → Python fills Jake's LaTeX template
- **JD analysis** — `jd_analyzer.py` sends raw job description, extracts category/skills/salary/ATS keywords
- **Resume tailoring** — `resume_tailor.py` takes base resume JSON + JD and returns a tailored JSON

**Where**
- `project/backend/app/services/bedrock_client.py` — `generate(prompt) -> str` wrapper around Converse API
- `project/backend/app/services/resume_agent.py` — base resume pipeline
- `project/backend/app/services/resume_tailor.py` — JD-tailored resume
- `project/backend/app/services/jd_analyzer.py` — job description parsing
- Model ID: `amazon.nova-pro-v1:0` (Anthropic models blocked → requires credit card even with credits)

**Why over alternatives**
| Alternative | Why not |
|---|---|
| OpenAI API | Separate billing, no AWS IAM integration, exits the AWS ecosystem |
| Anthropic API directly | Same — separate billing, credit card required, not IAM-controlled |
| Self-hosted LLaMA (EC2 GPU) | $0.50–$3/hr for GPU instance, ops overhead, model management |
| Google Vertex AI | Ties to GCP, separate credentials |

Bedrock uses the same IAM role as the rest of the app — no extra API keys to manage or rotate.

**How**
- `bedrock_client.generate(prompt)` calls `converse` API with model ID and message list
- Returns raw string; caller parses JSON from the string (with regex fence stripping)
- `max_tokens=4096`; `temperature=0.3` for deterministic structured output
- Batch JD analysis: `concurrency=3` async calls via `asyncio.gather`

---

## 5. AWS KMS

**What**
Managed Hardware Security Module (HSM)-backed key management. Creates, stores, and uses cryptographic keys — private key material never leaves AWS hardware.

**When**
Every OAuth token write (GitHub, LinkedIn) and every token read/decrypt in the authentication flow.

**Where**
- `project/backend/app/core/security.py` → `KmsTokenEncryptor` class
- CMK alias: `alias/careerforge-tokens` (key ID `d2c68fae-4c0f-4d46-a995-d5c1af4b8b87`, `us-east-1`)
- Migration script: `project/backend/scripts/migrate_tokens_to_kms.py` — re-encrypts legacy Fernet DB rows

**Why over alternatives**
| Alternative | Why not |
|---|---|
| Fernet (symmetric key in `.env`) | Key is in plaintext config; if env leaks, all tokens are decryptable; no audit trail |
| AES in application code | Same problem — key lives in app memory/config |
| No encryption | OWASP A02 Cryptographic Failure — OAuth tokens are credentials |

KMS gives automatic key rotation, CloudTrail audit logs on every `Encrypt`/`Decrypt` call, and the key material is never extractable.

**How**
- `KmsTokenEncryptor.encrypt(token)` → calls `kms.encrypt(KeyId=..., Plaintext=token)` → base64-encodes ciphertext → stores as `"KMS:<b64>"` in DynamoDB
- Decrypt: strips `"KMS:"` prefix → `kms.decrypt(CiphertextBlob=...)` → returns plaintext
- Legacy Fernet ciphertext (no `"KMS:"` prefix) → falls back to old Fernet decryptor for backward compatibility
- IAM policy: Lambda and FastAPI roles have `kms:Encrypt` + `kms:Decrypt` on the CMK; nothing else does

---

## 6. AWS Secrets Manager

**What**
Managed secrets vault. Stores database passwords, API keys, and secrets — encrypted at rest (KMS), versioned, with built-in rotation support.

**When**
Application startup — `Settings` model fetches all secrets from Secrets Manager before serving any request.

**Where**
- `project/backend/app/core/config.py` → `Settings` Pydantic model, `model_validator(mode="after")` fetches secrets
- Secrets stored:
  - `careerforge/jwt-secret-key` → `JWT_SECRET_KEY`
  - `careerforge/app-secret-key` → `SECRET_KEY`
  - `careerforge/github-app-client-secret` → `GITHUB_APP_CLIENT_SECRET`
  - `careerforge/cognito-app-client-secret` → `COGNITO_APP_CLIENT_SECRET`
  - `careerforge/github-app-private-key` → GitHub App PEM

**Why over alternatives**
| Alternative | Why not |
|---|---|
| Plaintext `.env` file | If the file or container image leaks, secrets are plaintext |
| SSM Parameter Store (Standard) | No built-in rotation, less ergonomic for secrets specifically |
| Hardcoded in source | OWASP A07 — secrets in git history are permanent |

Secrets Manager gives rotation without redeployment, IAM-controlled access per secret, and a full access audit trail.

**How**
- `boto3` `secretsmanager.get_secret_value(SecretId=...)` at startup
- Falls back to environment variable if Secrets Manager is unreachable (local dev without AWS credentials)
- Secrets cached in the `Settings` singleton — no per-request SM calls
- IAM role: only the app's execution role has `secretsmanager:GetSecretValue` on the `careerforge/*` path

---

## 7. AWS CloudWatch

**What**
Unified observability platform: log aggregation, custom metrics, dashboards, and alarms.

**When**
- Continuously — Lambda functions auto-emit all stdout/stderr to CloudWatch Logs
- On error conditions — alarms trigger SNS notifications
- Per scrape run — custom metrics for jobs found, analyzed, errors

**Where**
- Lambda log groups: `/aws/lambda/daily-job-digest`, `/aws/lambda/job-scout` (auto-created)
- FastAPI app: structured JSON logs via Python `logging` → CloudWatch agent (when deployed on EC2/ECS)
- Alarms: Lambda error rate, DynamoDB throttle rate, Bedrock invocation failures

**Why over alternatives**
| Alternative | Why not |
|---|---|
| Self-managed ELK (Elasticsearch, Logstash, Kibana) | Significant ops overhead; servers to maintain |
| Datadog / Grafana Cloud | Additional vendor, additional cost, additional credentials |
| Print-to-stdout only | No persistence, no alerting, no search |

Lambda logs go to CloudWatch with zero configuration — it's the default and costs nothing for moderate volume.

**How**
- Lambda execution role includes `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- Log retention set to 30 days to control cost
- Metric filter on `ERROR` log level → CloudWatch Alarm → SNS topic → email alert
- Custom metric: `PutMetricData` calls from job-scout Lambda for `JobsScraped`, `JobsAnalyzed`, `MatchScoreAvg`

---

## 8. AWS SNS

**What**
Pub/sub messaging and notification service. Publishers send to a topic; all subscribers (email, SMS, Lambda, SQS) receive the message fan-out.

**When**
- Daily job digest send — job-scout Lambda publishes a digest payload to an SNS topic; subscribed user email addresses receive it
- Error alerts — CloudWatch Alarm publishes to an SNS ops topic → engineer email/PagerDuty

**Where**
- `project/lambda/daily-job-digest/` — publishes formatted digest to SNS topic `careerforge-job-digest`
- CloudWatch Alarms → SNS topic `careerforge-ops-alerts`

**Why over alternatives**
| Alternative | Why not |
|---|---|
| SES directly from Lambda | Tightly coupled; adding Slack/webhook later requires Lambda code changes |
| SMTP (self-managed) | Server to manage, deliverability issues, no bounce/unsubscribe handling |
| Direct API call to user | Lambda must know all endpoints — not decoupled |

SNS decouples the producer (job-scout Lambda) from consumers (email, future mobile push, future Slack). Adding a new notification channel = new SNS subscription, no code change.

**How**
- Topic ARN stored in Lambda environment variable
- Lambda calls `sns.publish(TopicArn=..., Message=digest_json, Subject="Your Daily Job Digest")`
- Email subscribers confirmed via SNS double-opt-in
- Message structure: JSON with `jobs` array, `match_count`, `top_match` fields

---

## 9. AWS EventBridge

**What**
Serverless event bus and scheduler. Routes events between AWS services and triggers Lambda functions on cron schedules or event patterns.

**When**
- **Daily 8 AM IST** — EventBridge Scheduler fires the `daily-job-digest` Lambda
- **On-demand** — EventBridge rule can trigger `job-scout` for near-real-time scraping outside the daily window

**Where**
- EventBridge Scheduler rule: `cron(30 2 * * ? *)` (UTC, = 8:00 AM IST) → `daily-job-digest` Lambda
- EventBridge rule: matches `source: "careerforge.job-scout"` pattern → `job-scout` Lambda

**Why over alternatives**
| Alternative | Why not |
|---|---|
| CloudWatch Events (legacy) | EventBridge is the direct successor with the same cron syntax plus event bus features |
| EC2 cron (`crontab`) | Requires running server; fragile if server restarts |
| APScheduler inside FastAPI | Coupled to server process; dies if app crashes or redeploys |
| SQS delay queues | Not designed for time-based scheduling; awkward for daily jobs |

EventBridge Scheduler is the cleanest AWS-native way to run serverless functions on a schedule with no infra.

**How**
- Schedule expression: `cron(30 2 * * ? *)` — fires once daily
- Target: Lambda ARN of `daily-job-digest`
- Input transformer: passes `{"trigger": "scheduled", "date": "<aws.events.event.time>"}` as event
- Retry policy: 2 retries, 60s between attempts (handles transient Lambda cold-start failures)

---

## 10. AWS Cognito

**What**
Managed user identity service. Handles user pools (registration, login, MFA, password reset) and federated identity (OAuth2/OIDC with Google, GitHub, etc.).

**When**
- User registration and login flows
- OAuth2 authorization code flow for third-party providers
- JWT issuance and validation for API request authentication

**Where**
- `project/backend/app/api/routes/auth.py` — Cognito integration for OAuth flows
- `careerforge/cognito-app-client-secret` in Secrets Manager — app client secret
- Frontend: Cognito Hosted UI or custom auth pages hitting Cognito endpoints

**Why over alternatives**
| Alternative | Why not |
|---|---|
| Rolling own JWT auth (current `python-jose` impl) | No MFA, no password reset flows, no OAuth2 federation built-in; more security surface to own |
| Auth0 | Third-party vendor, exits AWS ecosystem, separate billing after free tier |
| Firebase Auth | Google Cloud — cross-cloud dependency |
| Okta | Enterprise pricing, overkill for this scale |

Cognito integrates with IAM, supports GitHub/Google OIDC federation, and issues standard JWT tokens the app already validates. The `python-jose` HS256 auth is the current implementation; Cognito is the target for production hardening.

**How**
- User Pool: email + password sign-up with email verification
- App Client: `ALLOW_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH`
- App Client Secret stored in Secrets Manager (`careerforge/cognito-app-client-secret`)
- Tokens: Cognito issues Access Token (15 min) + Refresh Token (30 days)
- Backend validates JWT against Cognito's public JWKS endpoint (`/.well-known/jwks.json`)

---

## 11. AWS Titan Embeddings

**What**
Amazon's text embedding model (`amazon.titan-embed-text-v1`) accessed via Bedrock. Converts text into a high-dimensional vector that captures semantic meaning — similar text produces similar vectors.

**When**
During job match scoring — whenever a job is scraped and analyzed, both the user's resume and the job description are embedded. Cosine similarity between the two vectors is 55% of the final match score.

**Where**
- `project/backend/app/services/match_scorer.py` — `_compute_vector_score(resume_text, jd_text)` 
- Score formula: `final_score = 0.55 * vector_score + 0.45 * keyword_overlap_score`
- Match breakdown stored in DynamoDB `Jobs` table under `matchBreakdown.vectorScore`

**Why over alternatives**
| Alternative | Why not |
|---|---|
| OpenAI `text-embedding-3-small` | Separate API key, separate billing, exits AWS |
| `sentence-transformers` (self-hosted) | Requires loading a model into Lambda memory (~500 MB+), cold start penalty, no managed scaling |
| Keyword overlap only | Misses semantic similarity — "led backend development" matches "Python FastAPI engineer" conceptually but not lexically |
| TF-IDF cosine similarity | Bag-of-words; no semantic understanding; poor cross-domain matching |

Titan Embeddings is already available in the Bedrock region (`us-east-1`) used by the app — same IAM role, same client, no extra credentials.

**How**
- API call: `bedrock_runtime.invoke_model(modelId="amazon.titan-embed-text-v1", body=json.dumps({"inputText": text}))`
- Returns a 1536-dimension float vector
- Cosine similarity: `dot(v1, v2) / (|v1| * |v2|)` → normalized to 0–1 → scaled to 0–100
- Combined with 45% keyword overlap (skill intersection / union) for the displayed match percentage
- Embeddings not cached — recomputed on each score call (fast enough at current scale)