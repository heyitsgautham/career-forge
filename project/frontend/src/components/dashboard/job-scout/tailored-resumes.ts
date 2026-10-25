export interface ResumeSummary {
  id: string;
  job_id?: string;
  type?: string;
}

/**
 * Maps job id to the tailored resume made for it.
 *
 * `fresh` holds resumes generated this session that the resume list may not
 * show yet. A fresh entry is kept only while its resume still exists, or while
 * the resume list is still empty because it has not loaded.
 */
export function tailoredResumeMap(
  resumes: ResumeSummary[],
  fresh: Record<string, string>
): Record<string, string> {
  const map: Record<string, string> = {};
  const existingResumeIds = new Set(resumes.map((r) => r.id));
  for (const r of resumes) {
    if (r.type === 'tailored' && r.job_id) {
      map[r.job_id] = r.id;
    }
  }
  for (const [jobId, resumeId] of Object.entries(fresh)) {
    if (existingResumeIds.has(resumeId) || !resumes.length) {
      map[jobId] = resumeId;
    }
  }
  return map;
}
