import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';
import type { ProfileData, ProfileField } from './types';

/** Fields PUT /api/auth/profile accepts. id and email are not editable. */
const EDITABLE_FIELDS = [
  'name',
  'headline',
  'summary',
  'location',
  'phone',
  'website',
  'linkedin_url',
  'address_line1',
  'address_line2',
  'city',
  'state',
  'zip_code',
  'country',
  'institution',
  'degree',
  'field_of_study',
  'graduation_year',
  'experience',
  'education',
  'skills',
  'certifications',
  'achievements',
] as const satisfies readonly ProfileField[];

/**
 * Loads the profile whenever `refreshKey` changes, keeps local edits, and
 * saves them. `reload` refetches without the loading state, for use after an
 * import has changed the stored profile.
 */
export function useProfile(refreshKey: number) {
  const { toast } = useToast();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setLoading(true);
        const response = await api.get('/api/auth/profile');
        if (active) setProfile(response.data);
      } catch (error: unknown) {
        toast({
          title: 'Error',
          description: apiErrorDetail(error, 'Failed to load profile'),
          variant: 'destructive',
        });
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refreshKey, toast]);

  const reload = useCallback(async () => {
    try {
      const response = await api.get('/api/auth/profile');
      setProfile(response.data);
    } catch {
      /* keep what is on screen */
    }
  }, []);

  const save = async () => {
    if (!profile) return;
    try {
      setSaving(true);
      const body = Object.fromEntries(EDITABLE_FIELDS.map((field) => [field, profile[field]]));
      const response = await api.put('/api/auth/profile', body);
      setProfile(response.data);
      toast({ title: 'Success', description: 'Profile updated successfully' });
    } catch (error: unknown) {
      toast({
        title: 'Error',
        description: apiErrorDetail(error, 'Failed to save profile'),
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const change = <K extends ProfileField>(field: K, value: ProfileData[K]) => {
    setProfile((current) => (current ? { ...current, [field]: value } : current));
  };

  return { profile, loading, saving, save, change, reload };
}
