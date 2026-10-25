/** Reads the signed-in user's id from the JWT kept in localStorage. */

/** Decodes one base64url JWT segment, which may use - and _ and omit padding. */
function decodeSegment(segment: string): string {
  const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
  return atob(base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '='));
}

/**
 * The `sub` claim of the stored token, or an empty string when there is no
 * token, it is malformed, or the code runs on the server. The signature is
 * not checked here; the backend does that on every request.
 */
export function currentUserId(): string {
  if (typeof window === 'undefined') return '';
  try {
    const token = localStorage.getItem('token');
    if (!token) return '';
    const payload = JSON.parse(decodeSegment(token.split('.')[1]));
    return typeof payload.sub === 'string' ? payload.sub : '';
  } catch {
    return '';
  }
}
