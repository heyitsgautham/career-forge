# CareerForge — AI Career Accelerator

> Turn any student's GitHub profile into a job-ready career engine — generating tailored resumes, mapping skill gaps, creating learning roadmaps, and matching jobs — powered by Amazon Bedrock.

---

## What It Does

CareerForge is a unified AI platform for students and early-career developers. You log in with GitHub, and the system does the rest:

1. **Analyses your repos** — extracts real skills, frameworks, and project complexity from your code
2. **Generates a LaTeX resume** — one-page, ATS-optimised, grounded to your actual GitHub projects
3. **Maps your skill gaps** — radar chart comparing your profile to your target role's requirements
4. **Builds a learning roadmap** — project-based milestones to close exactly the gaps that matter
5. **Scouts jobs** — scrapes live openings and ranks them by match % against your profile
6. **Tailors per-job resumes** — unique PDF for each application with JD-specific keywords injected
7. **Tracks applications** — Kanban board across all portals

---

## Tech Stack

| Layer     | Technology                                      |
|-----------|-------------------------------------------------|
| LLM       | Amazon Bedrock (Claude 3 Haiku)                 |
| Embeddings| Bedrock Titan Text Embeddings v2 (1024-dim)     |
| Vector DB | OpenSearch Serverless / ChromaDB                |
| Database  | Amazon DynamoDB                                 |
| Storage   | Amazon S3                                       |
| Backend   | FastAPI (Python) on EC2 t3.micro                |
| Frontend  | Next.js 14 + TailwindCSS on AWS Amplify         |
| Auth      | GitHub OAuth 2.0 + JWT                          |
| LaTeX     | latex.ytotech.com → PDF compiled, stored in S3  |
| Jobs      | jobspy (LinkedIn/Indeed) on AWS Lambda          |

---

## Repository Structure

```
career-forge/
├── project/              # Main application (in progress)
│   ├── backend/          # FastAPI server
│   └── frontend/         # Next.js app
├── milestones/           # Project breakdown and planning
│   ├── PROJECT.md        # Full architecture + milestone index
│   ├── M0-aws-setup.md
│   ├── M1-core-migration.md
│   ├── M2-resume-generator.md
│   ├── M3-skill-gap-learnweave.md
│   ├── M4-job-scout.md
│   ├── M5-tailored-apply.md
│   └── M6-deploy-polish.md
├── ref-repos/            # Prior-art projects being unified
│   ├── latex-agent/      # Resume generation (FastAPI + Gemini + LaTeX)
│   ├── job-scrapper/     # Job scraping + AI categorisation (GCP)
│   ├── learn-weave/      # Project-based learning platform (GCP ADK)
│   └── resume-maker-latex/ # LaTeX templates + Copilot-assisted generation
└── docs/
    ├── career-architecture.html  # Full system architecture diagram
    └── roadmap.html              # 5-day execution plan
```

---

## Reference Repositories

CareerForge unifies four existing projects, porting them from GCP to AWS:

### [`latex-agent`](ref-repos/latex-agent/)
JD-aware GitHub-grounded LaTeX resume generator. The user's GitHub projects are ranked by relevance to a job description, and Claude generates a one-page LaTeX resume populated entirely from real project data — no hallucination.
- Stack: FastAPI, SQLite, ChromaDB, Gemini 2.5, Next.js
- **Migration:** Gemini → Bedrock, SQLite → DynamoDB, local storage → S3

### [`job-scrapper`](ref-repos/job-scrapper/)
Automated job scraper and tracker. Scrapes LinkedIn and other portals via `jobspy`, uses AI to categorise and score each posting, and tracks application status per user.
- Stack: FastAPI, Firestore, python-jobspy, Vertex AI, React
- **Migration:** Gemini/Firestore → Bedrock/DynamoDB, Cloud Run → Lambda

### [`learn-weave`](ref-repos/learn-weave/)
AI-powered learning platform built around Bloom's Taxonomy. Generates project-based courses from uploaded PDFs using 8 specialised agents. Being adapted into CareerForge's LearnWeave roadmap feature.
- Stack: FastAPI, Google ADK, ChromaDB, MySQL, React + Vite
- **Migration:** Google ADK agents → Bedrock Claude, Cloud Run → EC2

### [`resume-maker-latex`](ref-repos/resume-maker-latex/)
LaTeX template library with GitHub Copilot slash command integration for AI-assisted resume generation. Provides the baseline LaTeX templates and project summary conventions used across the platform.
- Stack: LaTeX, GitHub Copilot, Markdown
- **Reuse:** Templates and project summary format used as-is

---

## Milestone Overview

```
M0 (AWS Setup) → M1 (Core Migration) → ┌─ M2 (Resume)
                                        ├─ M3 (Skill Gap + LearnWeave)  ← parallel
                                        └─ M4 (Job Scout)
                                              │
                                        M5 (Tailored Apply)
                                              │
                                        M6 (Deploy & Polish)
```

See [milestones/PROJECT.md](milestones/PROJECT.md) for the full architecture, pipeline breakdown, and task-level detail.

---

## Context

Built for **AI ASCEND Hackathon 2026** (Education & Employability theme) on AWS Academy Learner Labs with a $50 credit budget. Target deployment: March 7–8, 2026.

