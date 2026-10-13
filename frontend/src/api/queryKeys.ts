/**
 * Central query keys builder per AGENTS.md §4.2
 * Never write query keys inline.
 */
export const queryKeys = {
  dashboardSummary: (region?: string) => ['dashboard-summary', region ?? 'default'] as const,
  findings: (filters?: Record<string, unknown>) => ['findings', filters ?? {}] as const,
  finding: (findingId: string) => ['finding', findingId] as const,
  architecture: (view: string, filters?: Record<string, unknown>) => ['architecture', view, filters ?? {}] as const,
  intents: () => ['intents'] as const,
  intent: (intentId: string) => ['intent', intentId] as const,
  driftEvents: (filters?: Record<string, unknown>) => ['drift-events', filters ?? {}] as const,
  remediations: (status?: string) => ['remediations', status ?? 'ALL'] as const,
  remediation: (id: string) => ['remediation', id] as const,
  auditEvents: (filters?: Record<string, unknown>) => ['audit-events', filters ?? {}] as const,
  systemStatus: () => ['system-status'] as const,
  job: (jobId: string) => ['job', jobId] as const,
  apiHealth: () => ['api-health'] as const,
};
