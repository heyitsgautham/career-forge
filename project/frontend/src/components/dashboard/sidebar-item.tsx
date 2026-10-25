import type { ReactNode } from 'react';

export function SidebarItem({
  icon,
  label,
  active = false,
  onClick,
  onMouseEnter,
  collapsed = false,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
  onMouseEnter?: () => void;
  collapsed?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={`w-full flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-200 ${
        active
          ? 'bg-primary/10 text-primary font-medium shadow-sm border-l-2 border-primary'
          : 'text-muted-foreground hover:bg-primary/5 hover:text-foreground'
      }`}
      aria-current={active ? 'page' : undefined}
    >
      {icon}
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}
