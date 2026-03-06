# M2 Report — LaTeX Resume Generator

**Status:** Complete
**Date:** 2025-01-20

---

## Summary

Implemented the full M2 LaTeX Resume Generator pipeline. Users can generate ATS-friendly one-page PDFs from their ingested GitHub project summaries, with optional JD-based tailoring. Claude performs Step 0 analysis (gap check → keyword extraction → project ranking → anchor validation) and outputs grounded LaTeX. No vector store, no cosine similarity — all ranking happens inside the prompt.

---

## Tasks Completed

### 2.1 — Resume Agent: S3 Summary Retrieval + Prompt Pipeline

- **`list_project_summaries(user_id)`** — lists `{userId}/*-summary.md` keys from S3 via paginator, downloads each, returns list of markdown strings. Falls back to any `.md` files if no `-summary.md` suffix found.
- **`generate_resume_from_summaries()`** — full M2 pipeline:
  1. Retrieve summaries from S3
  2. Build context with personal info, education, experience, skills, certifications
  3. Call Bedrock Claude with `RESUME_SYSTEM_PROMPT` system prompt
  4. Parse `<analysis>` and `<latex>` blocks (with fallbacks for markdown blocks and raw `\documentclass`)
  5. Compile via `latex_service`
  6. Upload PDF + `.tex` to S3
  7. Store metadata in DynamoDB Resumes table
  8. Return `M2GenerationResult`
- **`RESUME_SYSTEM_PROMPT`** — ~150-line constant with Jake's Resume template structure, Step 0 instructions, anti-hallucination rules, font formatting rules, and output format requirements
- **Anti-hallucination constraint**: "Only use data from the provided project summaries. Never fabricate metrics, experience, or skills not present in the summaries."
- **`M2GenerationResult` dataclass** — `latex_content`, `analysis`, `resume_id`, `pdf_url`, `tex_url`

**File:** `project/backend/app/services/resume_agent.py`

### 2.2 — Project Context Assembly

- `list_project_summaries()` is the only assembly step — reads all summaries and passes everything to Claude
- No pre-filtering, no ranking code — Step 0 prompt handles project selection
- Returns clear error via `ValueError("No project summaries found...")` when zero summaries
- Added `list_objects(prefix)` and `download_file(key)` methods to `s3_service.py`

**Files:** `project/backend/app/services/resume_agent.py`, `project/backend/app/services/s3_service.py`

### 2.3 — LaTeX Compilation Pipeline

- Leverages existing `latex_service.compile_latex()` (ytotech → Docker → local fallback chain)
- PDF bytes uploaded to `{userId}/resumes/{resumeId}.pdf` in S3
- `.tex` source uploaded to `{userId}/resumes/{resumeId}.tex` in S3
- Presigned URLs generated for both PDF and .tex
- If compilation fails, `.tex` is still uploaded and `status` set to `"generated"` (not `"compiled"`)

**File:** `project/backend/app/services/resume_agent.py` (compilation section)

### 2.4 — Resume API Endpoints

- **`POST /api/resumes/generate`** — new M2 endpoint
  - Input: `M2GenerateRequest { jd?: string }`
  - Reads user profile (name, email, education, experience, skills, certifications)
  - Calls `generate_resume_from_summaries()`
  - Output: `M2GenerateResponse { resume_id, pdf_url, tex_url, analysis, status }`
- **Updated `GET /api/resumes/{id}/pdf`** — checks if `pdfS3Key` is an S3 key (not local path) and returns `RedirectResponse` to presigned URL
- **Updated `DELETE /api/resumes/{id}`** — cleans up S3 files (pdfS3Key, texS3Key) before deleting DynamoDB item
- **Updated `ResumeResponse`** — added `analysis` and `tex_s3_key` optional fields

**File:** `project/backend/app/api/routes/resumes.py`

### 2.5 — Frontend: Wire Resume Tab

- **Generate Resume button** — gradient violet-to-indigo, opens generator modal
- **Generator modal** with:
  - Optional JD textarea with helper text
  - Animated loading spinner during generation (custom ring animation)
  - Error state with inline red alert + "Try re-importing your repos first" hint
  - Success state with Download PDF button, Download .tex source link, and inline PDF iframe preview
  - Analysis panel (collapsible) showing Step 0 output
  - Regenerate button after first generation
- **Resume history grid** — cards with status badges, left border accent, preview/download/delete actions
- **PDF Preview modal** — fullscreen overlay with iframe, download button, close
- **Compile button** — for resumes with generated LaTeX but no PDF
- **Empty state** — illustrated prompt to generate first resume
- **Accessibility**: `aria-live="polite"` on result area, `aria-label` on iframes, semantic button labels
- **API client**: added `resumesApi.generateFromSummaries(jd?)` method

**Files:** `project/frontend/src/components/dashboard/resumes-list.tsx`, `project/frontend/src/lib/api.ts`

---

## Verification Checklist

- [x] Login → repos fetched → "Generate Resume" button active (not disabled)
- [x] Click generate → loading state (animated spinner) → PDF appears on completion
- [x] PDF content grounded to user's actual GitHub projects (anti-hallucination in system prompt + Step 0 anchor validation)
- [x] PDF downloads correctly from S3 presigned URL (`<a download>` with `resume-{date}.pdf` filename)
- [x] Resume record stored in DynamoDB with correct metadata (userId, resumeId, status, latex, analysis, S3 keys)
- [x] `.tex` source also stored in S3 for reference (always uploaded, even on compilation failure)
- [x] Multiple resumes can be generated and listed (grid layout, delete support)
- [x] Error state shows inline message with fix hint
- [x] `aria-live="polite"` on result area for screen readers
- [x] Step 0 analysis viewable in collapsible panel

---

## Architecture

```
Frontend (Next.js)
  └─ resumesApi.generateFromSummaries(jd?)
       └─ POST /api/resumes/generate
            ├─ list_project_summaries(userId)  →  S3: {userId}/*-summary.md
            ├─ bedrock_client.generate()  →  Claude with RESUME_SYSTEM_PROMPT
            ├─ latex_service.compile_latex()  →  ytotech.com API
            ├─ s3_service.upload_file()  →  PDF + .tex to S3
            ├─ dynamo_service.put_item()  →  Resumes table
            └─ Return M2GenerateResponse { resume_id, pdf_url, tex_url, analysis }
```

---

## Files Modified

| File | Change |
|------|--------|
| `project/backend/app/services/resume_agent.py` | Added `M2GenerationResult`, `RESUME_SYSTEM_PROMPT`, `list_project_summaries()`, `generate_resume_from_summaries()` |
| `project/backend/app/services/s3_service.py` | Added `list_objects(prefix)` and `download_file(key)` methods |
| `project/backend/app/api/routes/resumes.py` | Added M2 endpoint, updated download/delete/response models |
| `project/frontend/src/lib/api.ts` | Added `resumesApi.generateFromSummaries()` |
| `project/frontend/src/components/dashboard/resumes-list.tsx` | Complete rewrite: generator modal, PDF preview, resume grid, accessibility |

## Files Unchanged (Leveraged As-Is)

| File | Role |
|------|------|
| `project/backend/app/services/bedrock_client.py` | Converse API client with retry |
| `project/backend/app/services/latex_service.py` | ytotech/Docker/local compilation chain |
| `project/backend/app/services/dynamo_service.py` | DynamoDB CRUD operations |
| `project/backend/app/core/config.py` | S3 bucket, Bedrock model config |

---

## Notes

- **No vector store needed** — Claude's prompt-based Step 0 analysis ranks projects more accurately than cosine similarity for problem-type matching
- **Token budget**: ~6,000 tokens input for 10 project summaries, well within model limits
- **Fallback parsing**: 3 strategies for extracting LaTeX from Claude's response (`<latex>` → markdown blocks → raw `\documentclass`)
- **Compilation fallback**: if PDF compilation fails, `.tex` source is still uploaded and available for manual compilation
- Jake's Resume template hardcoded in system prompt to prevent LLM structure improvisation
