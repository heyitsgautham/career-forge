/** A project as returned by GET /api/projects. */
export interface Project {
  id: string;
  title: string;
  description: string;
  technologies: string[];
  url?: string;
  highlights: string[];
  is_private?: boolean;
  source_type?: string;
  start_date?: string;
  end_date?: string;
  created_at: string;
}

/** One repository in an in-flight GitHub import, shown by the progress banner and skeleton cards. */
export type ImportProgressItem = {
  name: string;
  fullName: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
};
