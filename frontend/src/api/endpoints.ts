export const endpoints = {
  systemStatus: () => '/v1/system/status',
  dashboardSummary: (region?: string) => `/v1/dashboard/summary${region ? `?region=${encodeURIComponent(region)}` : ''}`,
  findings: (params?: string) => `/v1/findings${params ? `?${params}` : ''}`,
  finding: (id: string) => `/v1/findings/${encodeURIComponent(id)}`,
  findingLifecycle: (id: string) => `/v1/findings/${encodeURIComponent(id)}`,
  findingGenerateAi: (id: string) => `/v1/findings/${encodeURIComponent(id)}/ai-explanation`,
  architecture: (view: string, selection?: { intentId?: string; version?: string }) => {
    const params = new URLSearchParams({ view });
    if (selection?.intentId) params.set('intentId', selection.intentId);
    if (selection?.version) params.set('version', selection.version);
    return `/v1/architecture/graph?${params.toString()}`;
  },
  intents: () => '/v1/intents',
  intent: (id: string) => `/v1/intents/${encodeURIComponent(id)}`,
  intentApprove: (id: string) => `/v1/intents/${encodeURIComponent(id)}/approve`,
  intentVersions: (id: string, params?: string) => `/v1/intents/${encodeURIComponent(id)}/versions${params ? `?${params}` : ''}`,
  intentVersion: (id: string, version: number) => `/v1/intents/${encodeURIComponent(id)}/versions/${version}`,
  intentVersionApprove: (id: string, version: number) => `/v1/intents/${encodeURIComponent(id)}/versions/${version}/approve`,
  intentRollback: (id: string) => `/v1/intents/${encodeURIComponent(id)}/rollback`,
  intentDiff: (id: string, fromVersion: number, toVersion: number) => `/v1/intents/${encodeURIComponent(id)}/diff?fromVersion=${fromVersion}&toVersion=${toVersion}`,
  intentUploadUrl: () => '/v1/intents/upload-url',
  driftEvents: (params?: string) => `/v1/drift-events${params ? `?${params}` : ''}`,
  remediations: (status?: string) => `/v1/remediations${status ? `?status=${encodeURIComponent(status)}` : ''}`,
  remediation: (id: string) => `/v1/remediations/${encodeURIComponent(id)}`,
  remediationDecision: (id: string) => `/v1/remediations/${encodeURIComponent(id)}/decision`,
  audit: (params?: string) => `/v1/audit${params ? `?${params}` : ''}`,
  evaluations: (params?: string) => `/v1/evaluations${params ? `?${params}` : ''}`,
  evaluation: (evaluationId: string) => `/v1/evaluations/${encodeURIComponent(evaluationId)}`,
};
