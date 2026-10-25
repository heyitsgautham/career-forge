/** One repository's outcome from POST /api/projects/ingest/github. */
export interface ImportResult {
  full_name?: string;
  status?: string;
  error?: string;
}

export interface ImportToast {
  title: string;
  description?: string;
  variant?: 'destructive';
}

const plural = (n: number) => (n !== 1 ? 's' : '');

/** The toast shown once every imported repository has a result. */
export function summarizeImport(results: ImportResult[]): ImportToast {
  const failed = results.filter((r) => r.status === 'error');
  const succeeded = results.filter((r) => r.status === 'success');

  if (succeeded.length > 0 && failed.length === 0) {
    return {
      title: `${succeeded.length} project${plural(succeeded.length)} imported successfully`,
    };
  }
  if (succeeded.length > 0 && failed.length > 0) {
    return {
      title: `${succeeded.length} imported, ${failed.length} failed`,
      description: `Failed: ${failed.map((f) => f.full_name).join(', ')}`,
    };
  }
  if (failed.length > 0) {
    return {
      title: `Import failed for ${failed.length} project${plural(failed.length)}`,
      description: failed[0].error ?? 'Unknown error',
      variant: 'destructive',
    };
  }
  return { title: 'Import completed' };
}
