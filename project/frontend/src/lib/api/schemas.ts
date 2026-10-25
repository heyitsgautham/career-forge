/**
 * Runtime checks for the API responses the dashboard renders.
 *
 * TypeScript types vanish at runtime, so a backend change that renames or
 * drops a field used to surface as a blank card or a crash deep in a
 * component. Each schema here pins the fields the UI depends on, and lets
 * through any extra fields the backend adds.
 */
import type { AxiosResponse } from 'axios';
import { z } from 'zod';

const text = z.string().nullish();
const textList = z.array(z.string());

export const ProjectSchema = z.looseObject({
  id: z.string(),
  title: z.string(),
  description: text,
  technologies: textList,
  highlights: textList,
  url: text,
  source_type: text,
  is_private: z.boolean().nullish(),
  start_date: text,
  end_date: text,
  created_at: text,
});

export const TemplateListItemSchema = z.looseObject({
  id: z.string(),
  name: z.string(),
  description: text,
  category: text,
  is_system: z.boolean(),
  use_count: z.number().nullish(),
  preview_image_path: text,
});

export const TemplateSchema = TemplateListItemSchema.extend({
  latex_content: z.string(),
});

export const JobSchema = z.looseObject({
  jobId: z.string(),
  title: z.string(),
  company: z.string(),
  matchScore: z.number().nullish(),
  url: text,
  location: text,
  source: text,
  category: text,
  datePosted: text,
  salary: text,
  jobType: text,
  experienceLevel: text,
  requiredSkills: textList.nullish(),
  preferredSkills: textList.nullish(),
  missingSkills: textList.nullish(),
  atsKeywords: textList.nullish(),
  matchBreakdown: z
    .looseObject({
      vectorScore: z.number().nullish(),
      keywordScore: z.number().nullish(),
      matchedSkills: textList.nullish(),
      explanation: text,
    })
    .nullish(),
  isAnalyzed: z.boolean().nullish(),
  description: text,
  createdAt: text,
});

export const ResumeSummarySchema = z.looseObject({
  id: z.string(),
  name: z.string(),
  status: z.string(),
  type: text,
  job_id: text,
  created_at: text,
  updated_at: text,
});

export type Project = z.infer<typeof ProjectSchema>;
export type TemplateListItem = z.infer<typeof TemplateListItemSchema>;
export type Template = z.infer<typeof TemplateSchema>;
export type Job = z.infer<typeof JobSchema>;
export type ResumeSummary = z.infer<typeof ResumeSummarySchema>;

/** Thrown when a response does not have the shape the UI needs. */
export class ApiResponseError extends Error {
  constructor(
    readonly url: string,
    readonly issues: z.core.$ZodIssue[]
  ) {
    const first = issues[0];
    const where = first?.path.length ? ` at ${first.path.join('.')}` : '';
    super(`Unexpected response from ${url}${where}: ${first?.message ?? 'invalid data'}`);
    this.name = 'ApiResponseError';
  }
}

/** Validates `response.data` against a schema, keeping the rest of the axios response. */
export function validated<S extends z.ZodType>(schema: S) {
  return <T>(response: AxiosResponse<T>): AxiosResponse<z.infer<S>> => {
    const result = schema.safeParse(response.data);
    if (!result.success) {
      throw new ApiResponseError(response.config?.url ?? 'the API', result.error.issues);
    }
    return { ...response, data: result.data };
  };
}
