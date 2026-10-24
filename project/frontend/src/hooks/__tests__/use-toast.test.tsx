import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { reducer, toast, useToast } from '@/hooks/use-toast';

const base = (id: string, title = id) => ({ id, title, open: true });

describe('toast reducer', () => {
  it('keeps only the newest toast', () => {
    let state = reducer({ toasts: [] }, { type: 'ADD_TOAST', toast: base('1') });
    state = reducer(state, { type: 'ADD_TOAST', toast: base('2') });
    expect(state.toasts.map((t) => t.id)).toEqual(['2']);
  });

  it('updates a toast by id', () => {
    const state = reducer({ toasts: [base('1', 'old')] }, { type: 'UPDATE_TOAST', toast: { id: '1', title: 'new' } });
    expect(state.toasts[0].title).toBe('new');
    expect(state.toasts[0].open).toBe(true);
  });

  it('closes a dismissed toast without removing it', () => {
    const state = reducer({ toasts: [base('1')] }, { type: 'DISMISS_TOAST', toastId: '1' });
    expect(state.toasts).toHaveLength(1);
    expect(state.toasts[0].open).toBe(false);
  });

  it('removes one toast or all of them', () => {
    const two = { toasts: [base('1'), base('2')] };
    expect(reducer(two, { type: 'REMOVE_TOAST', toastId: '1' }).toasts.map((t) => t.id)).toEqual(['2']);
    expect(reducer(two, { type: 'REMOVE_TOAST' }).toasts).toEqual([]);
  });
});

describe('useToast', () => {
  it('shows a toast and dismisses it through the hook', () => {
    const { result } = renderHook(() => useToast());
    let handle: ReturnType<typeof toast>;
    act(() => {
      handle = toast({ title: 'Saved' });
    });
    expect(result.current.toasts[0]).toMatchObject({ title: 'Saved', open: true });

    act(() => {
      result.current.dismiss(handle.id);
    });
    expect(result.current.toasts[0].open).toBe(false);
  });
});
