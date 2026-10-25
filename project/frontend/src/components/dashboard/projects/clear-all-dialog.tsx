import { Button } from '@/components/ui/button';
import { Portal } from '@/components/ui/portal';

/** Confirmation before deleting every project. */
export function ClearAllDialog({
  count,
  onCancel,
  onConfirm,
}: {
  count: number;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Portal>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="bg-background p-6 rounded-xl border border-border/60 w-full max-w-sm">
          <h2 className="text-lg font-bold mb-2">Clear All Projects?</h2>
          <p className="text-sm text-muted-foreground mb-4">
            This will permanently delete all {count} projects. You can re-import specific ones
            afterwards using &quot;Import from GitHub&quot;.
          </p>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={onConfirm}>
              Yes, Clear All
            </Button>
          </div>
        </div>
      </div>
    </Portal>
  );
}
