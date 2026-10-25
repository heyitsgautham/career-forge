import { describe, expect, it } from 'vitest';
import { summarizeImport } from '../import-summary';

describe('summarizeImport', () => {
  it('counts a clean import', () => {
    expect(summarizeImport([{ status: 'success' }])).toEqual({
      title: '1 project imported successfully',
    });
    expect(summarizeImport([{ status: 'success' }, { status: 'success' }]).title).toBe(
      '2 projects imported successfully'
    );
  });

  it('names the repositories that failed in a mixed import', () => {
    expect(
      summarizeImport([
        { full_name: 'asha/ok', status: 'success' },
        { full_name: 'asha/bad', status: 'error' },
        { full_name: 'asha/worse', status: 'error' },
      ])
    ).toEqual({ title: '1 imported, 2 failed', description: 'Failed: asha/bad, asha/worse' });
  });

  it('shows the first error when everything failed', () => {
    expect(
      summarizeImport([
        { status: 'error', error: 'Repository is empty' },
        { status: 'error', error: 'Rate limited' },
      ])
    ).toEqual({
      title: 'Import failed for 2 projects',
      description: 'Repository is empty',
      variant: 'destructive',
    });
  });

  it('falls back when a failure has no error text', () => {
    expect(summarizeImport([{ status: 'error' }]).description).toBe('Unknown error');
  });

  it('says completed when the API returned no results', () => {
    expect(summarizeImport([])).toEqual({ title: 'Import completed' });
  });
});
