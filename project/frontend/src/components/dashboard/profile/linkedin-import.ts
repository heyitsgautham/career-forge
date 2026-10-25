/** What POST /api/auth/linkedin/import-profile reports as imported. */
export interface LinkedInImported {
  education_added?: number;
  certifications_added?: number;
  name?: boolean | string;
  headline?: boolean | string;
  location?: boolean | string;
  email?: boolean | string;
  phone?: boolean | string;
  website?: boolean | string;
}

const SINGLE_FIELDS = ['name', 'headline', 'location', 'email', 'phone', 'website'] as const;

/** The toast text after a LinkedIn import, listing what was added. */
export function describeLinkedInImport(imported: LinkedInImported | null | undefined): string {
  const parts: string[] = [];
  if (imported?.education_added) parts.push(`${imported.education_added} education`);
  if (imported?.certifications_added) parts.push(`${imported.certifications_added} certifications`);
  for (const field of SINGLE_FIELDS) {
    if (imported?.[field]) parts.push(field);
  }
  return parts.length > 0
    ? `Imported: ${parts.join(', ')}`
    : 'Profile imported (no new data found).';
}
