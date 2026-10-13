import React from 'react';
import type { Severity } from '@/types/domain';
import { formatSeverity } from '@/utils/severity';

export interface SeverityBadgeProps {
  severity: Severity;
  compact?: boolean;
  className?: string;
}

export function SeverityBadge({ severity, compact = false, className = '' }: SeverityBadgeProps) {
  const label = formatSeverity(severity);

  // Shapes on a 12px grid (INV-05)
  const renderShape = () => {
    switch (severity) {
      case 'CRITICAL':
        // Filled Octagon
        return (
          <svg className="w-3 h-3 fill-sev-critical shrink-0" viewBox="0 0 12 12" aria-hidden="true">
            <polygon points="3.5,0 8.5,0 12,3.5 12,8.5 8.5,12 3.5,12 0,8.5 0,3.5" />
          </svg>
        );
      case 'HIGH':
        // Filled Triangle
        return (
          <svg className="w-3 h-3 fill-sev-high shrink-0" viewBox="0 0 12 12" aria-hidden="true">
            <polygon points="6,1 12,11 0,11" />
          </svg>
        );
      case 'MEDIUM':
        // Filled Diamond
        return (
          <svg className="w-3 h-3 fill-sev-medium shrink-0" viewBox="0 0 12 12" aria-hidden="true">
            <polygon points="6,0 12,6 6,12 0,6" />
          </svg>
        );
      case 'LOW':
        // Open Circle (Ring)
        return (
          <svg className="w-3 h-3 text-sev-low shrink-0" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="6" cy="6" r="4.5" />
          </svg>
        );
      case 'INFO':
        // Open Square
        return (
          <svg className="w-3 h-3 text-sev-info shrink-0" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <rect x="1.5" y="1.5" width="9" height="9" />
          </svg>
        );
    }
  };

  const textColors: Record<Severity, string> = {
    CRITICAL: 'text-sev-critical',
    HIGH: 'text-sev-high',
    MEDIUM: 'text-sev-medium',
    LOW: 'text-sev-low',
    INFO: 'text-sev-info',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium font-sans ${textColors[severity]} ${className}`}
      title={`Severity: ${label}`}
      role="status"
    >
      {renderShape()}
      {!compact && <span>{label}</span>}
    </span>
  );
}
