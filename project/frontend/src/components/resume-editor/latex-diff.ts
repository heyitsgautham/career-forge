/** Line diff for showing AI-proposed LaTeX edits. */

export type DiffLine =
  | { kind: 'equal'; text: string }
  | { kind: 'remove'; text: string }
  | { kind: 'add'; text: string }
  | { kind: 'separator' };

export const CONTEXT = 3; // lines of context around each change

/** Very small Myers-inspired line diff (no external dependency). */
export function diffLines(a: string[], b: string[]): DiffLine[] {
  // Build LCS table
  const m = a.length,
    n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);

  const raw: DiffLine[] = [];
  let i = 0,
    j = 0;
  while (i < m || j < n) {
    if (i < m && j < n && a[i] === b[j]) {
      raw.push({ kind: 'equal', text: a[i++] });
      j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      raw.push({ kind: 'add', text: b[j++] });
    } else {
      raw.push({ kind: 'remove', text: a[i++] });
    }
  }
  return raw;
}

/** Collapse unchanged regions to ±CONTEXT lines around each hunk. */
export function buildHunks(lines: DiffLine[]): DiffLine[] {
  const changed = new Set<number>();
  lines.forEach((l, i) => {
    if (l.kind !== 'equal') changed.add(i);
  });

  if (changed.size === 0) return [];

  const visible = new Set<number>();
  changed.forEach((ci) => {
    for (let k = ci - CONTEXT; k <= ci + CONTEXT; k++)
      if (k >= 0 && k < lines.length) visible.add(k);
  });

  const result: DiffLine[] = [];
  let prevVisible = false;
  lines.forEach((l, i) => {
    if (visible.has(i)) {
      if (!prevVisible && result.length > 0) result.push({ kind: 'separator' });
      result.push(l);
      prevVisible = true;
    } else {
      prevVisible = false;
    }
  });
  return result;
}
