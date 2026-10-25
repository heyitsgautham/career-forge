import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AddApplicationModal } from '../add-application-modal';
import { makeJob } from '@/test/fixtures';

afterEach(() => vi.restoreAllMocks());

function renderModal(props: Partial<Parameters<typeof AddApplicationModal>[0]> = {}) {
  const handlers = { onClose: vi.fn(), onSubmit: vi.fn() };
  render(
    <AddApplicationModal
      open
      isSubmitting={false}
      jobs={[makeJob({ jobId: 'j7', title: 'Data Intern', company: 'Demo Corp' })]}
      {...handlers}
      {...props}
    />
  );
  return handlers;
}

describe('AddApplicationModal', () => {
  it('renders nothing while closed', () => {
    const { container } = render(
      <AddApplicationModal
        open={false}
        isSubmitting={false}
        jobs={[]}
        onClose={() => {}}
        onSubmit={() => {}}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('fills company, role and URL from a picked job', async () => {
    const { onSubmit } = renderModal();
    await userEvent.selectOptions(screen.getByRole('combobox'), 'j7');
    expect(screen.getByDisplayValue('Demo Corp')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Data Intern')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Add Application/ }));
    expect(onSubmit).toHaveBeenCalledWith({
      jobId: 'j7',
      companyName: 'Demo Corp',
      roleTitle: 'Data Intern',
      notes: '',
      url: 'https://jobs.example.com/j1',
    });
  });

  it('needs a company and a role, and tags hand-entered jobs as manual', async () => {
    const { onSubmit } = renderModal({ jobs: [] });
    const submit = screen.getByRole('button', { name: /Add Application/ });
    expect(submit).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText('e.g. Stripe'), 'Sample Labs');
    await userEvent.type(screen.getByPlaceholderText('e.g. Backend SDE'), 'Backend Intern');
    await userEvent.type(screen.getByPlaceholderText('Applied via referral, etc.'), 'Referral');
    await userEvent.click(submit);

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        jobId: expect.stringMatching(/^manual-\d+$/),
        companyName: 'Sample Labs',
        notes: 'Referral',
      })
    );
  });

  it('asks before discarding typed changes', async () => {
    const confirm = vi
      .spyOn(window, 'confirm')
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    const { onClose } = renderModal();
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(confirm).not.toHaveBeenCalled();

    await userEvent.type(screen.getByPlaceholderText('e.g. Stripe'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('shows progress while saving', () => {
    renderModal({ isSubmitting: true });
    expect(screen.getByRole('button', { name: /Creating/ })).toBeDisabled();
  });
});
