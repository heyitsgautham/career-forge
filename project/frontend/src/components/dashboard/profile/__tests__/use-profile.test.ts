import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const http = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock('@/lib/api', () => ({ default: http }));
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { useProfile } from '../use-profile';

const PROFILE = { id: 'u1', email: 'asha@example.com', name: 'Asha Example', skills: ['Python'] };

beforeEach(() => {
  vi.clearAllMocks();
  http.get.mockResolvedValue({ data: PROFILE });
  http.put.mockImplementation(async (_url: string, body: object) => ({
    data: { ...PROFILE, ...body },
  }));
});

describe('useProfile', () => {
  it('loads the profile and reloads it when the refresh key changes', async () => {
    const { result, rerender } = renderHook(({ key }) => useProfile(key), {
      initialProps: { key: 0 },
    });
    await waitFor(() => expect(result.current.profile).toEqual(PROFILE));
    rerender({ key: 1 });
    await waitFor(() => expect(http.get).toHaveBeenCalledTimes(2));
  });

  it('reports a profile that will not load', async () => {
    http.get.mockRejectedValue({ response: { data: { detail: 'Session expired' } } });
    const { result } = renderHook(() => useProfile(0));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.profile).toBeNull();
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ description: 'Session expired' }));
  });

  it('saves only editable fields', async () => {
    const { result } = renderHook(() => useProfile(0));
    await waitFor(() => expect(result.current.profile).not.toBeNull());

    act(() => result.current.change('headline', 'Backend developer'));
    await act(() => result.current.save());

    const [url, body] = http.put.mock.calls[0];
    expect(url).toBe('/api/auth/profile');
    expect(body).toMatchObject({ name: 'Asha Example', headline: 'Backend developer' });
    expect(body).not.toHaveProperty('id');
    expect(body).not.toHaveProperty('email');
    expect(result.current.saving).toBe(false);
    expect(toast).toHaveBeenCalledWith({
      title: 'Success',
      description: 'Profile updated successfully',
    });
  });

  it('keeps edits and explains a failed save', async () => {
    http.put.mockRejectedValue({ response: { data: { detail: 'Name too long' } } });
    const { result } = renderHook(() => useProfile(0));
    await waitFor(() => expect(result.current.profile).not.toBeNull());
    act(() => result.current.change('name', 'A'.repeat(300)));
    await act(() => result.current.save());
    expect(result.current.profile?.name).toHaveLength(300);
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ description: 'Name too long' }));
  });

  it('reloads quietly and keeps the screen when that fails', async () => {
    const { result } = renderHook(() => useProfile(0));
    await waitFor(() => expect(result.current.profile).not.toBeNull());
    http.get.mockRejectedValueOnce(new Error('500'));
    await act(() => result.current.reload());
    expect(result.current.profile).toEqual(PROFILE);
    http.get.mockResolvedValueOnce({ data: { ...PROFILE, skills: ['Python', 'Go'] } });
    await act(() => result.current.reload());
    expect(result.current.profile?.skills).toEqual(['Python', 'Go']);
  });
});
