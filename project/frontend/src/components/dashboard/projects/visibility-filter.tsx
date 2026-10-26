import { Globe, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Visibility } from './github-repos';

const OPTIONS: { value: Visibility; label: string; icon?: typeof Globe }[] = [
  { value: 'all', label: 'All' },
  { value: 'public', label: 'Public', icon: Globe },
  { value: 'private', label: 'Private', icon: Lock },
];

/** All, public or private, each with its repository count. */
export function VisibilityFilter({
  value,
  onChange,
  counts,
}: {
  value: Visibility;
  onChange: (value: Visibility) => void;
  counts: Record<Visibility, number>;
}) {
  return (
    <div className="flex gap-1">
      {OPTIONS.map(({ value: option, label, icon: Icon }) => (
        <Button
          key={option}
          variant={value === option ? 'default' : 'outline'}
          size="sm"
          onClick={() => onChange(option)}
          className={Icon ? 'text-xs h-8 gap-1' : 'text-xs h-8'}
        >
          {Icon && <Icon className="h-3 w-3" />}
          {label} ({counts[option]})
        </Button>
      ))}
    </div>
  );
}
