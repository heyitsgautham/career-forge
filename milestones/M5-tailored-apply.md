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

- [ ] Create `app/services/resume_tailor.py`
- [ ] Input: base resume data (from M2) + specific JD analysis (from M4)
- [ ] Claude prompt strategy:
  > "You have the user's base resume data and a target job description. Rewrite the resume to maximise ATS match for this specific role: 1) Reorder skills to lead with JD-required ones, 2) Rewrite project bullets to emphasise JD keywords, 3) Adjust the professional summary to target this role. Only use real project data — never fabricate. Output valid LaTeX using Jake's Resume template."
- [ ] Key difference from base resume:
  - Skills section reordered (JD-required skills first)
  - Project bullets rewritten to embed JD keywords naturally
  - Project selection may change (different top 3 projects for different JDs)
  - Summary/objective line tailored to specific role
- [ ] Test: base resume for "Backend SDE" vs. tailored for "ML Engineer" → visible differences in skill order + bullet wording

### 5.2 — Tailor + Compile Pipeline

- [ ] Wire into existing LaTeX compilation pipeline (from M2):
  1. Resume tailor agent generates `.tex` string
  2. POST to ytotech → PDF bytes
  3. Upload to S3: `{userId}/tailored/{jobId}.pdf`
  4. Store in DynamoDB `Resumes` table with `jobId` reference
- [ ] Link resume to job: `Resumes` table record includes `jobId` and `type: "tailored"`
- [ ] Return presigned URL to frontend

### 5.3 — Tailor API Endpoints

- [ ] `POST /api/resumes/tailor` — generate tailored resume for a specific job
  - Input: `{ userId, jobId }`
  - Output: `{ resumeId, pdfUrl, texUrl, jobId, matchKeywords: [...] }`
- [ ] `GET /api/resumes/job/{jobId}` — fetch the tailored resume for a specific job
- [ ] Response should include diff summary: what changed from base resume
  - e.g., `{ skillsReordered: true, projectsChanged: ["proj-A → proj-C"], keywordsInjected: ["Docker", "Kubernetes"] }`

### 5.4 — Application Tracker Data Model

- [ ] DynamoDB `Applications` table schema:
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
- [ ] Status values: `saved` → `applied` → `viewed` → `interviewing` → `offered` → `rejected`
- [ ] Status is manually updated by user (no portal scraping — unreliable)

### 5.5 — Application Tracker API Endpoints

- [ ] `POST /api/applications` — create application record (auto-created when tailored resume is generated)
  - Input: `{ userId, jobId, resumeId }`
- [ ] `GET /api/applications/user/{userId}` — list all applications for user
  - Supports `?status=applied` filter
- [ ] `PATCH /api/applications/{applicationId}` — update status / notes
  - Input: `{ status, notes }`
- [ ] `DELETE /api/applications/{applicationId}` — remove application
- [ ] `GET /api/applications/stats/{userId}` — summary counts per status

### 5.6 — Frontend: Wire Tailored Resume Flow (Panel built in M1.5)

> The Apply tab's two-panel layout and tailored resume textarea exist from M1.5. This section wires the real API call.

- [ ] Enable "Generate Tailored Resume" button (remove `disabled` stub)
- [ ] Wire `POST /api/resumes/tailor` with `{ jobId, userId }` — show loading state "Tailoring resume…"
- [ ] On success: replace textarea panel with PDF iframe preview (same component as M2)
- [ ] "Apply" button below preview → calls `POST /api/applications` → creates application record → triggers Kanban card creation
- [ ] Download tailored PDF: `<a download>` with filename `resume-{company}-{date}.pdf`
- [ ] Optional (time permitting): side-by-side base vs. tailored diff view

### 5.7 — Frontend: Wire Application Tracker Kanban (Columns + modal built in M1.5)

> Kanban columns (Applied, Interviewing, Offer, Rejected), the Add Application modal, and DnD data-attributes exist from M1.5. This section adds real data + drag-and-drop behaviour.

- [ ] Wire `GET /api/applications/user/{userId}` → populate cards into correct columns on mount
- [ ] Wire `@hello-pangea/dnd` (already installed in M1.5) — enable drag between columns
- [ ] On drop: call `PATCH /api/applications/{id}` with new status — optimistic update, rollback on error
- [ ] Each card: company, role, applied date, resume link (clickable to PDF in S3)
- [ ] Stats bar: "12 Applied · 3 Interviewing · 1 Offer" — derived from card counts, `font-variant-numeric: tabular-nums`
- [ ] Wire "Add Application" modal (built in M1.5) → `POST /api/applications` on submit
- [ ] Warn before closing modal with dirty fields (`beforeunload` or router guard)

---

## Verification Checklist

- [ ] Click "Generate Tailored Resume" on a job → new PDF generated
- [ ] Tailored PDF differs from base PDF (different skill order, different bullet wording)
- [ ] Application record auto-created in DynamoDB
- [ ] Kanban board shows applications with correct statuses
- [ ] Status updates persist across page reloads
- [ ] Stats bar counts are accurate
- [ ] Multiple tailored resumes can coexist for different jobs

---

## Notes

- This milestone **cannot start** until M2 (base resume pipeline) and M4 (job data) are both working.
- The key demo moment: show the base resume, then click "Tailor for [Company]" → watch the PDF change.
- Kanban is the "polish" feature that impresses judges. If drag-and-drop is too complex, use a simple dropdown selector per card.
- Keep application tracking simple — manual status updates only. Automated portal scraping is unreliable and out of scope.
