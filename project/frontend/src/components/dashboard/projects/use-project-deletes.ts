import { useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

const PROJECTS_KEY = ['projects'];

/**
 * Deleting one project or all of them. Both update the cached list first so
 * the cards vanish at once, and restore the snapshot if the API refuses.
 */
export function useProjectDeletes() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const deleteOne = useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onMutate: async (id: string) => {
      // Cancel any in-flight refetches so they don't overwrite the optimistic update
      await queryClient.cancelQueries({ queryKey: PROJECTS_KEY });
      const previous = queryClient.getQueryData(PROJECTS_KEY);
      queryClient.setQueryData(PROJECTS_KEY, (old: unknown) => {
        if (!Array.isArray(old)) return old;
        return old.filter((p: { id: string }) => p.id !== id);
      });
      return { previous };
    },
    onError: (_err, _id, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(PROJECTS_KEY, context.previous);
      }
      toast({ title: 'Failed to delete project', variant: 'destructive' });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });

  const deleteAll = useMutation({
    mutationFn: () => projectsApi.deleteAll(),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: PROJECTS_KEY });
      const previous = queryClient.getQueryData(PROJECTS_KEY);
      queryClient.setQueryData(PROJECTS_KEY, []);
      return { previous };
    },
    onSuccess: (response) => {
      toast({
        title: 'All projects cleared',
        description: response.data?.message || 'Projects deleted.',
      });
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(PROJECTS_KEY, context.previous);
      }
      toast({ title: 'Failed to clear projects', variant: 'destructive' });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });

  return {
    deleteProject: (id: string) => deleteOne.mutate(id),
    clearAll: () => deleteAll.mutate(),
    clearing: deleteAll.isPending,
  };
}
