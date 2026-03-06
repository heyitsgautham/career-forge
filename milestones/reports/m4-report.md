# M4 — Job Scout (Scrape & Match) — Implementation Report

**Status:** ✅ Complete  
**Date:** March 6, 2026  
**Milestone:** [M4-job-scout.md](../M4-job-scout.md)  
**Depends on:** M1 (Bedrock client + DynamoDB), M1.5 (Frontend shell with Job Scout tab)  
**Unlocks:** M5 (Tailored Resumes & Apply)

---

## Summary

Implemented the full Job Scout pipeline: a job scraper that fetches listings via `jobspy` (with mock fallback for demo), AI-powered JD analysis using AWS Bedrock, a weighted match scoring engine combining vector similarity and keyword overlap, 5 new REST endpoints, and a fully-wired frontend with filter/sort controls and real job cards replacing skeleton placeholders.

---

## Tasks Completed

### 4.1 — Port Job Scraper to AWS

| Item | File | Status |
|------|------|--------|
| `JobScraper` class with `jobspy` integration | `app/services/job_scraper.py` | ✅ |
| No Firestore/GCP imports — all DynamoDB | `job_scraper.py` | ✅ |
| `jobspy` optional: auto-falls back to mock data | `job_scraper.py` | ✅ |
| DynamoDB `Jobs` table writes via `dynamo_service` | `job_scraper.py` | ✅ |
| Configurable: sites, location, results_wanted | `job_scraper.py` | ✅ |
| 12 realistic mock jobs for demo (pre-populated) | `job_scraper.py` | ✅ |
| `scrape_and_store()` — full scrape → store pipeline | `job_scraper.py` | ✅ |

### 4.2 — JD Analysis with Bedrock

| Item | File | Status |
|------|------|--------|
| `JDAnalyzer` class using `bedrock_client.generate_json()` | `app/services/jd_analyzer.py` | ✅ |
| Extracts: category, requiredSkills, experienceLevel, salary, atsKeywords, isPaid | `jd_analyzer.py` | ✅ |
| Batch analysis with concurrency control (semaphore=3) | `jd_analyzer.py` | ✅ |
| Fallback keyword-based analysis when AI fails | `jd_analyzer.py` | ✅ |
| `analyze_and_store()` — analyze → update DynamoDB | `jd_analyzer.py` | ✅ |

### 4.3 — Match Scoring Engine

| Item | File | Status |
|------|------|--------|
| `MatchScorer` class with `compute_match()` | `app/services/match_scorer.py` | ✅ |
| Vector similarity via Titan embeddings (55% weight) | `match_scorer.py` | ✅ |
| Keyword overlap with partial matching (45% weight) | `match_scorer.py` | ✅ |
| Cosine similarity calculation (pure Python) | `match_scorer.py` | ✅ |
| `score_all_jobs()` — bulk scoring + DynamoDB persist | `match_scorer.py` | ✅ |
| `JobMatchScore` dataclass with matched/missing skills | `match_scorer.py` | ✅ |
| Human-readable match explanations | `match_scorer.py` | ✅ |

### 4.4 — Lambda Deployment (Skipped — Fallback Used)

| Item | Status |
|------|--------|
| Lambda packaging | ⬜ Skipped |
| EventBridge rule | ⬜ Skipped |
| IAM role | ⬜ Skipped |
| **Fallback:** Scraper runs in FastAPI via `POST /api/jobs/scrape` | ✅ |

### 4.5 — Job Scout API Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/jobs/scrape` | POST | Trigger manual scrape + analyze + score | ✅ |
| `/api/jobs/matches` | GET | List all jobs sorted by match score | ✅ |
| `/api/jobs/stats` | GET | Summary stats (total, avg match, categories) | ✅ |
| `/api/jobs/scout/{jobId}` | GET | Full job detail + match breakdown | ✅ |
| `/api/jobs/scout/{jobId}` | DELETE | Remove a scraped job | ✅ |

Query params on `/matches`: `?role=`, `?minMatch=`, `?sortBy=`, `?limit=`

### 4.6 — Frontend: Wire Job Scout Tab

| Item | File | Status |
|------|------|--------|
| "Scan Jobs" button enabled with modal dialog | `job-scout-shell.tsx` | ✅ |
| Real `<article>` job cards with company, location, skills | `job-scout-shell.tsx` | ✅ |
| Match score badge (green/amber/red colour system) | `job-scout-shell.tsx` | ✅ |
| Skill chips: matched (green), missing (amber/red) | `job-scout-shell.tsx` | ✅ |
| "View Details" accordion → full JD text + ATS keywords | `job-scout-shell.tsx` | ✅ |
| "Generate Tailored Resume" button (visible, wired in M5) | `job-scout-shell.tsx` | ✅ |
| Filter bar: role category, min match %, sort order | `job-scout-shell.tsx` | ✅ |
| Skeleton → real loading state (conditionally rendered) | `job-scout-shell.tsx` | ✅ |
| Stats bar (jobs count, analyzed, avg match, categories) | `job-scout-shell.tsx` | ✅ |
| Delete job action | `job-scout-shell.tsx` | ✅ |
| `jobMatchApi` wired (replaces stubs) | `api.ts` | ✅ |
| `Job` interface updated with all new fields | `api.ts` | ✅ |

---

## Verification Checklist

| Check | Status |
|-------|--------|
| Scraper runs → jobs appear in DynamoDB with structured data | ✅ |
| JD analysis extracts skills, category, keywords correctly | ✅ |
| Match scores correlate with actual skill overlap (not random) | ✅ |
| Job board shows ranked list with match percentages | ✅ |
| Filtering and sorting work | ✅ |
| "Generate Tailored Resume" button is visible (M5 wires it) | ✅ |

---

## Architecture

```
User clicks "Scan Jobs"
        │
        ▼
POST /api/jobs/scrape
        │
        ├─► JobScraper.scrape_and_store()
        │       └─► jobspy (or mock fallback) → DynamoDB Jobs table
        │
        ├─► JDAnalyzer.analyze_and_store()
        │       └─► Bedrock generate_json() → structured fields → DynamoDB update
        │
        └─► MatchScorer.score_all_jobs()
                └─► Titan embeddings + keyword overlap → matchScore → DynamoDB update
                        │
                        ▼
               GET /api/jobs/matches → Frontend renders cards
```

---

## Files Changed / Created

### New Files
- `project/backend/app/services/job_scraper.py` — Job scraping service
- `project/backend/app/services/jd_analyzer.py` — AI JD analysis service
- `project/backend/app/services/match_scorer.py` — Match scoring engine

### Modified Files
- `project/backend/app/api/routes/jobs.py` — Added 5 new Job Scout endpoints
- `project/frontend/src/components/dashboard/job-scout-shell.tsx` — Full rewrite with real data
- `project/frontend/src/lib/api.ts` — Updated `Job` interface + wired `jobMatchApi`

---

## Design Decisions

1. **jobspy fallback:** If `jobspy` is not installed, the scraper generates 12 realistic mock jobs. This ensures the demo always works even if jobspy gets rate-limited.
2. **Scoring weights:** 55% vector similarity + 45% keyword overlap. Vector catches semantic similarity (e.g., "API development" matches "REST API design"), keyword catches exact skill matches.
3. **No Lambda:** Used FastAPI endpoint (`POST /scrape`) instead of Lambda for simplicity. Lambda can be added post-hackathon.
4. **Partial skill matching:** The keyword scorer checks partial matches (e.g., user has "React" → matches "React.js" in JD), preventing false negatives.
5. **Concurrent analysis:** JD analysis uses `asyncio.Semaphore(3)` to limit concurrent Bedrock calls and avoid throttling.

---

## Notes

- Mock jobs cover Backend, Frontend, Full Stack, DevOps, ML, Data, and Cloud roles
- Match insights show in expandable card (explanation, ATS keywords, full JD)
- "Tailored Resume" button is visible but action is deferred to M5
