# M5 — Tailored Resumes & Application Tracker

> **Dependencies:** M2 (Resume Generator working) + M4 (Job Scout with JD data) + M1.5 (Apply & Track tab with Kanban columns + tailored resume panel already built)
> **Unlocks:** M6 (Deploy & Polish)
> **Cannot parallelize:** Requires both the base resume pipeline AND job data to exist
> **Estimated effort:** 3–4 hours (frontend now ~1.5 hrs — Apply shell, Kanban columns, modal, and DnD scaffold already exist)
> **Target:** March 6

---

## Goal

For each specific job, generate a unique, JD-tailored resume that differs from the base resume — reordering skills, tweaking bullet points, and injecting ATS keywords. Track all applications in a Kanban-style dashboard.

---

## Tasks

### 5.1 — Resume Tailor Agent

- [x] Create `app/services/resume_tailor.py`
- [x] Input: base resume data (from M2) + specific JD analysis (from M4)
- [x] Claude prompt strategy:
  > "You have the user's base resume data and a target job description. Rewrite the resume to maximise ATS match for this specific role: 1) Reorder skills to lead with JD-required ones, 2) Rewrite project bullets to emphasise JD keywords, 3) Adjust the professional summary to target this role. Only use real project data — never fabricate. Output valid LaTeX using Jake's Resume template."
- [x] Key difference from base resume:
  - Skills section reordered (JD-required skills first)
  - Project bullets rewritten to embed JD keywords naturally
  - Project selection may change (different top 3 projects for different JDs)
  - Summary/objective line tailored to specific role
- [x] Test: base resume for "Backend SDE" vs. tailored for "ML Engineer" → visible differences in skill order + bullet wording

### 5.2 — Tailor + Compile Pipeline

- [x] Wire into existing LaTeX compilation pipeline (from M2):
  1. Resume tailor agent generates `.tex` string
  2. POST to ytotech → PDF bytes
  3. Upload to S3: `{userId}/tailored/{jobId}.pdf`
  4. Store in DynamoDB `Resumes` table with `jobId` reference
- [x] Link resume to job: `Resumes` table record includes `jobId` and `type: "tailored"`
- [x] Return presigned URL to frontend

### 5.3 — Tailor API Endpoints

- [x] `POST /api/resumes/tailor` — generate tailored resume for a specific job
  - Input: `{ userId, jobId }`
  - Output: `{ resumeId, pdfUrl, texUrl, jobId, matchKeywords: [...] }`
- [x] `GET /api/resumes/job/{jobId}` — fetch the tailored resume for a specific job
- [x] Response should include diff summary: what changed from base resume
  - e.g., `{ skillsReordered: true, projectsChanged: ["proj-A → proj-C"], keywordsInjected: ["Docker", "Kubernetes"] }`

### 5.4 — Application Tracker Data Model

- [x] DynamoDB `Applications` table schema:
  ```json
  {
    "userId": "github-123",
    "applicationId": "app-uuid",
    "jobId": "job-uuid",
    "companyName": "Stripe",
    "roleTitle": "Backend SDE",
    "resumeId": "resume-uuid",
    "status": "applied",
    "appliedAt": "2026-03-07T10:30:00Z",
    "updatedAt": "2026-03-07T10:30:00Z",
    "notes": ""
  }
  ```
- [x] Status values: `saved` → `applied` → `viewed` → `interviewing` → `offered` → `rejected`
- [x] Status is manually updated by user (no portal scraping — unreliable)

### 5.5 — Application Tracker API Endpoints

- [x] `POST /api/applications` — create application record (auto-created when tailored resume is generated)
  - Input: `{ userId, jobId, resumeId }`
- [x] `GET /api/applications/user/{userId}` — list all applications for user
  - Supports `?status=applied` filter
- [x] `PATCH /api/applications/{applicationId}` — update status / notes
  - Input: `{ status, notes }`
- [x] `DELETE /api/applications/{applicationId}` — remove application
- [x] `GET /api/applications/stats/{userId}` — summary counts per status

### 5.6 — Frontend: Wire Tailored Resume Flow (Panel built in M1.5)

> The Apply tab's two-panel layout and tailored resume textarea exist from M1.5. This section wires the real API call.

- [x] Enable "Generate Tailored Resume" button (remove `disabled` stub)
- [x] Wire `POST /api/resumes/tailor` with `{ jobId, userId }` — show loading state "Tailoring resume…"
- [x] On success: replace textarea panel with PDF iframe preview (same component as M2)
- [x] "Apply" button below preview → calls `POST /api/applications` → creates application record → triggers Kanban card creation
- [x] Download tailored PDF: `<a download>` with filename `resume-{company}-{date}.pdf`
- [x] Optional (time permitting): side-by-side base vs. tailored diff view

### 5.7 — Frontend: Wire Application Tracker Kanban (Columns + modal built in M1.5)

> Kanban columns (Applied, Interviewing, Offer, Rejected), the Add Application modal, and DnD data-attributes exist from M1.5. This section adds real data + drag-and-drop behaviour.

- [x] Wire `GET /api/applications/user/{userId}` → populate cards into correct columns on mount
- [x] Wire `@hello-pangea/dnd` (already installed in M1.5) — enable drag between columns
- [x] On drop: call `PATCH /api/applications/{id}` with new status — optimistic update, rollback on error
- [x] Each card: company, role, applied date, resume link (clickable to PDF in S3)
- [x] Stats bar: "12 Applied · 3 Interviewing · 1 Offer" — derived from card counts, `font-variant-numeric: tabular-nums`
- [x] Wire "Add Application" modal (built in M1.5) → `POST /api/applications` on submit
- [x] Warn before closing modal with dirty fields (`beforeunload` or router guard)

---

## Verification Checklist

- [x] Click "Generate Tailored Resume" on a job → new PDF generated
- [x] Tailored PDF differs from base PDF (different skill order, different bullet wording)
- [x] Application record auto-created in DynamoDB
- [x] Kanban board shows applications with correct statuses
- [x] Status updates persist across page reloads
- [x] Stats bar counts are accurate
- [x] Multiple tailored resumes can coexist for different jobs

---

## Notes

- This milestone **cannot start** until M2 (base resume pipeline) and M4 (job data) are both working.
- The key demo moment: show the base resume, then click "Tailor for [Company]" → watch the PDF change.
- Kanban is the "polish" feature that impresses judges. If drag-and-drop is too complex, use a simple dropdown selector per card.
- Keep application tracking simple — manual status updates only. Automated portal scraping is unreliable and out of scope.
