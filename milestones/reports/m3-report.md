# M3 Report — Skill Gap Analysis + LearnWeave Roadmap

**Status:** Complete
**Date:** March 7, 2026
**Estimated Effort:** 4–5 hours | **Actual:** ~3 hours

---

## Summary

M3 implements the Skill Gap Analysis engine and LearnWeave Roadmap generator. Users select a target career role from 8 predefined options, and the system uses Bedrock Claude to score their GitHub project portfolio against role benchmarks. The result is a visual radar chart, gap breakdown table, and a personalised 4-week learning roadmap.

---

## What Was Built

### Backend

| File | Purpose |
|------|---------|
| `app/data/role_benchmarks.json` | Static JSON with 8 career roles, each with 8 skill domains and proficiency targets (0–100) |
| `app/services/gap_analysis.py` | Skill scoring via Claude, gap computation, overall fit calculation, DynamoDB caching |
| `app/services/roadmap_generator.py` | 4-week project-based roadmap generation via Claude, milestone tracking |
| `app/api/routes/skill_gap.py` | 7 API endpoints for roles, analysis, reports, roadmaps, and milestones |

### Frontend

| File | Purpose |
|------|---------|
| `src/components/dashboard/skill-gap-shell.tsx` | Full rewrite: role picker grid, Recharts `RadarChart`, gap table, roadmap timeline UI |
| `src/lib/api.ts` | Updated API client: replaced stubs with real `skillGapApi` and `roadmapApi` implementations |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/skill-gap/roles` | List 8 career roles with skill domains |
| `POST` | `/api/skill-gap/analyse` | Run Claude-powered gap analysis for user vs. role |
| `GET` | `/api/skill-gap/report` | Fetch cached gap report (optional `?roleId=`) |
| `POST` | `/api/skill-gap/roadmap/generate` | Generate 4-week learning roadmap from gaps |
| `GET` | `/api/skill-gap/roadmap/{id}` | Fetch specific roadmap |
| `GET` | `/api/skill-gap/roadmaps` | List all roadmaps for current user |
| `PATCH` | `/api/skill-gap/roadmap/{id}/milestone/{week}` | Mark a week as complete |

---

## Architecture Decisions

1. **Role benchmarks as static JSON** — simpler than a DynamoDB table, easily versioned in git, no admin UI needed.
2. **Single Claude call for scoring** — sends all project summaries + skill domains in one prompt. Avoids per-domain calls (cost/latency).
3. **Calibrated scoring prompt** — system prompt specifies 0–100 scale with descriptive anchors (20=minimal, 60=intermediate, 80=strong) to prevent score inflation.
4. **Trusted resource domains only** — roadmap prompt restricts Claude to well-known documentation sites to minimise hallucinated URLs.
5. **Recharts over D3** — simpler API, better React integration, animation out-of-the-box.
6. **Timeline UI for roadmap** — vertical timeline with dots, cards, and checkmarks. Collapsible. Progress bar with `font-variant-numeric: tabular-nums`.

---

## DynamoDB Tables Used

| Table | PK | SK | Purpose |
|-------|----|----|---------|
| `SkillGapReports` | `userId` | `reportId` | Cached analysis results |
| `Roadmaps` | `userId` | `roadmapId` | Generated learning roadmaps with milestone tracking |
| `Projects` | `userId` | `projectId` | Read-only — source of user's GitHub projects for scoring |

---

## Frontend Features

- **Role Picker**: 2x4 card grid with Lucide icons, selected state with ring highlight
- **Radar Chart**: Recharts `RadarChart` with dual overlays (user=blue, benchmark=orange dashed), 800ms animation
- **Overall Fit**: Large percentage display + progress bar + project count
- **Gap Table**: Domain | Your Score | Required | Gap | Priority — with colour-coded badges
- **Priority Badges**: Red/amber/green following existing M1.5 match-score colour system
- **Roadmap Timeline**: Vertical timeline with week dots, project cards, tech stack chips, resource links
- **Milestone Tracking**: "Mark Complete" button → green checkmark + strikethrough → DynamoDB persisted
- **Progress Bar**: "X of 4 weeks completed — Y%" with tabular-nums
- **Collapsible**: Roadmap section toggles with chevron button
- **Accessibility**: `aria-label` on chart, `rel="noopener noreferrer"` on links, semantic structure

---

## Verification

- [x] 8 career roles load from JSON and display in picker grid
- [x] Backend imports clean — `gap_analysis.py`, `roadmap_generator.py`, `skill_gap.py` all load
- [x] 7 API routes registered under `/api/skill-gap/*`
- [x] Frontend compiles with zero TypeScript errors
- [x] Recharts radar chart renders with dual overlay and animation
- [x] Gap table shows Domain/Score/Required/Gap/Priority columns
- [x] Overall fit percentage uses `tabular-nums`
- [x] Roadmap generates via Claude with 4 weeks, tech stacks, and resource links
- [x] Milestone completion updates DynamoDB and UI state
- [x] All milestone checkboxes in M3 spec ticked

---

## Dependencies Added

- `recharts` — frontend charting library for RadarChart (npm)

No new backend dependencies required (uses existing `boto3`, `structlog`, `bedrock_client`).
