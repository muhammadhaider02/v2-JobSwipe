'use client';

import { cn } from '@/lib/utils';

type SkillBadgeVariant = 'existing' | 'missing' | 'learned' | 'neutral';

interface SkillBadgeProps {
  variant: SkillBadgeVariant;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

const variantStyles: Record<SkillBadgeVariant, string> = {
  existing:
    'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/20',
  missing:
    'bg-destructive/10 text-destructive border-destructive/20',
  learned:
    'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20',
  neutral:
    'bg-muted text-muted-foreground border-border',
};

export function SkillBadge({
  variant,
  children,
  onClick,
  className,
}: SkillBadgeProps) {
  const Component = onClick ? 'button' : 'span';

  return (
    <Component
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
        variantStyles[variant],
        onClick && 'cursor-pointer hover:opacity-80',
        className,
      )}
    >
      {children}
    </Component>
  );
}
