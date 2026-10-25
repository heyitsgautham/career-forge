import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Toaster } from '@/components/ui/toaster';
import { toast } from '@/hooks/use-toast';

describe('Tabs', () => {
  it('shows the panel of the chosen tab', async () => {
    render(
      <Tabs defaultValue="signin">
        <TabsList>
          <TabsTrigger value="signin">Sign In</TabsTrigger>
          <TabsTrigger value="signup">Sign Up</TabsTrigger>
        </TabsList>
        <TabsContent value="signin">sign-in form</TabsContent>
        <TabsContent value="signup">sign-up form</TabsContent>
      </Tabs>
    );
    expect(screen.getByText('sign-in form')).toBeVisible();
    await userEvent.click(screen.getByRole('tab', { name: 'Sign Up' }));
    expect(screen.getByText('sign-up form')).toBeVisible();
    expect(screen.queryByText('sign-in form')).not.toBeInTheDocument();
  });
});

describe('Toaster', () => {
  it('renders toasts raised anywhere in the app and closes them', async () => {
    render(<Toaster />);
    act(() => {
      toast({ title: 'Saved', description: 'Profile updated successfully' });
    });
    expect(screen.getByText('Saved')).toBeInTheDocument();
    expect(screen.getByText('Profile updated successfully')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button'));
    await act(async () => {});
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });
});
