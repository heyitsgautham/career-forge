# M6 — Deploy, Polish & Demo

> **Dependencies:** M2 + M3 + M4 + M5 (all features complete)
> **Unlocks:** Hackathon submission
> **Estimated effort:** 4–6 hours
> **Target:** March 7 (Hackathon Day 1) – March 8 morning

---

## Goal

Deploy the full stack to AWS, stress-test the demo flow, polish the UI, and prepare the submission package. Everything must work live on a public URL.

---

## Tasks

### 6.1 — Backend Deployment (EC2)

- [ ] Launch EC2 `t3.micro` in us-east-1 (free tier)
- [ ] Security group: open ports 22 (SSH), 8000 (API), 443 (HTTPS optional)
- [ ] Attach IAM role with policies: Bedrock, S3, DynamoDB, Lambda (NO hardcoded keys on EC2)
- [ ] SSH in and setup:
  ```bash
  sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx git
  git clone <repo-url> /home/ubuntu/careerforge
  cd /home/ubuntu/careerforge/project/backend
  python3.11 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  ```
- [ ] Run with process manager:
  ```bash
  pip install pm2  # or use systemd service
  pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000" --name careerforge-api
  ```
- [ ] Configure Nginx reverse proxy:
  ```nginx
  server {
      listen 80;
      location / {
          proxy_pass http://127.0.0.1:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }
  }
  ```
- [ ] Verify: `curl http://<ec2-public-ip>/api/health` → `200 OK`

### 6.2 — Frontend Deployment (Amplify)

- [ ] Push frontend code to GitHub (if not already)
- [ ] Connect repo to AWS Amplify:
  - Framework: Next.js
  - Build command: `npm run build`
  - Output dir: `.next`
- [ ] Set environment variable: `NEXT_PUBLIC_API_URL=http://<ec2-public-ip>`
- [ ] Trigger deploy → wait for build
- [ ] Verify: open Amplify URL → app loads → login works
- [ ] Note the Amplify URL for submission

### 6.3 — End-to-End Smoke Test

Run through the complete demo flow on the deployed environment:

- [ ] GitHub OAuth login works on Amplify URL
- [ ] Repos fetched → skill profile generated
- [ ] Base resume generates → PDF downloadable from S3
- [ ] Role selection → radar chart renders with live data
- [ ] LearnWeave roadmap generates → milestones toggleable
- [ ] Job Scout shows pre-populated jobs with match scores
- [ ] Tailored resume generates → differs from base resume
- [ ] Application tracker updates and persists

### 6.4 — UI Polish

- [ ] Loading skeletons for all AI-generated content (Bedrock calls take 3–8s)
- [ ] Error states: friendly messages, not blank screens or raw errors
- [ ] Add "Powered by Amazon Bedrock" badge on resume generator
- [ ] Career role selection: icons + clean card layout
- [ ] Radar chart: smooth animation on render
- [ ] Mobile responsive check (judges may use phones)
- [ ] Consistent colour scheme and typography across all pages
- [ ] Navigation: clear tab/sidebar for: Dashboard → Resume → Skill Gap → LearnWeave → Jobs → Applications

### 6.5 — Pre-populate Demo Data

- [ ] Run job scraper to load 50+ jobs into DynamoDB
- [ ] Generate 2–3 sample resumes for demo GitHub account
- [ ] Create sample application records in various statuses for Kanban demo
- [ ] Pre-compute gap analysis for at least 2 roles
- [ ] Pre-generate at least 1 LearnWeave roadmap
- [ ] **Backup:** Screenshot every screen in case live demo fails

### 6.6 — Architecture Diagram & Submission

- [ ] Take screenshots of `career-architecture.html` for presentation slides
- [ ] Annotate which AWS service handles each phase
- [ ] Prepare AWS cost breakdown slide:
  | Service | Estimated Cost |
  |---------|---------------|
  | Bedrock (Claude + Titan) | ~$2.50 |
  | OpenSearch Serverless | ~$2 |
  | DynamoDB | ~$0 |
  | S3 | ~$0.01 |
  | EC2 t3.micro | ~$0 (free tier) |
  | Amplify | ~$0 |
  | Lambda | ~$0 |
  | **Total** | **~$5** |
- [ ] Record 3-minute demo video (backup for submission)
- [ ] File named: `TeamName – UniversityName` (per PS rules)
- [ ] Submission includes: Amplify URL, GitHub repo, architecture diagram, demo video

### 6.7 — Demo Script Rehearsal

| Time      | Action                                                | What Judges See                     |
|-----------|-------------------------------------------------------|-------------------------------------|
| 0:00–0:20 | Open app → GitHub OAuth login                          | Clean login flow, "Connecting…"     |
| 0:20–0:50 | Skill profile loads                                    | Tech stack extracted from real repos|
| 0:50–1:20 | Select "Backend SDE" → gap analysis                    | Animated radar chart + gap table    |
| 1:20–1:50 | Generate base resume → PDF opens                       | Jake's template, auto-filled        |
| 1:50–2:20 | Job Scout → click job → tailored resume                | Rankings + new PDF differs from base|
| 2:20–2:50 | LearnWeave roadmap + application Kanban                | 4-week plan + tracker dashboard     |
| 2:50–3:00 | Flash AWS console: Bedrock, S3, DynamoDB, Lambda       | Prove real AWS usage                |

- [ ] Rehearse 3 times minimum
- [ ] Time each run — must finish under 3:00
- [ ] Assign speaker roles if team presentation
- [ ] Prepare answers for: "What if GitHub is down?", "How does anti-hallucination work?", "What's the cost at scale?"

---

## Verification Checklist

- [ ] App accessible at public Amplify URL
- [ ] Full flow works end-to-end without errors
- [ ] All 6 AWS services visible in console (Bedrock, S3, DynamoDB, Lambda, EC2, Amplify)
- [ ] Demo completes in under 3 minutes
- [ ] Backup screenshots/video ready
- [ ] Submission file correctly named and formatted

---

## Notes

- **Don't deploy too early.** Finish features (M2–M5) first, then deploy. Deploying half-baked code wastes debugging time.
- EC2 IAM role is critical — never hardcode AWS keys on the server.
- Amplify auto-deploys on push — be careful not to push broken code after the demo URL is live.
- Pre-populating demo data is non-negotiable. Live scraping during the demo is a gamble.
- The 3-minute demo script is your most important preparation. Practice it.
