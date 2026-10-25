import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobsTable, type JobsTableProps } from '../jobs-table';
import { makeJob } from '@/test/fixtures';

function renderTable(overrides: Partial<JobsTableProps> = {}) {
  const props: JobsTableProps = {
    rows: [makeJob({ jobId: 'j1' }), makeJob({ jobId: 'j2', title: 'Data Intern', url: '' })],
    loading: false,
    filteredCount: 2,
    totalCount: 2,
    page: 0,
    totalPages: 1,
    onPageChange: vi.fn(),
    source: 'All',
    onSourceChange: vi.fn(),
    tracking: { j1: { status: 'applied', notes: '' } },
    tailoredResumes: {},
    tailoringJobId: null,
    onTrack: vi.fn(),
    onTailor: vi.fn(),
    onSelect: vi.fn(),
    ...overrides,
  };
  render(<JobsTable {...props} />);
  return props;
}

const bodyRows = () => screen.getAllByRole('row').slice(1);

describe('JobsTable', () => {
  it('renders one row per job with its tracking status', () => {
    renderTable();
    const [first, second] = bodyRows();
    expect(within(first).getByRole('button', { name: 'Backend Intern' })).toBeInTheDocument();
    expect(within(first).getByRole('combobox')).toHaveValue('applied');
    expect(within(second).getByRole('combobox')).toHaveValue('pending');
    expect(within(second).queryByRole('link', { name: /View/ })).not.toBeInTheDocument();
  });

  it('shows eight skeleton rows while loading', () => {
    renderTable({ loading: true });
    expect(bodyRows()).toHaveLength(8);
    expect(bodyRows()[0].querySelectorAll('td')).toHaveLength(7);
  });

  it('tells "no jobs yet" apart from "nothing matches"', () => {
    renderTable({ rows: [], filteredCount: 0, totalCount: 0 });
    expect(screen.getByText(/No jobs yet/)).toBeInTheDocument();
  });

  it('says when the filters hide every job', () => {
    renderTable({ rows: [], filteredCount: 0, totalCount: 5 });
    expect(screen.getByText('No jobs match the current filters.')).toBeInTheDocument();
  });

  it('passes the job id up for track, tailor and select', async () => {
    const props = renderTable();
    const [first] = bodyRows();

    await userEvent.selectOptions(within(first).getByRole('combobox'), 'interviewing');
    await userEvent.click(within(first).getByRole('button', { name: /Resume/ }));
    await userEvent.click(within(first).getByRole('button', { name: 'Backend Intern' }));

    expect(props.onTrack).toHaveBeenCalledWith('j1', 'interviewing');
    expect(props.onTailor).toHaveBeenCalledWith('j1');
    expect(props.onSelect).toHaveBeenCalledWith(expect.objectContaining({ jobId: 'j1' }));
  });

  it('links to the editor when a tailored resume exists and spins while tailoring', () => {
    renderTable({ tailoredResumes: { j1: 'r7' }, tailoringJobId: 'j2' });
    const [first, second] = bodyRows();
    expect(within(first).getByRole('link', { name: /Editor/ })).toHaveAttribute(
      'href',
      '/dashboard/resumes/r7/edit'
    );
    expect(within(second).getByRole('button', { name: /Tailoring/ })).toBeDisabled();
  });

  it('changes the source filter', async () => {
    const props = renderTable();
    await userEvent.selectOptions(screen.getByLabelText('Filter by source'), 'linkedin');
    expect(props.onSourceChange).toHaveBeenCalledWith('linkedin');
  });

  it('hides pagination on a single page', () => {
    renderTable();
    expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
  });

  it('pages forward and back and disables the ends', async () => {
    const props = renderTable({ page: 1, totalPages: 3, filteredCount: 60 });
    expect(screen.getByText('60 jobs · Page 2 of 3')).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Next page'));
    await userEvent.click(screen.getByLabelText('Previous page'));
    expect(props.onPageChange).toHaveBeenNthCalledWith(1, 2);
    expect(props.onPageChange).toHaveBeenNthCalledWith(2, 0);
  });

  it('disables previous on the first page and next on the last', () => {
    renderTable({ page: 0, totalPages: 1 + 1, filteredCount: 30 });
    expect(screen.getByLabelText('Previous page')).toBeDisabled();
    expect(screen.getByLabelText('Next page')).toBeEnabled();
  });
});
