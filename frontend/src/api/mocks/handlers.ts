import { http, HttpResponse, delay } from 'msw';
import {
  mockSystemStatus,
  mockDashboardSummary,
  mockFindings,
  mockArchitectureGraph,
  mockDriftEvents,
  mockRemediations,
  mockAuditEvents,
  mockEvaluation,
} from './fixtures';
import type { Manifest } from '@/api/backendSchemas';

const now = new Date().toISOString();
const initialManifest = {
  schemaVersion: 2 as const,
  name: 'Production Network Baseline',
  description: 'Reviewed v2 topology for the bundled three-tier fixture.',
  components: [
    { id: 'web', resourceTypes: ['AWS::EC2::Instance'], selector: { resourceIds: ['i-fixture-web'] }, minMatches: 1 },
    { id: 'api', resourceTypes: ['AWS::EC2::Instance'], selector: { resourceIds: ['i-fixture-api'] }, minMatches: 1 },
    { id: 'worker', resourceTypes: ['AWS::Lambda::Function'], selector: { resourceIds: ['fixture-worker'] }, minMatches: 1 },
    { id: 'db', resourceTypes: ['AWS::RDS::DBInstance'], selector: { resourceIds: ['fixture-db'] }, minMatches: 1 },
  ],
  relationships: [
    { id: 'web-api', from: 'web', to: 'api', effect: 'ALLOW', relationshipType: 'NETWORK_REACHABILITY', protocol: 'tcp', ports: [443], required: true },
    { id: 'api-db', from: 'api', to: 'db', effect: 'ALLOW', relationshipType: 'NETWORK_REACHABILITY', protocol: 'tcp', ports: [5432], required: true },
  ],
  trustBoundaries: [
    { id: 'edge', members: ['web'], crossingRules: [{ id: 'web-service', to: 'services', effect: 'ALLOW', via: ['api'] }] },
    { id: 'services', members: ['api', 'worker'], crossingRules: [{ id: 'service-data', to: 'data', effect: 'ALLOW', via: ['api'] }] },
    { id: 'data', members: ['db'], crossingRules: [] },
  ],
  criticality: { db: 'CRITICAL', api: 'HIGH', web: 'MEDIUM', worker: 'MEDIUM' },
  constraints: [
    { id: 'ssh', type: 'SECURITY_GROUP_NO_OPEN_SSH', severity: 'HIGH', description: 'SSH must not be publicly reachable.', enabled: true },
    { id: 'no-direct-worker-db', type: 'FORBIDDEN_PATH', from: 'worker', to: 'db', pathMode: 'DIRECT', edgeTypes: ['NETWORK_REACHABILITY'], severity: 'HIGH', description: 'The worker cannot connect directly to the database.', enabled: true },
    { id: 'worker-via-api', type: 'REQUIRED_INTERMEDIARY', from: 'worker', to: 'db', via: ['api'], edgeTypes: ['NETWORK_REACHABILITY'], severity: 'HIGH', description: 'Database access from the worker must pass through the API.', enabled: true },
  ],
} satisfies Pick<Manifest, 'schemaVersion' | 'name' | 'description' | 'components' | 'relationships' | 'trustBoundaries' | 'criticality' | 'constraints'>;
let mockManifest: Manifest = {
  intentId: 'int-prod-net-01',
  version: 2, status: 'APPROVED', createdAt: now, updatedAt: now,
  approvedAt: now, createdBy: 'local-fixture', sourceType: 'JSON',
  ...initialManifest,
  activeVersion: 2, latestVersion: 2, revision: 2,
};
type MockVersion = Manifest & { contentHash: string; parentVersion?: number };
const snapshot = (manifest: Manifest, version: number, parentVersion?: number): MockVersion => ({
  ...structuredClone(manifest), version, contentHash: `local-fixture-content-${version}`,
  ...(parentVersion ? { parentVersion } : {}),
});
let mockVersions: MockVersion[] = [
  snapshot({ ...mockManifest, relationships: mockManifest.relationships?.filter((row) => row.id !== 'web-api') }, 1),
  snapshot(mockManifest, 2, 1),
];

function diffSection(before: unknown[] = [], after: unknown[] = []) {
  const key = (row: unknown) => String((row as { id?: unknown })?.id ?? '');
  const oldRows = new Map(before.map((row) => [key(row), row]));
  const newRows = new Map(after.map((row) => [key(row), row]));
  return {
    added: [...newRows].filter(([id]) => !oldRows.has(id)).map(([id, value]) => ({ id, value })),
    removed: [...oldRows].filter(([id]) => !newRows.has(id)).map(([id, value]) => ({ id, value })),
    changed: [...newRows].filter(([id, value]) => oldRows.has(id) && JSON.stringify(oldRows.get(id)) !== JSON.stringify(value))
      .map(([id, afterValue]) => ({ id, before: oldRows.get(id), after: afterValue })),
  };
}

function diffCriticality(before: Record<string, unknown> = {}, after: Record<string, unknown> = {}) {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  return {
    added: [...keys].filter((id) => !(id in before)).map((id) => ({ id, value: after[id] })),
    removed: [...keys].filter((id) => !(id in after)).map((id) => ({ id, value: before[id] })),
    changed: [...keys].filter((id) => id in before && id in after && before[id] !== after[id])
      .map((id) => ({ id, before: before[id], after: after[id] })),
  };
}
let currentMockEvaluation = { ...mockEvaluation };

function mockAudit(action: string, target: unknown, result: string, metadata: Record<string, unknown> = {}) {
  mockAuditEvents.unshift({
    auditId: `aud-local-${Date.now()}`,
    timestamp: new Date().toISOString(),
    actor: { sub: 'local-fixture-admin', displayName: 'Local fixture administrator' },
    action,
    target,
    result,
    requestId: `local-request-${Date.now()}`,
    scopeKey: 'local:us-east-1:fixture',
    metadata,
  });
}

function mockApiError(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status });
}

export const handlers = [
  // System Status
  http.get('/v1/system/status', async () => {
    await delay(120);
    return HttpResponse.json(mockSystemStatus);
  }),

  // Dashboard Summary
  http.get('/v1/dashboard/summary', async () => {
    await delay(150);
    return HttpResponse.json(mockDashboardSummary);
  }),

  // Findings List
  http.get('/v1/findings', async ({ request }) => {
    await delay(150);
    const url = new URL(request.url);
    const severity = url.searchParams.get('severity');
    const status = url.searchParams.get('status');
    const search = url.searchParams.get('q');

    let items = [...mockFindings];
    if (severity) {
      items = items.filter((f) => f.severity === severity);
    }
    if (status) {
      items = items.filter((f) => f.status === status);
    }
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (f) =>
          f.title.toLowerCase().includes(q) ||
          f.resourceId.toLowerCase().includes(q) ||
          f.ruleId.toLowerCase().includes(q)
      );
    }

    return HttpResponse.json({
      items,
      meta: { nextCursor: null, totalCount: items.length },
    });
  }),

  // Finding Detail
  http.get('/v1/findings/:id', async ({ params }) => {
    await delay(100);
    const found = mockFindings.find((f) => f.id === params.id);
    if (!found) {
      return new HttpResponse(JSON.stringify({ message: 'Finding not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return HttpResponse.json(found);
  }),

  // Acknowledge Finding
  http.patch('/v1/findings/:id', async ({ params, request }) => {
    await delay(200);
    const body = (await request.json()) as { action: 'ACKNOWLEDGE' | 'SUPPRESS' | 'REOPEN'; reason?: string; expectedRevision: number };
    const item = mockFindings.find((f) => f.id === params.id);
    if (item) {
      if (item.revision !== body.expectedRevision) return HttpResponse.json({ message: 'Revision conflict' }, { status: 409 });
      item.status = body.action === 'ACKNOWLEDGE' ? 'ACKNOWLEDGED' : body.action === 'SUPPRESS' ? 'SUPPRESSED' : 'OPEN';
      item.revision = (item.revision || 0) + 1;
      item.updatedAt = new Date().toISOString();
      return HttpResponse.json({ item: {
        findingId: item.id,
        title: item.title,
        ruleId: item.ruleId,
        description: item.description,
        severity: item.severity,
        status: item.status,
        resourceId: item.resourceId,
        resourceType: item.resourceType,
        region: item.region,
        firstSeenAt: item.detectedAt,
        updatedAt: item.updatedAt,
        revision: item.revision,
        remediationAvailable: false,
      } });
    }
    return HttpResponse.json({ message: 'Finding not found' }, { status: 404 });
  }),

  // Generate AI Explanation
  http.post('/v1/findings/:id/ai-explanation', async () => {
    await delay(500);
    return HttpResponse.json({
      summary: 'AI-assisted architectural drift analysis generated.',
      rationale: 'The resource configuration deviates from baseline intent parameters for network ingress controls.',
      citedEvidence: ['CloudTrail event log: ModifySecurityGroupRules', 'Intent baseline spec v2.1'],
    });
  }),

  // Architecture Graph
  http.get('/v1/architecture/graph', async ({ request }) => {
    await delay(200);
    const url = new URL(request.url);
    const view = (url.searchParams.get('view') || 'DIFF') as 'DIFF' | 'INTENT' | 'ACTUAL';
    return HttpResponse.json({
      ...mockArchitectureGraph,
      view,
    });
  }),

  // Intents List
  http.get('/v1/intents', async ({ request }) => {
    await delay(120);
    const url = new URL(request.url);
    return HttpResponse.json({
      items: [mockManifest], nextToken: null, count: 1,
      limit: Number(url.searchParams.get('limit') || 25),
    });
  }),

  // Intent Detail
  http.get('/v1/intents/:id', async ({ params }) => {
    await delay(100);
    if (params.id !== mockManifest.intentId) return HttpResponse.json({ message: 'Intent not found' }, { status: 404 });
    return HttpResponse.json({ item: mockManifest });
  }),

  http.post('/v1/intents', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    mockManifest = {
      ...mockManifest,
      ...body,
      intentId: `local-intent-${Date.now()}`,
      version: 1,
      status: 'DRAFT',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      approvedAt: null,
      createdBy: 'local-fixture',
      sourceType: 'JSON',
      activeVersion: null,
      latestVersion: 1,
      revision: 1,
    } as Manifest;
    mockVersions = [snapshot({ ...mockManifest, status: 'DRAFT' }, 1)];
    return HttpResponse.json({ item: mockManifest }, { status: 201 });
  }),

  http.post('/v1/intents/:id/approve', async ({ params }) => {
    if (params.id !== mockManifest.intentId) return HttpResponse.json({ message: 'Intent not found' }, { status: 404 });
    mockManifest = { ...mockManifest, status: 'APPROVED', approvedAt: new Date().toISOString(), activeVersion: mockManifest.version, revision: (mockManifest.revision || 0) + 1 };
    mockVersions = mockVersions.map((version) => ({ ...version, status: version.version === mockManifest.version ? 'APPROVED' : version.status }));
    return HttpResponse.json({ item: mockManifest });
  }),

  http.get('/v1/intents/:id/versions', async ({ params, request }) => {
    if (params.id !== mockManifest.intentId) return HttpResponse.json({ message: 'Intent not found' }, { status: 404 });
    const url = new URL(request.url);
    return HttpResponse.json({ items: mockVersions, nextToken: null, count: mockVersions.length, limit: Number(url.searchParams.get('limit') || 25) });
  }),

  http.post('/v1/intents/:id/versions', async ({ params, request }) => {
    if (params.id !== mockManifest.intentId) return HttpResponse.json({ message: 'Intent not found' }, { status: 404 });
    const body = await request.json() as { manifest: Record<string, unknown>; expectedRevision: number };
    if (body.expectedRevision !== mockManifest.revision) return HttpResponse.json({ message: 'Revision conflict' }, { status: 409 });
    const version = (mockManifest.latestVersion || mockManifest.version) + 1;
    const content = snapshot({ ...mockManifest, ...body.manifest, status: 'DRAFT' as const, updatedAt: new Date().toISOString() } as Manifest, version, version - 1);
    mockVersions = [...mockVersions, content];
    mockManifest = { ...mockManifest, latestVersion: version, revision: (mockManifest.revision || 0) + 1 };
    return HttpResponse.json({ item: content }, { status: 201 });
  }),

  http.get('/v1/intents/:id/versions/:version', async ({ params }) => {
    const item = mockVersions.find((version) => version.version === Number(params.version));
    return item ? HttpResponse.json({ item }) : HttpResponse.json({ message: 'Version not found' }, { status: 404 });
  }),

  http.post('/v1/intents/:id/versions/:version/approve', async ({ params, request }) => {
    const body = await request.json() as { expectedRevision: number };
    const versionNumber = Number(params.version);
    if (body.expectedRevision !== mockManifest.revision) return HttpResponse.json({ message: 'Revision conflict' }, { status: 409 });
    const item = mockVersions.find((version) => version.version === versionNumber);
    if (!item) return HttpResponse.json({ message: 'Version not found' }, { status: 404 });
    if (item.status !== 'DRAFT') return HttpResponse.json({ message: 'Only draft versions can be approved' }, { status: 409 });
    const approvedAt = new Date().toISOString();
    const approved = { ...item, status: 'APPROVED' as const, approvedAt };
    mockManifest = { ...approved, activeVersion: versionNumber, latestVersion: mockManifest.latestVersion, revision: (mockManifest.revision || 0) + 1 };
    mockVersions = mockVersions.map((version) => version.version === versionNumber ? approved : version);
    return HttpResponse.json({ item: approved });
  }),

  http.post('/v1/intents/:id/rollback', async ({ params, request }) => {
    const body = await request.json() as { targetVersion: number; expectedRevision: number; reason: string };
    if (params.id !== mockManifest.intentId) return HttpResponse.json({ message: 'Intent not found' }, { status: 404 });
    if (body.expectedRevision !== mockManifest.revision) return HttpResponse.json({ message: 'Revision conflict' }, { status: 409 });
    const item = mockVersions.find((version) => version.version === body.targetVersion && version.status === 'APPROVED');
    if (!item) return HttpResponse.json({ message: 'Approved version not found' }, { status: 404 });
    mockManifest = { ...item, status: 'APPROVED', activeVersion: item.version, latestVersion: mockManifest.latestVersion, revision: (mockManifest.revision || 0) + 1 };
    return HttpResponse.json({ item: mockManifest });
  }),

  http.get('/v1/intents/:id/diff', async ({ params, request }) => {
    const url = new URL(request.url);
    const fromVersion = Number(url.searchParams.get('fromVersion'));
    const toVersion = Number(url.searchParams.get('toVersion'));
    const before = mockVersions.find((version) => version.version === fromVersion);
    const after = mockVersions.find((version) => version.version === toVersion);
    if (!before || !after) return HttpResponse.json({ message: 'Version not found' }, { status: 404 });
    return HttpResponse.json({ item: {
      intentId: String(params.id), fromVersion, toVersion,
      components: diffSection(before.components, after.components),
      relationships: diffSection(before.relationships, after.relationships),
      trustBoundaries: diffSection(before.trustBoundaries, after.trustBoundaries),
      criticality: diffCriticality(before.criticality, after.criticality),
      constraints: diffSection(before.constraints, after.constraints),
    } });
  }),

  // Drift Events
  http.get('/v1/drift-events', async () => {
    await delay(150);
    return HttpResponse.json({
      items: mockDriftEvents,
      meta: { nextCursor: null },
    });
  }),

  // Remediations List
  http.get('/v1/remediations', async ({ request }) => {
    await delay(120);
    const url = new URL(request.url);
    const status = url.searchParams.get('status');
    let items = [...mockRemediations];
    if (status && status !== 'ALL') {
      items = items.filter((r) => r.status === status);
    }
    const limit = Number(url.searchParams.get('limit') || 25);
    return HttpResponse.json({
      items,
      count: items.length,
      nextToken: null,
      limit,
    });
  }),

  http.get('/v1/remediations/:id', async ({ params }) => {
    await delay(100);
    const item = mockRemediations.find((row) => row.proposalId === params.id);
    if (!item) return mockApiError(404, 'PROPOSAL_NOT_FOUND', 'No proposal exists in this scope.');
    return HttpResponse.json({ item });
  }),

  http.post('/v1/remediations', async ({ request }) => {
    await delay(250);
    const body = (await request.json()) as { findingId: string; actionId: 'REMOVE_OPEN_SSH' | 'ENABLE_S3_BLOCK_PUBLIC_ACCESS' };
    const finding = mockFindings.find((row) => row.id === body.findingId);
    if (!finding || !finding.remediationAvailable || finding.remediationActionId !== body.actionId || finding.tier === 'TIER_2') {
      return mockApiError(409, 'ACTION_NOT_ELIGIBLE', 'This finding is not eligible for that registry action.');
    }
    if (!finding.resourceId || !finding.resourceType) return mockApiError(409, 'ACTION_NOT_ELIGIBLE', 'The finding does not include a supported resource.');
    const now = new Date().toISOString();
    const sshPlan = body.actionId === 'REMOVE_OPEN_SSH';
    const item = {
      proposalId: `rem-${Date.now()}`,
      findingId: finding.id,
      actionId: body.actionId,
      status: 'PROPOSED' as const,
      revision: 1,
      dryRun: true,
      createdAt: now,
      expiresAt: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
      createdBy: { sub: 'local-fixture-admin', role: 'admin', displayName: 'Local fixture administrator' },
      resourceId: finding.resourceId,
      resourceType: finding.resourceType,
      plan: sshPlan
        ? { before: { publicSshPermissions: [{ IpProtocol: 'tcp', FromPort: 22, ToPort: 22, IpRanges: [{ CidrIp: '0.0.0.0/0' }] }] }, after: { publicSshPermissions: [] }, rollback: { operation: 'authorize_security_group_ingress', permissions: [{ IpProtocol: 'tcp', FromPort: 22, ToPort: 22, IpRanges: [{ CidrIp: '0.0.0.0/0' }] }] }, description: 'Revoke only the evidenced public CIDR ingress permissions that include SSH.' }
        : { before: { blockPublicAccess: false }, after: { blockPublicAccess: true }, rollback: { blockPublicAccess: false }, description: 'Enable all S3 Block Public Access settings for this bucket.' },
      approvalRequired: true,
    };
    mockRemediations.unshift(item);
    mockAudit('REMEDIATION_PROPOSED', { type: 'REMEDIATION', id: item.proposalId }, 'RECORDED', { findingId: item.findingId, actionId: item.actionId, status: item.status });
    return HttpResponse.json({ item }, { status: 201 });
  }),

  http.post('/v1/remediations/:id/approve', async ({ params, request }) => {
    await delay(250);
    const body = (await request.json()) as { expectedRevision: number; reason: string };
    const item = mockRemediations.find((row) => row.proposalId === params.id);
    if (!item) return mockApiError(404, 'PROPOSAL_NOT_FOUND', 'No proposal exists in this scope.');
    if (item.revision !== body.expectedRevision) return mockApiError(409, 'STATE_CONFLICT', 'The proposal changed; refresh it.');
    if (Date.parse(item.expiresAt) <= Date.now()) return mockApiError(409, 'PROPOSAL_EXPIRED', 'This proposal expired; create a fresh proposal.');
    if (typeof body.reason !== 'string' || body.reason.trim().length < 1 || body.reason.trim().length > 1000) return mockApiError(400, 'APPROVAL_REASON_REQUIRED', 'Human approval requires a reason of 1-1000 characters.');
    if (item.status !== 'PROPOSED') return mockApiError(409, 'STATE_CONFLICT', 'Only a proposed action can be approved.');
    item.status = 'APPROVED';
    item.revision += 1;
    item.approvedAt = new Date().toISOString();
    item.approvedBy = { sub: 'local-fixture-admin', role: 'admin', displayName: 'Local fixture administrator' };
    item.reason = body.reason.trim();
    mockAudit('REMEDIATION_APPROVED', { type: 'REMEDIATION', id: item.proposalId }, 'RECORDED', { findingId: item.findingId, actionId: item.actionId, status: item.status });
    return HttpResponse.json({ item });
  }),

  http.post('/v1/remediations/:id/execute', async ({ params, request }) => {
    await delay(250);
    const body = (await request.json()) as { expectedRevision: number };
    const item = mockRemediations.find((row) => row.proposalId === params.id);
    if (!item) return mockApiError(404, 'PROPOSAL_NOT_FOUND', 'No proposal exists in this scope.');
    if (item.revision !== body.expectedRevision) return mockApiError(409, 'STATE_CONFLICT', 'The proposal changed; refresh it.');
    if (Date.parse(item.expiresAt) <= Date.now()) return mockApiError(409, 'PROPOSAL_EXPIRED', 'This proposal expired; create a fresh proposal.');
    if (item.status !== 'APPROVED' || !item.approvedBy) return mockApiError(409, 'APPROVAL_REQUIRED', 'Explicit human approval is required before execution.');
    item.revision += 1;
    item.status = 'EXECUTING';
    item.status = 'DRY_RUN_COMPLETE';
    item.revision += 1;
    item.execution = { dryRun: true, status: 'DRY_RUN_COMPLETE', completedAt: new Date().toISOString() };
    mockAudit('REMEDIATION_DRY_RUN_COMPLETE', { type: 'REMEDIATION', id: item.proposalId }, 'RECORDED', { findingId: item.findingId, actionId: item.actionId, status: item.status });
    return HttpResponse.json({ item });
  }),

  // Audit Events
  http.get('/v1/audit', async ({ request }) => {
    await delay(120);
    const url = new URL(request.url);
    return HttpResponse.json({
      items: mockAuditEvents,
      count: mockAuditEvents.length,
      nextToken: null,
      limit: Number(url.searchParams.get('limit') || 25),
    });
  }),

  // Evaluations trigger
  http.post('/v1/evaluations', async () => {
    await delay(300);
    currentMockEvaluation = { ...mockEvaluation, createdAt: new Date().toISOString() };
    return HttpResponse.json({ evaluation: {
      evaluationId: currentMockEvaluation.evaluationId,
      status: 'QUEUED',
      intentId: currentMockEvaluation.intentId,
      intentVersion: currentMockEvaluation.intentVersion,
      createdAt: currentMockEvaluation.createdAt,
    }, statusUrl: `/v1/evaluations/${currentMockEvaluation.evaluationId}` }, { status: 202 });
  }),

  // Evaluation detail and history
  http.get('/v1/evaluations/:id', async ({ params }) => {
    await delay(100);
    if (params.id !== currentMockEvaluation.evaluationId) return HttpResponse.json({ message: 'Evaluation not found' }, { status: 404 });
    return HttpResponse.json({ item: currentMockEvaluation });
  }),
  http.get('/v1/evaluations', async ({ request }) => {
    await delay(100);
    const url = new URL(request.url);
    return HttpResponse.json({ items: [currentMockEvaluation], count: 1, nextToken: null, limit: Number(url.searchParams.get('limit') || 25) });
  }),
];
