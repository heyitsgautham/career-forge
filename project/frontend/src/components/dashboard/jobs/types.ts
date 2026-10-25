/** A saved job description from GET /api/jobs. */
export interface JobDescription {
  id: string;
  title: string;
  company: string;
  raw_text: string;
  source_url?: string;
  required_skills: string[];
  preferred_skills: string[];
  keywords: string[];
  is_analyzed: boolean;
  created_at: string;
}
