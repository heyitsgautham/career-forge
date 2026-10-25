import type { Job } from '@/lib/api';
import { ROWS_PER_PAGE, type SourceFilter } from './constants';

export interface JobFilters {
  source: SourceFilter;
  category: string;
  query: string;
}

/**
 * Narrows the job list by source, then category, then free text.
 * A category matches the job's category, its title or its required skills.
 * Free text matches the title, company or location. All matching ignores case.
 */
export function filterJobs(jobs: Job[], { source, category, query }: JobFilters): Job[] {
  let list = jobs;

  if (source !== 'All') {
    list = list.filter((j) => (j.source || '').toLowerCase() === source);
  }

  if (category !== 'All') {
    const cat = category.toLowerCase();
    list = list.filter((j) => {
      const jobCategory = (j.category || '').toLowerCase();
      const title = (j.title || '').toLowerCase();
      const skills = (j.requiredSkills || []).join(' ').toLowerCase();
      return jobCategory.includes(cat) || title.includes(cat) || skills.includes(cat);
    });
  }

  if (query.trim()) {
    const q = query.toLowerCase();
    list = list.filter(
      (j) =>
        (j.title || '').toLowerCase().includes(q) ||
        (j.company || '').toLowerCase().includes(q) ||
        (j.location || '').toLowerCase().includes(q)
    );
  }

  return list;
}

/** Number of table pages for a list, never less than one. */
export function pageCount(total: number, perPage = ROWS_PER_PAGE): number {
  return Math.max(1, Math.ceil(total / perPage));
}

/** The rows shown on a zero-based page. */
export function pageSlice<T>(items: T[], page: number, perPage = ROWS_PER_PAGE): T[] {
  return items.slice(page * perPage, (page + 1) * perPage);
}
