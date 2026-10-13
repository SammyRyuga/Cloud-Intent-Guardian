import type { Severity, DiffState } from '@/types/domain';

export const SEVERITY_ORDER: Record<Severity, number> = {
  CRITICAL: 5,
  HIGH: 4,
  MEDIUM: 3,
  LOW: 2,
  INFO: 1,
};

export function compareSeverity(a: Severity, b: Severity): number {
  return SEVERITY_ORDER[b] - SEVERITY_ORDER[a];
}

export function formatSeverity(sev: Severity): string {
  switch (sev) {
    case 'CRITICAL': return 'Critical';
    case 'HIGH': return 'High';
    case 'MEDIUM': return 'Medium';
    case 'LOW': return 'Low';
    case 'INFO': return 'Info';
  }
}

export function formatDiffState(state: DiffState): string {
  switch (state) {
    case 'MATCHED': return 'Matched';
    case 'ADDED': return 'Unmatched';
    case 'MISSING': return 'Missing';
    case 'CHANGED': return 'Changed';
    case 'UNKNOWN': return 'Unknown';
  }
}
