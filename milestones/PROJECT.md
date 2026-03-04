# CareerForge — AI Career Accelerator

> Turn any student's GitHub profile into a job-ready career engine — generating tailored resumes, mapping skill gaps, creating learning roadmaps, and matching jobs — all powered by Amazon Bedrock.

---

## The Problem

Students and early-career developers face a fragmented, exhausting job-hunting process:

1. **No resume reflects their real skills** — they manually list technologies instead of showcasing what they've actually built.
2. **Skill gaps are invisible** — they don't know what's missing until a recruiter rejects them.
3. **Learning is unguided** — they pick random tutorials instead of targeted, project-based upskilling.
4. **Job applications are one-size-fits-all** — the same resume goes to every company, ignoring ATS keywords.
5. **Tracking applications is chaos** — spreadsheets, bookmarks, lost emails.

CareerForge solves all five in a single, AI-driven pipeline.

---

## Core Idea

CareerForge is a **unified AI career platform** that chains together four capabilities:

```
GitHub Profile → Skill Extraction → Resume Generation → Skill Gap Analysis → Learning Roadmap → Job Matching → Tailored Resumes → Application Tracking
```

The key insight: **your GitHub repositories are the single source of truth** for what you can build. Everything else — resume content, skill assessments, learning plans, job fit scores — is derived from that ground truth by AI agents.

---

## Hackathon Context

- **Event:** AI ASCEND Hackathon 2026 — Grand Finale (March 7–8, 2026)
- **Theme:** Education & Employability
- **Cloud:** AWS Academy Learner Labs ($50 credits)
- **Edge:** ~75% of the system is already built across four reference projects. CareerForge unifies, ports to AWS, and adds the missing pieces.

---

## System Architecture — The 6-Phase Pipeline

### Phase 1: Auth & Consent

The user logs in via **GitHub OAuth 2.0**, granting read access to their repositories and profile.

| Component       | Detail                                              | AWS Service       |
|-----------------|------------------------------------------------------|-------------------|
| GitHub OAuth    | Standard OAuth flow, repo read scope                 | Amazon Cognito    |
| Consent Screen  | Explicit permission for repo + profile data          | —                 |
| User Profile    | Username, avatar, public info — stored on first login| DynamoDB          |

**Output:** Access token stored securely → repo fetch begins.

---

### Phase 2: Repo Ingestion & Analysis

The system fetches all public (and consented private) repos, then runs a multi-step analysis pipeline:

```
Fetch Repos → Parse Code → LLM Summariser → Skill Extractor → Vector Embed
```

| Step             | What Happens                                                        | AWS Service                  |
|------------------|----------------------------------------------------------------------|------------------------------|
| Fetch Repos      | GitHub API → list repos, clone metadata, extract README              | Lambda (orchestration)       |
| Parse Code       | Language detection, file tree analysis, dependency extraction        | Lambda                       |
| LLM Summariser   | Claude summarises each repo into structured skill signals            | Amazon Bedrock (Claude)      |
| Skill Extractor  | Maps repos → tech skills, frameworks, domains, complexity level      | Bedrock                      |
| Vector Embed     | Skill profile embedded as vectors for similarity search              | Bedrock Titan Embeddings v2  |
| Storage          | Raw repo snapshots + embeddings persisted                            | S3 + OpenSearch Serverless   |

**Output:** A rich, vectorised skill profile representing everything the user has built.

---

### Phase 3A: LaTeX Resume Generator

Using the extracted skills and project descriptions, an AI agent generates a professional one-page resume in LaTeX (Jake's Resume template), grounded entirely to real data — **zero hallucination**.

| Step            | What Happens                                                       | AWS Service        |
|-----------------|---------------------------------------------------------------------|--------------------|
| Resume Agent    | Bedrock Claude drafts structured LaTeX from GitHub skills + projects| Bedrock + Lambda   |
| LaTeX Compiler  | `.tex` → PDF compilation                                           | Lambda (Docker)    |
| Base Resume PDF | Stored, versioned per analysis run                                  | S3                 |

**Key design:** The agent is prompt-constrained to only use data from the user's actual GitHub profile. It ranks projects by relevance, selects the top 3–4, and generates ATS-optimised bullet points with action verbs and metrics.

**Output:** A downloadable base resume PDF stored in S3.

---

### Phase 3B: Role Selection & Skill Gap Analysis

The user selects 1–3 target career roles (e.g., Backend SDE, ML Engineer, DevOps). The system computes a vector similarity between their skill profile and the role's required skill benchmark.

| Step              | What Happens                                                     | AWS Service            |
|-------------------|--------------------------------------------------------------------|------------------------|
| Career Role Picker| UI presents role options — user selects targets                    | —                      |
| Skill Gap Analysis| User skill vector vs. role skill vector → gap score per domain     | Bedrock + OpenSearch   |
| Gap Report        | Visual radar chart + missing skills list with priority badges      | —                      |

**Output:** A gap report like: *"You have 70% of Backend SDE skills. Missing: System Design, SQL, Docker."*

---

### Phase 4: LearnWeave — Project-Based Learning Roadmap

The skill gap feeds directly into a personalised learning plan. Instead of generic course recommendations, LearnWeave generates **project-based milestones** — each milestone is a mini-project the user builds to close a specific gap.

| Component          | What Happens                                                     | AWS Service   |
|--------------------|-------------------------------------------------------------------|---------------|
| Roadmap Generator  | Claude creates a 4–8 week plan targeting exact skill gaps          | Bedrock Claude|
| Milestones         | Each = 1 project to build, with title, stack, estimated hours      | —             |
| Curated References | Docs, repos, YouTube playlists, papers — ranked per topic          | —             |
| Progress Tracker   | User marks milestones complete → roadmap updates dynamically       | DynamoDB      |

**Output:** A structured, trackable learning path that directly addresses what's missing.

---

### Phase 5: Job Scout — Scrape & Match

A scheduled scraper monitors job portals (LinkedIn, Naukri, Internshala, Wellfound) for roles matching the user's selected career targets. Each job description is analysed and scored against the user's profile.

| Component     | What Happens                                                        | AWS Service            |
|---------------|----------------------------------------------------------------------|------------------------|
| Job Scraper   | Scheduled Lambda scrapes job portals for matching roles               | Lambda + EventBridge   |
| JD Analyser   | Extracts required skills, keywords, ATS signals from each JD         | Bedrock Claude         |
| Match Scorer  | Vector similarity → ranks jobs by fit %                               | OpenSearch             |
| Job Board UI  | Ranked list with match %, missing skills, "Generate Resume" button    | —                      |

**Output:** A personalised job board ranked by fit, not just recency.

---

### Phase 6: Tailored Resumes & Apply

For each specific job, the system generates a **unique, tailored resume** — reordering skills, tweaking project descriptions, and injecting JD-specific keywords for ATS optimisation.

| Component           | What Happens                                                     | AWS Service        |
|---------------------|-------------------------------------------------------------------|--------------------|
| Resume Tailor Agent | Rewrites base resume to match specific JD keywords & ATS signals  | Bedrock Claude     |
| Per-Job PDF         | Unique `.tex` → PDF compiled per application                      | Lambda + S3        |
| One-Click Apply     | Pre-fills application with tailored resume + profile data          | —                  |
| Application Tracker | Tracks Applied / Viewed / Interview stages across all portals      | DynamoDB + SNS     |

**Output:** Job-specific resumes + a Kanban-style application tracker.

---

## AWS Infrastructure

All services run within the $50 AWS credit budget:

| Service                    | Role                                                    | Cost Estimate |
|----------------------------|---------------------------------------------------------|---------------|
| **Amazon Bedrock**         | Claude 3 Haiku — all LLM tasks (summarise, generate, tailor) | ~$2          |
| **Bedrock Titan Embed v2** | Vector embeddings for skill profiles and JDs             | ~$0.50       |
| **OpenSearch Serverless**  | Vector store for skill profiles, JD embeddings, role benchmarks | ~$2       |
| **AWS Lambda**             | All compute — repo fetch, LaTeX compile, job scrape      | ~$0          |
| **Amazon S3**              | Resume PDFs, `.tex` files, raw repo snapshots, JD cache  | ~$0.01       |
| **DynamoDB**               | User profiles, skill vectors, roadmap state, app tracking| ~$0          |
| **EC2 t3.micro**           | Backend FastAPI server (free tier)                       | ~$0          |
| **AWS Amplify**            | Frontend hosting (auto-deploy from GitHub)               | ~$0          |
| **Amazon Cognito**         | Auth + JWT tokens                                        | ~$0          |
| **EventBridge**            | Scheduled triggers for job scraper Lambda                | ~$0          |
| **Total**                  |                                                          | **~$5**      |

---

## Reference Projects (Prior Art)

CareerForge is built on top of four existing projects, each handling a piece of the pipeline:

| Project             | What It Does                                           | Ported From         |
|---------------------|--------------------------------------------------------|---------------------|
| **latex-agent**     | JD-aware, GitHub-grounded LaTeX resume generation       | Gemini → Bedrock    |
| **job-scrapper**    | Automated job scraping + AI categorisation + tracking   | Firestore → DynamoDB|
| **learn-weave**     | AI-powered learning with Bloom's Taxonomy alignment     | GCP ADK → Bedrock   |
| **resume-maker-latex** | LaTeX template library + Copilot-assisted generation | Templates reused    |

### Migration Map (GCP → AWS)

| Component       | Current (GCP/Local)           | AWS Replacement                      |
|-----------------|-------------------------------|--------------------------------------|
| LLM             | Gemini 2.0/2.5 Flash         | Bedrock Claude 3 Haiku               |
| Embeddings      | Gemini `text-embedding-004`   | Bedrock Titan Text Embeddings v2     |
| Vector DB       | ChromaDB (local)              | OpenSearch Serverless / ChromaDB     |
| Relational DB   | SQLite (local)                | DynamoDB                             |
| File Storage    | Local filesystem              | Amazon S3                            |
| LaTeX Compile   | latex.ytotech.com             | Keep ytotech + store PDF in S3       |
| Backend         | Local FastAPI                 | EC2 t3.micro + Nginx                 |
| Frontend        | Local Next.js dev             | AWS Amplify (GitHub auto-deploy)     |
| Job Scraper     | jobspy (local Python)         | Lambda + EventBridge schedule        |

---

## Core Flow — End to End

```
┌─────────────┐
│  GitHub      │
│  OAuth Login │
└──────┬──────┘
       │ access token
       ▼
┌─────────────────────┐
│  Repo Ingestion     │
│  Fetch → Parse →    │
│  Summarise → Embed  │
└──────┬──────────────┘
       │ skill profile (vectorised)
       ▼
┌──────┴──────────────────────────────┐
│              PARALLEL               │
│                                     │
│  ┌──────────────┐  ┌─────────────┐  │
│  │ 3A: Resume   │  │ 3B: Role    │  │
│  │ Generator    │  │ Selection + │  │
│  │ (Base PDF)   │  │ Gap Analysis│  │
│  └──────┬───────┘  └──────┬──────┘  │
│         │                 │         │
└─────────┼─────────────────┼─────────┘
          │                 │
          │          ┌──────▼──────┐
          │          │ 4: LearnWeave│
          │          │ Roadmap     │
          │          └─────────────┘
          │
   ┌──────▼──────────────┐
   │ 5: Job Scout        │
   │ Scrape → Analyse →  │
   │ Match & Rank        │
   └──────┬──────────────┘
          │ per-job click
          ▼
   ┌─────────────────────┐
   │ 6: Tailored Resume  │
   │ + Application Track │
   └─────────────────────┘
```

---

## Key Technical Decisions

1. **Ground truth = GitHub repos.** No self-reported skills. Every resume bullet is traceable to an actual repository.
2. **Anti-hallucination by design.** The resume agent is prompt-constrained to only reference stored project data — never fabricate experience.
3. **Vector similarity for everything.** Skill gap analysis, job matching, and project ranking all use the same embedding space for consistency.
4. **LaTeX, not DOCX.** Jake's Resume template is the gold standard for ATS-friendly formatting. LaTeX ensures pixel-perfect, deterministic output.
5. **Per-job tailoring, not one-size-fits-all.** Each application gets a unique resume rewritten to match the specific JD's keywords and requirements.
6. **Project-based learning over course recommendations.** LearnWeave generates projects to build, not playlists to watch — closing gaps through practice.

---

## Demo Flow (3 minutes)

| Time      | Action                                                              |
|-----------|---------------------------------------------------------------------|
| 0:00–0:20 | Open app → GitHub OAuth login → "Connecting to your repos…"         |
| 0:20–0:50 | Skill profile appears — tech stack extracted from real repos         |
| 0:50–1:20 | Select "Backend SDE" → radar chart animates → gap report shows       |
| 1:20–1:50 | Base resume compiles live → PDF opens (Jake's template, auto-filled) |
| 1:50–2:20 | Job Scout tab → ranked jobs → click one → tailored resume generates  |
| 2:20–2:50 | LearnWeave roadmap → 4-week plan → Application tracker Kanban        |
| 2:50–3:00 | AWS console: Bedrock logs, S3 bucket, DynamoDB tables, Lambda        |

---

## Milestones

The project is broken into 7 milestones with a clear topological order. See individual files for full task breakdowns.

### Dependency Graph

```
M0 (AWS Setup)
 │
 ▼
M1 (Core Migration)
 │
 ├───────────────┬───────────────┐
 ▼               ▼               ▼
M2 (Resume)    M3 (Gap +       M4 (Job
               LearnWeave)      Scout)        ← PARALLEL
 │                               │
 └───────────────┬───────────────┘
                 ▼
          M5 (Tailored Apply)
                 │
                 ▼
          M6 (Deploy & Polish)
```

### Milestone Index

| Milestone | Name | Depends On | Parallel With | Est. Hours |
|-----------|------|-----------|---------------|------------|
| [M0](M0-aws-setup.md) | AWS Setup & Codebase Audit | — | — | 3–4 hrs |
| [M1](M1-core-migration.md) | Core AWS Migration | M0 | — | 6–8 hrs |
| [M2](M2-resume-generator.md) | LaTeX Resume Generator | M1 | M3, M4 | 4–5 hrs |
| [M3](M3-skill-gap-learnweave.md) | Skill Gap + LearnWeave | M1 | M2, M4 | 5–6 hrs |
| [M4](M4-job-scout.md) | Job Scout (Scrape & Match) | M1 | M2, M3 | 4–5 hrs |
| [M5](M5-tailored-apply.md) | Tailored Resumes & Apply | M2, M4 | — | 4–5 hrs |
| [M6](M6-deploy-polish.md) | Deploy, Polish & Demo | M2–M5 | — | 4–6 hrs |

### Execution Order

**Sequential (critical path):**
```
M0 → M1 → M2 → M5 → M6
```

**Parallel lanes (after M1 completes):**
- **Lane A:** M2 (Resume Generator)
- **Lane B:** M3 (Skill Gap + LearnWeave)
- **Lane C:** M4 (Job Scout)

**Convergence point:** M5 requires both M2 and M4 to be complete.

### Day Mapping

| Day | Milestones | Focus |
|-----|-----------|-------|
| **Mar 4** | M0 + M1 (start) | AWS setup, begin migration |
| **Mar 5** | M1 (finish) + M2/M3/M4 (start parallel) | Core migration done, features begin |
| **Mar 6** | M2/M3/M4 (finish) + M5 | All features, tailored apply |
| **Mar 7** | M5 (finish) + M6 | Deploy, stress-test, rehearse |
| **Mar 8** | M6 (polish) | UI polish, submission, demo |

---

## Elevator Pitch

*"CareerForge turns any student's GitHub profile into a job-ready career engine. It extracts real skills from your code, generates ATS-optimised LaTeX resumes tailored to each job, identifies your skill gaps with visual analytics, and builds a personal learning roadmap to close them — all powered by Amazon Bedrock on AWS."*
