# M4 — Job Scout (Scrape & Match)

> **Dependencies:** M1 (Bedrock client + DynamoDB working) + M1.5 (Frontend shell with Job Scout tab already built)
> **Unlocks:** M5 (Tailored Resumes & Apply)
> **Parallel with:** M2 (Resume Generator), M3 (Skill Gap + LearnWeave)
> **Estimated effort:** 3–4 hours (frontend now ~1 hr — shell + skeleton cards already exist)
> **Target:** March 5 – March 6

---

## Goal

A scheduled job scraper that fetches live openings from job portals, analyses each JD with AI, and ranks them against the user's skill profile by match percentage.

---

## Tasks

### 4.1 — Port Job Scraper to AWS

- [ ] Copy `job-scrapper/backend/scraper.py` → `project/backend/app/services/job_scraper.py`
- [ ] Remove all Firestore/GCP imports and calls
- [ ] Keep `jobspy` library as the scraping engine (it works)
- [ ] Replace Firestore writes with DynamoDB `Jobs` table writes
- [ ] Configure search parameters:
  - Sites: LinkedIn, Indeed (Naukri/Internshala if jobspy supports)
  - Roles: filtered by user's selected career targets
  - Location: configurable (default: India, Remote)
  - Results: 20–50 per scrape run
- [ ] Test locally: run scrape → jobs appear in DynamoDB

### 4.2 — JD Analysis with Bedrock

- [ ] Port `job-scrapper/backend/ai_analyzer.py` → `app/services/jd_analyzer.py`
- [ ] Replace Vertex AI / Gemini calls with `bedrock_client`
- [ ] For each scraped job, Claude extracts:
  ```json
  {
    "category": "Backend SDE",
    "requiredSkills": ["Python", "Django", "PostgreSQL", "Docker"],
    "experienceLevel": "Entry / 0-2 years",
    "salary": "$80k-$100k",
    "atsKeywords": ["microservices", "REST API", "CI/CD"],
    "isPaid": true
  }
  ```
- [ ] Batch analysis: process all scraped jobs in one pass (or parallel Claude calls)
- [ ] Store enriched job data back to DynamoDB `Jobs` table
- [ ] Test: raw JD text → structured extraction → looks correct

### 4.3 — Match Scoring Engine

- [ ] Create `app/services/match_scorer.py`
- [ ] Method:
  1. Embed JD required skills using Titan embeddings
  2. Compare against user's skill profile vector (from repo ingestion)
  3. Compute cosine similarity → convert to percentage (0–100%)
  4. Also: count keyword overlap between user skills and JD required skills
  5. Final score = weighted blend of vector similarity + keyword overlap
- [ ] Rank all jobs by match score (descending)
- [ ] Store match scores in DynamoDB per user-job pair
- [ ] Test: user with Python/FastAPI skills → Python backend jobs ranked higher than Java jobs

### 4.4 — Lambda Deployment (optional for hackathon)

- [ ] Package scraper as AWS Lambda function:
  - Handler: `handler.lambda_handler(event, context)`
  - Layers: `jobspy`, `boto3` (bundled)
  - Memory: 512 MB, Timeout: 120 sec
- [ ] Create EventBridge rule: trigger every 6 hours
- [ ] IAM role: Lambda needs DynamoDB write + Bedrock invoke permissions
- [ ] **Fallback for hackathon:** if Lambda packaging is painful, run scraper as a background task in the FastAPI server using APScheduler (already exists in job-scrapper)

### 4.5 — Job Scout API Endpoints

- [ ] `POST /api/jobs/scrape` — trigger manual scrape (admin only)
- [ ] `GET /api/jobs` — list all jobs, sorted by match score for authenticated user
  - Query params: `?role=backend-sde&minMatch=50&limit=20`
  - Response includes match percentage per job
- [ ] `GET /api/jobs/{jobId}` — full job detail + JD analysis + match breakdown
- [ ] `GET /api/jobs/stats` — summary stats (total jobs, avg match, top categories)
- [ ] `DELETE /api/jobs/{jobId}` — admin cleanup

### 4.6 — Frontend: Wire Job Scout Tab (Shell + skeleton cards built in M1.5)

> The Job Scout tab, 5 skeleton cards, filter bar skeleton, and empty state exist from M1.5. This section replaces them with real data.

- [ ] Enable "Scan for Jobs" button (remove `disabled` stub)
- [ ] Wire `GET /api/jobs/matches` → replace skeleton cards with real `<article>` job cards
  - Company name + logo (`<img alt="{company} logo" width="32" height="32" loading="lazy" />`)
  - Role title, match score badge (colour system inherited from M1.5 shell)
  - Skill chips: required skills, missing skills in red/amber
  - "View Details" accordion → full JD text
  - "Generate Tailored Resume" button → passes `jobId` to Apply tab (M5 wires the actual call)
- [ ] Wire filter bar: role category, minimum match %, date posted — update URL via `searchParams`
- [ ] Wire sort: match score (default), date, company — also URL-synced
- [ ] Replace skeleton with real loading state (keep same skeleton component, just conditionally rendered)

---

## Verification Checklist

- [ ] Scraper runs → jobs appear in DynamoDB with structured data
- [ ] JD analysis extracts skills, category, keywords correctly
- [ ] Match scores correlate with actual skill overlap (not random)
- [ ] Job board shows ranked list with match percentages
- [ ] Filtering and sorting work
- [ ] "Generate Tailored Resume" button is visible (functionality in M5)

---

## Notes

- **Pre-populate jobs on March 6.** Don't rely on live scraping during the demo — jobspy can be rate-limited.
- Cache 50+ jobs in DynamoDB so the job board looks full during the presentation.
- Match scoring doesn't need to be perfect — a reasonable ranking that "makes sense" to judges is sufficient.
- Lambda deployment is nice-to-have. If time is tight, use APScheduler in FastAPI instead.
