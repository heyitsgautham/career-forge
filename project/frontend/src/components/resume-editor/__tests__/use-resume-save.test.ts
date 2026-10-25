import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ resumesApi: { saveLaTeX: vi.fn() } }));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { AUTO_SAVE_DELAY, useResumeSave } from '../use-resume-save';

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  api.resumesApi.saveLaTeX.mockResolvedValue({});
});
afterEach(() => vi.useRealTimers());

const render = (content = 'editor text') => renderHook(() => useResumeSave('r1', () => content));

describe('useResumeSave', () => {
  it('saves the editor content on demand', async () => {
    const { result } = render();
    await act(() => result.current.save());
    expect(api.resumesApi.saveLaTeX).toHaveBeenCalledWith('r1', 'editor text');
    expect(result.current.saveStatus).toBe('saved');
  });

  it('skips saving an empty document', async () => {
    const { result } = render('');
    await act(() => result.current.save());
    expect(api.resumesApi.saveLaTeX).not.toHaveBeenCalled();
  });

  it('debounces typing into one save of the latest text', async () => {
    const { result } = render();

    act(() => result.current.scheduleSave('v1'));
    expect(result.current.saveStatus).toBe('dirty');
    await act(() => vi.advanceTimersByTimeAsync(AUTO_SAVE_DELAY - 1));
    act(() => result.current.scheduleSave('v2'));
    await act(() => vi.advanceTimersByTimeAsync(AUTO_SAVE_DELAY));

    expect(api.resumesApi.saveLaTeX).toHaveBeenCalledOnce();
    expect(api.resumesApi.saveLaTeX).toHaveBeenCalledWith('r1', 'v2');
    expect(result.current.saveStatus).toBe('saved');
  });

  it('stays dirty and warns when the save fails', async () => {
    api.resumesApi.saveLaTeX.mockRejectedValue(new Error('500'));
    const { result } = render();
    await act(() => result.current.save());
    expect(result.current.saveStatus).toBe('dirty');
    expect(toast).toHaveBeenCalledWith({ title: 'Save failed', variant: 'destructive' });
  });

  it('still saves a pending edit after the editor unmounts', async () => {
    const { result, unmount } = render();
    act(() => result.current.scheduleSave('last words'));
    unmount();
    await vi.advanceTimersByTimeAsync(AUTO_SAVE_DELAY);
    expect(api.resumesApi.saveLaTeX).toHaveBeenCalledWith('r1', 'last words');
  });
});
