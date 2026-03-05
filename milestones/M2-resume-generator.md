# M2 — LaTeX Resume Generator

> **Dependencies:** M1 (Bedrock client + S3 + DynamoDB working) + M1.5 (Frontend shell with Resume tab already built)
> **Unlocks:** M5 (Tailored Resumes & Apply)
> **Parallel with:** M3 (Skill Gap), M4 (Job Scout)
> **Estimated effort:** 3–4 hours (frontend now ~1 hr — shell already exists)
> **Target:** March 5 – March 6

---

## Goal

Port the latex-agent resume generation pipeline to AWS. A user can log in, have their GitHub repos analysed, and receive a downloadable one-page LaTeX resume PDF — grounded entirely to their real projects.

---

## Tasks

### 2.1 — Resume Agent Prompts (port from Gemini to Bedrock)

- [ ] Port `app/services/resume_agent.py` — swap all `gemini_client` calls to `bedrock_client`
- [ ] Verify Claude 3 Haiku generates valid LaTeX with Jake's Resume template structure
- [ ] Tune system prompt for Bedrock Claude format (system message as separate param, not in conversation)
- [ ] Ensure anti-hallucination constraint is in system prompt:
  > "Only use data from the provided project descriptions. Never fabricate experience, skills, or metrics."
- [ ] Test: pass 3 project descriptions → receive valid `.tex` string

### 2.2 — Project Ranking & Selection

- [ ] Port `app/services/matching_engine.py` — project-to-JD relevance ranking
- [ ] Use Bedrock Titan embeddings for similarity computation
- [ ] Given N projects and optional JD keywords → rank projects → select top 3–4
- [ ] If no JD provided (base resume), rank by complexity/recency instead
- [ ] Test: 10 projects + JD → top 3 returned are the most relevant

### 2.3 — LaTeX Compilation Pipeline

- [ ] Keep `latex.ytotech.com` as compiler (already working, no need to change)
- [ ] Update `app/services/latex_service.py`:
  1. Receive `.tex` string from resume agent
  2. POST to ytotech API → receive PDF bytes
  3. Upload PDF to S3 via `s3_service.upload_file()`
  4. Upload `.tex` source to S3 (for re-editing later)
  5. Store resume metadata in DynamoDB `Resumes` table
  6. Return presigned S3 URL to frontend
- [ ] Add fallback: if ytotech is down, return `.tex` file for manual compilation
- [ ] Test: full pipeline → `.tex` generated → compiled → PDF in S3 → URL works

### 2.4 — Resume API Endpoints

- [ ] `POST /api/resumes/generate` — trigger base resume generation
  - Input: `{ userId }` (uses stored profile + projects)
  - Output: `{ resumeId, pdfUrl, texUrl }`
- [ ] `GET /api/resumes/{resumeId}` — fetch resume metadata + download URL
- [ ] `GET /api/resumes/user/{userId}` — list all resumes for a user
- [ ] `DELETE /api/resumes/{resumeId}` — delete resume + S3 files
- [ ] All endpoints use DynamoDB for metadata, S3 for files

### 2.5 — Frontend: Wire Resume Tab (Shell built in M1.5)

> The Resume Generator tab, loading skeleton, and empty state already exist from M1.5. This section only wires real data.

- [ ] Enable the "Generate Resume" button (remove `disabled` + tooltip stub)
- [ ] Wire `POST /api/resumes/generate` — on click: show skeleton → on success: replace with real PDF iframe
- [ ] Wire `GET /api/resumes/user/{userId}` — replace placeholder list with real resume history
- [ ] PDF preview: `<iframe src={pdfUrl} title="Generated resume preview" />` with `aria-label`
- [ ] Download button: presigned S3 URL, `<a download>` with filename `resume-{date}.pdf`
- [ ] Error state: inline error message below button (not toast), includes fix hint: "Try re-importing your repos first"
- [ ] `aria-live="polite"` on result area so screen readers announce PDF ready

---

## Verification Checklist

- [ ] Login → repos fetched → "Generate Resume" button active
- [ ] Click generate → loading state → PDF appears in < 15 seconds
- [ ] PDF content matches user's actual GitHub projects (no hallucination)
- [ ] PDF downloads correctly from S3 presigned URL
- [ ] Resume record exists in DynamoDB with correct metadata
- [ ] `.tex` source also stored in S3 for reference
- [ ] Multiple resumes can be generated and listed

---

## Notes

- This is the **hero feature** for the demo. Invest in making it bulletproof.
- Claude 3 Haiku is faster than Gemini for LaTeX generation — expect 2–4 sec for the LLM call.
- ytotech is a free service with no SLA. Pre-generate a demo resume and cache it as backup.
- Jake's Resume template must be hardcoded in the prompt — don't let the LLM improvise the structure.
