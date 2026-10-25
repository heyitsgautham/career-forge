import { describe, expect, it } from 'vitest';
import { describeLinkedInImport } from '../linkedin-import';

describe('describeLinkedInImport', () => {
  it('lists counts first, then single fields in a fixed order', () => {
    expect(
      describeLinkedInImport({
        website: true,
        name: true,
        education_added: 2,
        certifications_added: 1,
        headline: 'Backend developer',
      })
    ).toBe('Imported: 2 education, 1 certifications, name, headline, website');
  });

  it('says nothing new was found when the import added nothing', () => {
    expect(describeLinkedInImport({ education_added: 0, name: false })).toBe(
      'Profile imported (no new data found).'
    );
    expect(describeLinkedInImport(undefined)).toBe('Profile imported (no new data found).');
  });
});
