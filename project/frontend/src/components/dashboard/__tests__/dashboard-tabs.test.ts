import { describe, expect, it } from 'vitest';
import {
  HIDDEN_TABS,
  TABS,
  TAB_DESCRIPTIONS,
  TAB_TITLES,
  parseTab,
} from '@/components/dashboard/dashboard-tabs';

describe('parseTab', () => {
  it.each(TABS.map((t) => t.key))('accepts the sidebar tab %s', (key) => {
    expect(parseTab(key)).toBe(key);
  });

  it.each([...HIDDEN_TABS, 'profile'])('accepts %s, which has no sidebar entry', (key) => {
    // Regression: only sidebar tabs used to restore from the URL, so a reload
    // on ?tab=profile or ?tab=templates fell back to the resumes tab.
    expect(parseTab(key)).toBe(key);
  });

  it.each([null, undefined, '', 'settings', 'RESUMES', 'resumes '])('rejects %j', (value) => {
    expect(parseTab(value)).toBeNull();
  });
});

describe('tab copy', () => {
  it('has a title and a description for every tab key', () => {
    const keys = [...TABS.map((t) => t.key), ...HIDDEN_TABS, 'profile'];
    expect(Object.keys(TAB_TITLES).sort()).toEqual([...keys].sort());
    expect(Object.keys(TAB_DESCRIPTIONS).sort()).toEqual([...keys].sort());
  });

  it('spells out multi-word titles instead of showing the URL key', () => {
    expect(TAB_TITLES['skill-gap']).toBe('Skill Gap');
    expect(TAB_TITLES['job-scout']).toBe('Job Scout');
    expect(TAB_TITLES.apply).toBe('Apply & Track');
    expect(TAB_TITLES.roadmap).toBe('Project Roadmap');
  });
});
