# CareerForge

CareerForge turns a student's GitHub profile into job-search material.
It imports your repositories, writes a one-page LaTeX resume grounded in those projects, scores your skills against a target role, builds a learning roadmap for the gaps, and ranks scraped job postings by how well they match you.

It is a full-stack app with a FastAPI backend, a Next.js frontend and a nightly AWS Lambda.
The production setup runs on AWS (Bedrock, DynamoDB, S3, KMS, Secrets Manager, Cognito).
For local work the backend also runs on SQLite with no AWS account at all.

[![CI](https://github.com/heyitsgautham/career-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/heyitsgautham/career-forge/actions/workflows/ci.yml)

## What it does

| Feature | Backend route prefix | Frontend screen |
|---|---|---|
| Email, GitHub, Google (Cognito) and LinkedIn sign-in | `/api/auth` | `/login` |
| GitHub App repo import and project extraction | `/api/github`, `/api/projects` | Dashboard, Projects |
| LaTeX resume generation, editing and PDF compile | `/api/resumes`, `/api/templates` | Resumes, resume editor |
| Job description storage and matching | `/api/jobs` | Jobs |
| Skill gap report and learning roadmap | `/api/skill-gap` | Skill gap |
| Job Scout scraping, per-job resume tailoring, application tracker | `/api` | Job Scout, Apply |
| Project-based roadmap suggestions | `/api/project-roadmap` | Project roadmap |
| Health checks | `/health`, `/health/db`, `/health/services` | none |

## Repository layout

```
career-forge/
├── project/
│   ├── backend/              FastAPI app (Python 3.11, uv)
│   │   ├── app/
│   │   │   ├── api/routes/   HTTP routes, one module per feature
│   │   │   ├── api/deps.py   auth dependencies (JWT to user)
│   │   │   ├── core/         settings, database, security, cache headers
│   │   │   ├── models/       SQLAlchemy models for the SQLite backend
│   │   │   ├── services/     Bedrock, DynamoDB, S3, scrapers, matching, LaTeX
│   │   │   └── data/         role skill benchmarks
│   │   ├── tests/            pytest suite, runs offline
│   │   ├── scripts/          one-off maintenance and smoke_* live-AWS checks
│   │   ├── pyproject.toml    dependencies and tool config
│   │   └── uv.lock           locked dependency versions
│   ├── frontend/             Next.js 14 App Router app (TypeScript, Tailwind)
│   │   └── src/
│   │       ├── app/          pages
│   │       ├── components/   dashboard screens, resume editor, ui kit
│   │       ├── hooks/        toast state
│   │       └── lib/          axios API client, React Query keys
│   └── lambda/daily-job-digest/   nightly SNS email of top job matches (AWS SAM)
├── docs/                     architecture and security notes
├── milestones/               original build plan and milestone reports
└── docker-compose.yml        local backend and frontend stack
```

## Architecture

The browser talks to the FastAPI backend through the axios client in `project/frontend/src/lib/api.ts`.
The client sends the app JWT from `localStorage` as a bearer token, and a 401 response sends the user back to `/login`.

The backend picks its storage at startup from `USE_DYNAMO`.
With `USE_DYNAMO=true` it reads and writes DynamoDB tables through `app/services/dynamo_service.py` and starts an APScheduler job that scrapes job portals every hour.
With `USE_DYNAMO=false` it creates SQLite tables from the models in `app/models/` and skips the scheduler.

Resume generation in `app/services/resume_agent.py` sends project summaries and the user profile to Bedrock Claude, gets structured JSON back, and renders it to LaTeX with the pure functions in `app/services/resume_latex.py`.
`app/services/latex_service.py` compiles the LaTeX to PDF and `app/services/s3_service.py` stores the result.

Job matching in `app/services/match_scorer.py` blends cosine similarity of Titan embeddings (55 percent) with skill keyword overlap (45 percent).
Skill gap scoring in `app/services/gap_analysis.py` compares Bedrock-scored skill domains against the benchmarks in `app/data/role_benchmarks.json`.

Settings live in `app/core/config.py`.
When `USE_SECRETS_MANAGER=true`, secrets left at their defaults are fetched from AWS Secrets Manager at startup.
GitHub and LinkedIn tokens are encrypted with KMS before they are stored.

The backend logs JSON lines through structlog.

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python | 3.11 | backend |
| uv | 0.5 or newer | backend dependencies |
| Node.js | 22.12 or newer (see `project/frontend/.nvmrc`) | frontend |
| Docker with Compose | optional | running both services in containers |

## Install

```bash
git clone https://github.com/heyitsgautham/career-forge.git
cd career-forge

# Backend
cd project/backend
uv sync                     # creates .venv from uv.lock, dev tools included
cp .env.example .env        # defaults run on SQLite with no AWS calls

# Frontend
cd ../frontend
npm ci
cp .env.example .env.local
```

`project/backend/requirements.txt` is exported from `uv.lock` for hosts that install with pip.
Regenerate it after a dependency change with `uv export --no-dev --no-hashes -o requirements.txt`.

## Run

Backend, from `project/backend`:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The API docs are at http://localhost:8000/docs and the health check is at http://localhost:8000/health.

Frontend, from `project/frontend`:

```bash
npm run dev
```

Open http://localhost:3000 and sign up with an email and password.
Features that call Bedrock, such as resume generation and skill scoring, need AWS credentials with Bedrock access in `project/backend/.env`.

### With Docker Compose

From the repo root:

```bash
cp .env.example .env        # optional, sets the JWT and app secrets
docker compose up --build
```

Compose starts the backend on port 8000 with SQLite in a named volume, then the frontend on port 3000 once the backend health check passes.
It sets `USE_DYNAMO=false` and `USE_SECRETS_MANAGER=false`, so it starts without AWS credentials.
The image does not include Playwright browsers, so the Naukri and LinkedIn scrapers do not run inside it.

## Test

Backend, from `project/backend`:

```bash
uv run pytest                    # offline, uses a throwaway SQLite database
uv run pytest --cov              # with coverage, fails under the floor in pyproject.toml
uv run ruff check .              # lint
uv run ruff format --check .     # formatting
```

`tests/conftest.py` turns off Secrets Manager and DynamoDB and sets dummy AWS credentials, so the suite never calls AWS.
Tests that touch Bedrock or embeddings replace those clients with stubs.

Frontend, from `project/frontend`:

```bash
npm test                 # Vitest in jsdom
npm run test:coverage    # with v8 coverage
npm run lint             # next lint
npm run typecheck        # tsc --noEmit
npm run build            # production build
```

The scripts named `smoke_*.py` in `project/backend/scripts/` are manual checks against live AWS services.
They are not part of the test suite, and they cost money to run.

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request.

| Job | Steps |
|---|---|
| Backend | `uv sync --frozen`, ruff check, ruff format check, pytest with coverage |
| Frontend | `npm ci`, lint, typecheck, Vitest with coverage, production build |
| Dependency audit | pip-audit on `requirements.txt`, audit-ci on runtime npm packages |
| Secret scan | gitleaks over the working tree with `.gitleaks.toml` |

Each audit ignore list sits next to its command with the reason for every entry.
The Next.js advisories stay allowlisted until the frontend moves to Next 15.

## Environment variables

Each `.env.example` lists every variable its service reads, grouped with comments.

| File | Copy to | Read by |
|---|---|---|
| `project/backend/.env.example` | `project/backend/.env` | `app/core/config.py` |
| `project/frontend/.env.example` | `project/frontend/.env.local` | Next.js at build and dev time |
| `.env.example` | `.env` | `docker-compose.yml` |

The Lambda in `project/lambda/daily-job-digest` reads `DYNAMODB_TABLE`, `SNS_TOPIC_ARN`, `TOP_JOBS_COUNT` and `AWS_REGION`, and `template.yaml` sets them at deploy time.

## Deployment notes

The hackathon deployment ran the backend on EC2 and the frontend on AWS Amplify.
`docs/aws-architecture.md` and `docs/aws-security.md` describe the AWS resources and the IAM setup.
`project/lambda/daily-job-digest/setup.sh` deploys the digest Lambda with AWS SAM.

## Background

CareerForge was built for the AI ASCEND Hackathon 2026 (Education and Employability theme).
It merges four earlier projects, a LaTeX resume agent, a job scraper, the LearnWeave learning platform and a LaTeX template library, and moves them from GCP to AWS.
`milestones/PROJECT.md` has the original plan and `milestones/reports/` has a report per milestone.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
