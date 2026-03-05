# M2 — LaTeX Resume Generator

> **Dependencies:** M1 (Bedrock client + S3 + DynamoDB working) + M1.5 (Frontend shell with Resume tab already built) + **M1.6 (GitHub repos ingested into DynamoDB — resume generator needs real project data)**
> **Unlocks:** M5 (Tailored Resumes & Apply)
> **Parallel with:** M3 (Skill Gap), M4 (Job Scout)
> **Estimated effort:** 2–3 hours (frontend now ~1 hr — shell already exists)
> **Target:** March 5 – March 6

---

## Goal

Port the latex-agent resume generation pipeline to AWS. A user can log in, have their GitHub repos analysed, and receive a downloadable one-page LaTeX resume PDF — grounded entirely to their real projects. The resume agent follows the **`new-resume.prompt.md`** pattern: it reads all per-repo summary `.md` files from S3, passes them with the JD to Claude, which autonomously does Step 0 analysis (gap check → JD keyword extraction → project ranking table → anchor validation) and then generates the full LaTeX resume in one call. No semantic search, no Titan embeddings, no vector store.

---

## Tasks

### 2.1 — Resume Agent: S3 Summary Retrieval + Prompt Pipeline

**Pipeline: Read all `{userId}/*-summary.md` from S3 → pass to Claude with `new-resume.prompt.md` system prompt → LaTeX output**

- [ ] Add `app/services/resume_agent.py`:
  1. `list_project_summaries(user_id: str) -> List[str]` — lists all `{userId}/*-summary.md` keys from S3 and downloads their content; returns a list of raw `.md` strings
  2. `generate_resume_latex(user_id: str, jd: Optional[str]) -> str` — assembles the prompt and calls Bedrock Claude:
     ```python
     async def generate_resume_latex(self, user_id: str, jd: Optional[str] = None) -> str:
         summaries = await self.list_project_summaries(user_id)
         if not summaries:
             raise ValueError("No project summaries found. Run GitHub ingestion first.")
         
         # Build context block — all project .md files concatenated with separators
         projects_context = "\n\n---\n\n".join(summaries)
         
         user_message = f"""## Project Summaries (from proj-summary/)\n{projects_context}
     
     ## Job Description\n{jd or 'No JD provided — generate a strong base resume ranking by complexity and recency.'}
     
     Perform Step 0 analysis first (gap check → JD keyword extraction → project ranking table → anchor validation), then generate the complete LaTeX resume."""
         
         response = await bedrock_client.generate_text(
             system=RESUME_SYSTEM_PROMPT,   # contents of new-resume.prompt.md adapted for API
             messages=[{"role": "user", "content": user_message}],
             model="anthropic.claude-3-haiku-20240307-v1:0",
             max_tokens=8192,
             temperature=0.3,
         )
         return response
     ```
- [ ] Store `RESUME_SYSTEM_PROMPT` as a constant in `app/services/resume_agent.py` — this is the `new-resume.prompt.md` content adapted for Bedrock's system parameter (strip the YAML front-matter, keep Step 0 through Output Requirements intact)
- [ ] **Anti-hallucination constraint** must be in the system prompt:
  > "Only use data from the provided project summaries. Never fabricate metrics, experience, or skills not present in the summaries."
- [ ] **Step 0 must execute before LaTeX output** — system prompt must explicitly instruct Claude to output the ranking table and analysis in a `<analysis>` block before the `<latex>` block so the API response can be parsed in two parts
- [ ] Parse response: extract `<analysis>` block (log it for debugging) and `<latex>` block (pass to 2.3 compilation)
- [ ] Test: pass 5 summary `.md` files + a sample JD → receive valid `.tex` string with projects ranked and selected correctly

### 2.2 — Project Context Assembly (replaces matching_engine)

> **No cosine similarity. No Titan embeddings. No `matching_engine.py`.** Project ranking happens inside Claude's Step 0 prompt analysis — it scores every project on Unique JD Requirements, Problem-Type Match, Tech Stack Match, Role Type Match, and Impact Relevance, which is strictly more accurate than vector similarity. Cosine similarity can't detect that a PII detection JD and a generic LMS project share the same tech stack but solve completely different types of problems.

- [ ] `list_project_summaries()` (implemented in 2.1) is the only assembly step needed:
  - List all `{userId}/*-summary.md` keys via `s3_service.list_objects(prefix=f"{user_id}/")`
  - Download each `.md` and return the full list — Claude receives everything and decides what's relevant
- [ ] No pre-filtering, no ranking code — pass all summaries and let the Step 0 prompt do the work
- [ ] If `user_id` has zero summaries in S3, surface a clear API error: `"No projects found. Please run GitHub ingestion first."`
- [ ] Test: call `list_project_summaries(user_id)` for a user with 10 ingested repos → 10 `.md` strings returned, each matching the `academia-sync.md` structure

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
  - Input: `{ userId, jd?: string }` (optional JD; no JD = base resume ranked by complexity/recency)
  - Output: `{ resumeId, pdfUrl, texUrl, analysis: string }` (analysis = Step 0 output block, useful for debugging)
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
- **No vector store needed.** Claude's Step 0 does project selection better than cosine similarity — it catches problem-type matching that embeddings miss (e.g., a PII detection JD + a generic LMS project share tech overlap but solve different problems; Claude catches this, cosine similarity doesn't).
- The `RESUME_SYSTEM_PROMPT` in `resume_agent.py` is the distilled version of `new-resume.prompt.md`. Strip the YAML front-matter and any file-path references (`proj-summary/` folder) since we're injecting summaries directly as context. Keep Step 0 through Output Requirements verbatim.
- Claude 3 Haiku is faster than Gemini for LaTeX generation — expect 3–6 sec for the LLM call with 10+ project summaries in context.
- ytotech is a free service with no SLA. Pre-generate a demo resume and cache it as backup.
- Jake's Resume template must be hardcoded in the system prompt — don't let the LLM improvise the structure.
- **Token budget:** 10 project summaries × ~600 tokens each = ~6,000 tokens input. Well within Haiku's 200K context window. Cost ≈ $0.002 per resume generation.
