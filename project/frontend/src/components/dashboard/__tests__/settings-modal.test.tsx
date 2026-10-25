import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithQuery } from '@/test/render-with-query';

const api = vi.hoisted(() => ({
  userApi: { uploadResume: vi.fn() },
  authApi: { githubInstall: vi.fn() },
}));
vi.mock('@/lib/api', () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast }) }));

import { SettingsModal } from '@/components/dashboard/settings-modal';

function renderSettings(githubConnected = false) {
  const handlers = { onClose: vi.fn(), onResumeUploaded: vi.fn(), onLogout: vi.fn() };
  const view = renderWithQuery(
    <SettingsModal githubConnected={githubConnected} githubUsername="asha-example" {...handlers} />
  );
  return { ...view, ...handlers };
}

const upload = (name = 'resume.pdf') => {
  const input = document.getElementById('resume-upload') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(['%PDF'], name)] } });
};

beforeEach(() => vi.clearAllMocks());

describe('SettingsModal', () => {
  it('uploads a resume, reports the fields it filled, and closes', async () => {
    api.userApi.uploadResume.mockResolvedValue({ data: { fields_updated: 7 } });
    const { onResumeUploaded, onClose } = renderSettings();

    upload();

    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    const form = api.userApi.uploadResume.mock.calls[0][0] as FormData;
    expect((form.get('file') as File).name).toBe('resume.pdf');
    expect(onResumeUploaded).toHaveBeenCalledOnce();
    expect(toast).toHaveBeenCalledWith({
      title: 'Resume uploaded!',
      description: 'Extracted 7 profile fields.',
    });
  });

  it('stays open and shows the reason when the upload is refused', async () => {
    api.userApi.uploadResume.mockRejectedValue({
      response: {
        data: { detail: 'Unsupported file type. Please upload PDF, DOCX, or TXT files.' },
      },
    });
    const { onClose } = renderSettings();
    upload('resume.rtf');
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: 'Upload failed',
        description: 'Unsupported file type. Please upload PDF, DOCX, or TXT files.',
        variant: 'destructive',
      })
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it('falls back to a generic reason when the request fails without one', async () => {
    api.userApi.uploadResume.mockRejectedValue(new Error('Network Error'));
    renderSettings();
    upload();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Could not process resume' })
      )
    );
  });

  it('offers to connect GitHub when it is not connected', async () => {
    const { user } = renderSettings(false);
    await user.click(screen.getByRole('button', { name: /Connect GitHub/ }));
    expect(api.authApi.githubInstall).toHaveBeenCalledOnce();
  });

  it('shows the connected GitHub account', () => {
    renderSettings(true);
    expect(screen.getByText('@asha-example')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Connect GitHub/ })).not.toBeInTheDocument();
  });

  it('logs out and closes from its buttons and the backdrop', async () => {
    const { user, onLogout, onClose } = renderSettings();
    await user.click(screen.getByRole('button', { name: 'Logout' }));
    expect(onLogout).toHaveBeenCalledOnce();
    await user.click(screen.getByRole('button', { name: 'Close settings' }));
    await user.click(screen.getByRole('dialog'));
    await user.click(screen.getByText('Upload Resume'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
