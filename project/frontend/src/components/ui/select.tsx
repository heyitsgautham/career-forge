import * as React from 'react';
import { cn } from '@/lib/utils';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options?: Array<{ value: string; label: string }>;
}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, children, ...props }, ref) => {
    return (
      <select
        className={cn(
          'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:border-primary/50 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        ref={ref}
        {...props}
      >
        {children}
      </select>
    );
  }
);

Select.displayName = 'Select';

export { Select };
