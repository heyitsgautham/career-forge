# M5 — Tailored Resumes & Application Tracker — Implementation Report

**Status:** ✅ Complete  
**Date:** March 7, 2026  
**Milestone:** [M5-tailored-apply.md](../M5-tailored-apply.md)  
**Depends on:** M2 (Resume Generator), M4 (Job Scout), M1.5 (Frontend shell)  
**Unlocks:** M6 (Deploy & Polish)

---

## Summary

Implemented the full Tailored Resume + Application Tracker pipeline: a Bedrock-powered resume tailoring agent that rewrites resumes to maximize ATS match for specific jobs, a complete application tracking system with DynamoDB persistence, 7 new REST endpoints, and a fully-wired frontend with Kanban drag-and-drop, tailored resume preview panel, and stats bar.

---

## Tasks Completed

### 5.1 — Resume Tailor Agent

| Item | File | Status |
|------|------|--------|
| `tailor_resume_for_job()` function | `app/services/resume_tailor.py` | ✅ |
| Tailored system prompt with JD-specific strategy | `resume_tailor.py` | ✅ |
| Skills reordering (JD-required first) | `resume_tailor.py` | ✅ |
| Project selection changed per JD | `resume_tailor.py` | ✅ |
| Bullet rewriting with ATS keyword injection | `resume_tailor.py` | ✅ |
| Diff summary extraction (what changed) | `resume_tailor.py` | ✅ |
| Reuses `_fill_jakes_template()` from M2 | `resume_tailor.py` | ✅ |

### 5.2 — Tailor + Compile Pipeline

| Item | File | Status |
|------|------|--------|
| LaTeX generation via `_fill_jakes_template()` | `resume_tailor.py` | ✅ |
| Compilation via `latex_service.compile_latex()` | `resume_tailor.py` | ✅ |
| S3 upload: `{userId}/tailored/{jobId}.pdf/.tex` | `resume_tailor.py` | ✅ |
| DynamoDB `Resumes` table with `jobId` + `type: "tailored"` | `resume_tailor.py` | ✅ |
| Presigned URL generation for frontend | `resume_tailor.py` | ✅ |
| Compilation error handling with graceful fallback | `resume_tailor.py` | ✅ |

### 5.3 — Tailor API Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/resumes/tailor` | POST | Generate tailored resume for a job | ✅ |
| `/api/resumes/job/{jobId}` | GET | Fetch existing tailored resume for a job | ✅ |

Response includes `diffSummary` with `skillsReordered`, `projectsChanged`, `keywordsInjected`, `bulletsRewritten`, `sectionsModified` fields.

### 5.4 — Application Tracker Data Model

| Item | Status |
|------|--------|
| DynamoDB `Applications` table (PK: userId, SK: applicationId) | ✅ (already existed) |
| Schema: jobId, companyName, roleTitle, resumeId, status, appliedAt, updatedAt, notes, url | ✅ |
| Status enum: saved → applied → viewed → interviewing → offered → rejected | ✅ |
| Manual status updates only (no portal scraping) | ✅ |

### 5.5 — Application Tracker API Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/applications` | POST | Create application record | ✅ |
| `/api/applications/user/{userId}` | GET | List all applications (with `?status_filter=`) | ✅ |
| `/api/applications/{applicationId}` | PATCH | Update status / notes | ✅ |
| `/api/applications/{applicationId}` | DELETE | Remove application | ✅ |
| `/api/applications/stats/{userId}` | GET | Summary counts per status | ✅ |

Security: ownership validation on all endpoints — users can only access their own applications.

### 5.6 — Frontend: Wire Tailored Resume Flow

| Item | File | Status |
|------|------|--------|
| Job selector dropdown (from Job Scout data) | `apply-shell.tsx` | ✅ |
| "Generate Tailored Resume" button with loading state | `apply-shell.tsx` | ✅ |
| PDF iframe preview on success | `apply-shell.tsx` | ✅ |
| Diff summary badges (skills reordered, bullets rewritten) | `apply-shell.tsx` | ✅ |
| Injected keywords display | `apply-shell.tsx` | ✅ |
| Download tailored PDF: `resume-{company}-{date}.pdf` | `apply-shell.tsx` | ✅ |
| "Tailor Another" reset flow | `apply-shell.tsx` | ✅ |
| Job Scout "Tailored Resume" button wired to `tailorApi` | `job-scout-shell.tsx` | ✅ |

### 5.7 — Frontend: Wire Application Tracker Kanban

| Item | File | Status |
|------|------|--------|
| `GET /api/applications/user/{userId}` on mount | `apply-shell.tsx` | ✅ |
| `@hello-pangea/dnd` installed and wired | `apply-shell.tsx` | ✅ |
| Drag-and-drop between columns (Applied, Interviewing, Offer, Rejected) | `apply-shell.tsx` | ✅ |
| Optimistic update on drop → `PATCH` API call → rollback on error | `apply-shell.tsx` | ✅ |
| Application cards: company, role, date, resume link | `apply-shell.tsx` | ✅ |
| Stats bar: "{n} Applied · {n} Interviewing · {n} Offer" with `tabular-nums` | `apply-shell.tsx` | ✅ |
| "Add Application" modal with job selector + form | `apply-shell.tsx` | ✅ |
| Dirty field warning on modal close | `apply-shell.tsx` | ✅ |
| Delete application from cards | `apply-shell.tsx` | ✅ |

---

## Files Changed / Created

### Backend (3 files)

| File | Action | Description |
|------|--------|-------------|
| `app/services/resume_tailor.py` | **Created** | Resume tailoring service with Bedrock AI |
| `app/api/routes/applications.py` | **Created** | 7 endpoints: 2 tailor + 5 application CRUD |
| `app/main.py` | **Modified** | Added `applications` router import + mount |

### Frontend (3 files)

| File | Action | Description |
|------|--------|-------------|
| `src/components/dashboard/apply-shell.tsx` | **Rewritten** | Full Kanban + tailor panel (was placeholder) |
| `src/components/dashboard/job-scout-shell.tsx` | **Modified** | Wired "Tailored Resume" button with `tailorApi` |
| `src/lib/api.ts` | **Modified** | Added `tailorApi`, `applicationsApi` (real), `TailorResponse`, `ApplicationStats` types |

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `@hello-pangea/dnd` | latest | Kanban drag-and-drop |

---

## Architecture

```
User clicks "Generate Tailored Resume"
  ├─ Frontend: POST /api/resumes/tailor { jobId }
  ├─ Backend: Fetch job from Jobs table (M4 data)
  ├─ Backend: Fetch project summaries from S3 (M2 data)
  ├─ Backend: Build tailoring prompt with JD analysis + user profile
  ├─ Backend: Bedrock AI generates tailored resume JSON
  │   ├─ Skills reordered for this specific JD
  │   ├─ Projects re-selected for relevance
  │   └─ Bullets rewritten with ATS keywords
  ├─ Backend: _fill_jakes_template() → LaTeX string
  ├─ Backend: latex_service.compile_latex() → PDF
  ├─ Backend: S3 upload: {userId}/tailored/{jobId}.pdf
  ├─ Backend: DynamoDB Resumes table: type="tailored", jobId ref
  └─ Frontend: PDF iframe preview + diff summary + download link

User drags Kanban card
  ├─ Frontend: Optimistic cache update (instant visual feedback)
  ├─ Frontend: PATCH /api/applications/{id} { status: "interviewing" }
  └─ Backend: DynamoDB Applications table update
      └─ On error: Frontend rollback + refetch + error toast
```

---

## Verification

| Check | Status |
|-------|--------|
| "Generate Tailored Resume" button produces new PDF | ✅ |
| Tailored resume differs from base (skill order, bullets) | ✅ |
| Application records stored in DynamoDB | ✅ |
| Kanban columns populate from API data | ✅ |
| Drag-and-drop persists status changes | ✅ |
| Stats bar shows accurate counts | ✅ |
| Multiple tailored resumes coexist per user | ✅ |
| Backend imports: all 3 new/modified files verified | ✅ |
| Frontend: zero TypeScript errors in all 3 files | ✅ |
| 76 total routes registered in FastAPI app | ✅ |

---

## Notes

- The tailoring agent uses the same `_fill_jakes_template()` as M2, ensuring consistent LaTeX output format.
- S3 key structure: base resumes at `{userId}/resumes/`, tailored at `{userId}/tailored/{jobId}.pdf` — clean separation.
- The Kanban uses optimistic updates for instant drag feedback, with automatic rollback on API failure.
- Application status enum supports 6 states, but the Kanban UI shows 4 columns (saved/viewed map to "applied").
- The "Tailored Resume" button also works from the Job Scout tab for quick access.
