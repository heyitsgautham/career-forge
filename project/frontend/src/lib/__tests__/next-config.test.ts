import { describe, expect, it } from 'vitest';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const nextConfig = require('../../../next.config.js');

describe('next.config.js', () => {
  it('sends the old standalone profile page to the dashboard profile tab', async () => {
    expect(await nextConfig.redirects()).toContainEqual({
      source: '/dashboard/profile',
      destination: '/dashboard?tab=profile',
      permanent: false,
    });
  });

  it('proxies /api to the backend', async () => {
    const [rule] = await nextConfig.rewrites();
    expect(rule.source).toBe('/api/:path*');
    expect(rule.destination).toMatch(/\/api\/:path\*$/);
  });
});
