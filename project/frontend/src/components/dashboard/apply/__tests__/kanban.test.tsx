import { DragDropContext } from '@hello-pangea/dnd';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Send } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import { KanbanColumn, StatsBar } from '../kanban';
import { makeApplication } from '@/test/applications';

function renderColumn(apps = [makeApplication()], onDelete = vi.fn()) {
  render(
    <DragDropContext onDragEnd={() => {}}>
      <KanbanColumn
        columnKey="applied"
        label="Applied"
        icon={Send}
        color="text-primary"
        bg="bg-primary/10"
        apps={apps}
        onDelete={onDelete}
      />
    </DragDropContext>
  );
  return onDelete;
}

describe('KanbanColumn', () => {
  it('counts its cards and shows each role, company, date and note', () => {
    renderColumn([
      makeApplication({ notes: 'Referral from Asha', resumeId: 'r1' }),
      makeApplication({ applicationId: 'a2', roleTitle: 'ML Intern' }),
    ]);
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Backend Intern')).toBeInTheDocument();
    expect(screen.getByText('ML Intern')).toBeInTheDocument();
    expect(screen.getAllByText('Mar 5')).toHaveLength(2);
    expect(screen.getByText('Referral from Asha')).toBeInTheDocument();
    expect(screen.getByText('Resume')).toBeInTheDocument();
  });

  it('invites a drop when empty', () => {
    renderColumn([]);
    expect(screen.getByText('Drag applications here')).toBeInTheDocument();
  });

  it('deletes a card by id', async () => {
    const onDelete = renderColumn();
    await userEvent.click(screen.getByRole('button', { name: 'Delete application' }));
    expect(onDelete).toHaveBeenCalledWith('a1');
  });
});

describe('StatsBar', () => {
  it('renders nothing without applications', () => {
    const { container } = render(<StatsBar applications={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('counts applications per pipeline stage', () => {
    render(
      <StatsBar
        applications={[
          makeApplication({ status: 'applied' }),
          makeApplication({ status: 'applied' }),
          makeApplication({ status: 'offered' }),
          makeApplication({ status: 'saved' }),
        ]}
      />
    );
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('2 Applied')).toBeInTheDocument();
    expect(screen.getByText('0 Interviewing')).toBeInTheDocument();
    expect(screen.getByText('1 Offer')).toBeInTheDocument();
    expect(screen.getByText('0 Rejected')).toBeInTheDocument();
  });
});
