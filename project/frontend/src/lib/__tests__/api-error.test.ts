import { describe, expect, it } from 'vitest';
import { apiErrorDetail } from '@/lib/api-error';

const axiosError = (detail: unknown) => ({ response: { data: { detail } } });

describe('apiErrorDetail', () => {
  it('returns a string detail from an HTTPException', () => {
    expect(apiErrorDetail(axiosError('Resume not found'), 'fallback')).toBe('Resume not found');
  });

  it('joins the messages of a FastAPI validation error list', () => {
    const detail = [
      { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address' },
      { type: 'missing', loc: ['body', 'password'], msg: 'Field required' },
    ];
    expect(apiErrorDetail(axiosError(detail), 'fallback')).toBe(
      'value is not a valid email address; Field required'
    );
  });

  it('accepts plain strings inside a detail list', () => {
    expect(apiErrorDetail(axiosError(['first', 'second']), 'fallback')).toBe('first; second');
  });

  it.each([
    ['no response', new Error('Network Error')],
    ['null', null],
    ['undefined', undefined],
    ['an empty detail', axiosError('')],
    ['a whitespace detail', axiosError('   ')],
    ['an object detail', axiosError({ code: 42 })],
    ['a list without messages', axiosError([{ loc: ['body'] }, 3])],
    ['an empty list', axiosError([])],
  ])('falls back for %s', (_label, error) => {
    expect(apiErrorDetail(error, 'Please try again.')).toBe('Please try again.');
  });
});
