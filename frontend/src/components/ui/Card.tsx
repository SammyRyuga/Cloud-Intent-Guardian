import React from 'react';
import { cn } from './Button';

export function Card({
  className,
  children,
  padding = 'md',
}: {
  className?: string;
  children: React.ReactNode;
  padding?: 'sm' | 'md' | 'lg' | 'none';
}) {
  const paddings = {
    none: 'p-0',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
  };

  return (
    <div
      className={cn(
        'rounded-[12px] border border-rule bg-sheet text-ink shadow-none',
        paddings[padding],
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  className,
  title,
  subtitle,
  action,
}: {
  className?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className={cn('flex items-start justify-between border-b border-rule pb-3 mb-4', className)}>
      <div>
        <h3 className="font-title text-base font-semibold text-ink leading-tight">{title}</h3>
        {subtitle && <p className="text-xs text-pencil mt-0.5">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
