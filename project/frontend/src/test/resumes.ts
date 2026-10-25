import type { Resume } from '@/components/dashboard/resumes/types';

/** A synthetic resume row. */
export function makeResume(overrides: Partial<Resume> = {}): Resume {
  return {
    id: 'r1-abcdefgh',
    name: 'Backend resume',
    type: 'standard',
    status: 'compiled',
    pdf_path: 'u1/r1.pdf',
    tex_s3_key: 'u1/r1.tex',
    latex_content: '\\documentclass{article}',
    created_at: '2026-03-01T10:00:00Z',
    updated_at: '2026-03-02T10:00:00Z',
    ...overrides,
  };
}
