/**
 * Turns a failed API call into a message a user can read.
 *
 * FastAPI sends `detail` as a string for HTTPException, but as a list of
 * `{ loc, msg, type }` objects for request validation errors (422). Rendering
 * that list as a React child crashes the page, so callers go through here.
 */
export function apiErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response?.data
    ?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === 'string' ? item : (item as { msg?: unknown })?.msg))
      .filter((msg): msg is string => typeof msg === 'string' && msg.trim() !== '');
    if (messages.length > 0) {
      return messages.join('; ');
    }
  }
  return fallback;
}
