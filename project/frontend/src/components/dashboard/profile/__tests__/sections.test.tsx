import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState, type ComponentType } from 'react';
import { describe, expect, it } from 'vitest';
import { CertificationsSection } from '../certifications-section';
import { ContactSections } from '../contact-sections';
import { EducationSection } from '../education-section';
import { ExperienceSection } from '../experience-section';
import { GithubProjectsSection } from '../github-projects-section';
import { SkillsAndAchievements } from '../skills-achievements';
import type { ProfileChangeHandler, ProfileData } from '../types';

type Section = ComponentType<{ profile: ProfileData; onChange: ProfileChangeHandler }>;

const BASE: ProfileData = { id: 'u1', email: 'asha@example.com', name: 'Asha Example' };

/** Renders a section against real state, and exposes the latest profile. */
function renderSection(Section: Section, initial: Partial<ProfileData> = {}) {
  const latest: { profile: ProfileData } = { profile: { ...BASE, ...initial } };
  function Harness() {
    const [profile, setProfile] = useState<ProfileData>(latest.profile);
    latest.profile = profile;
    const onChange: ProfileChangeHandler = (field, value) =>
      setProfile((p) => ({ ...p, [field]: value }));
    return <Section profile={profile} onChange={onChange} />;
  }
  render(<Harness />);
  return latest;
}

describe('ContactSections', () => {
  it('edits the name and keeps the email read-only', async () => {
    const latest = renderSection(ContactSections);
    const name = screen.getByLabelText('Full Name');
    await userEvent.clear(name);
    await userEvent.type(name, 'Asha E.');
    expect(latest.profile.name).toBe('Asha E.');
    expect(screen.getByDisplayValue('asha@example.com')).toBeDisabled();
  });
});

describe('ExperienceSection', () => {
  it('adds a role, fills it in, adds and removes a highlight, then removes the role', async () => {
    const latest = renderSection(ExperienceSection);
    await userEvent.click(screen.getByRole('button', { name: 'Add Experience' }));
    await userEvent.type(screen.getByPlaceholderText('Company name'), 'Sample Labs');
    await userEvent.type(screen.getByPlaceholderText('e.g., Senior Software Engineer'), 'Intern');
    await userEvent.type(
      screen.getByPlaceholderText('Describe your achievement or responsibility'),
      'Built APIs'
    );
    expect(latest.profile.experience).toEqual([
      {
        company: 'Sample Labs',
        title: 'Intern',
        dates: '',
        location: '',
        highlights: ['Built APIs'],
      },
    ]);

    const card = screen.getByText('Experience 1').parentElement!.parentElement!;
    const buttons = within(card).getAllByRole('button');
    await userEvent.click(buttons.find((b) => /Add/i.test(b.textContent ?? ''))!);
    expect(latest.profile.experience?.[0].highlights).toHaveLength(2);

    await userEvent.click(within(card).getAllByRole('button')[0]);
    expect(latest.profile.experience).toEqual([]);
  });
});

describe('EducationSection', () => {
  it('shows legacy single-entry fields until a list entry exists', async () => {
    const latest = renderSection(EducationSection, { institution: 'Example' });
    await userEvent.type(screen.getByLabelText('Institution'), ' Institute');
    expect(latest.profile.institution).toBe('Example Institute');

    await userEvent.click(screen.getByRole('button', { name: /Add Education/ }));
    await userEvent.type(screen.getByPlaceholderText('e.g., 3.8/4.0'), '8.7');
    expect(latest.profile.education?.[0]).toMatchObject({ gpa: '8.7' });
  });
});

describe('CertificationsSection', () => {
  it('adds a certification and removes it', async () => {
    const latest = renderSection(CertificationsSection);
    await userEvent.click(screen.getAllByRole('button')[0]);
    await userEvent.type(screen.getByLabelText('Certification Name *'), 'AWS Cloud Practitioner');
    await userEvent.type(screen.getByLabelText('Issuing Organization *'), 'AWS');
    expect(latest.profile.certifications?.[0]).toMatchObject({
      name: 'AWS Cloud Practitioner',
      issuer: 'AWS',
    });

    const card = screen.getByText('Certification 1').parentElement!;
    await userEvent.click(within(card).getByRole('button'));
    expect(latest.profile.certifications).toEqual([]);
  });
});

describe('SkillsAndAchievements', () => {
  it('adds, edits and removes an achievement', async () => {
    const latest = renderSection(SkillsAndAchievements, { achievements: [] });
    await userEvent.click(screen.getByRole('button', { name: /Add Achievement/ }));
    const input = screen.getAllByRole('textbox').at(-1)!;
    await userEvent.type(input, 'Won a hackathon');
    expect(latest.profile.achievements).toEqual(['Won a hackathon']);
  });
});

describe('GithubProjectsSection', () => {
  it('lists projects and refreshes from its button', async () => {
    let refreshed = 0;
    render(
      <GithubProjectsSection
        projects={[
          {
            projectId: 'p1',
            name: 'job-scout',
            oneLiner: 'Ranks postings',
            technologies: ['Python'],
          },
        ]}
        ingesting={false}
        ingestionStatus="done"
        ingestionSummary={{ total: 1, processed: 1, failed: 0, lastRunAt: '2026-03-10T09:00:00Z' }}
        onRefresh={() => refreshed++}
      />
    );
    expect(screen.getByText('job-scout')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button')[0]);
    expect(refreshed).toBe(1);
  });
});
