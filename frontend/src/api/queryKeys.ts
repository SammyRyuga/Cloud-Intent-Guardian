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
  intentVersions: (intentId: string, filters?: Record<string, unknown>) => ['intent-versions', intentId, filters ?? {}] as const,
  intentVersion: (intentId: string, version: number) => ['intent-version', intentId, version] as const,
  intentDiff: (intentId: string, fromVersion: number, toVersion: number) => ['intent-diff', intentId, fromVersion, toVersion] as const,
  driftEvents: (filters?: Record<string, unknown>) => ['drift-events', filters ?? {}] as const,
  remediations: (filters?: Record<string, unknown>) => ['remediations', filters ?? {}] as const,
  remediation: (id: string) => ['remediation', id] as const,
  audit: (filters?: Record<string, unknown>) => ['audit', filters ?? {}] as const,
  systemStatus: () => ['system-status'] as const,
  evaluationLists: () => ['evaluations'] as const,
  evaluationResults: () => [['dashboard-summary'], ['findings'], ['finding'], ['architecture'], ['drift-events'], ['system-status'], ['audit']] as const,
  evaluations: (filters?: Record<string, unknown>) => ['evaluations', filters ?? {}] as const,
  evaluation: (evaluationId: string) => ['evaluation', evaluationId] as const,
  apiHealth: () => ['api-health'] as const,
};
