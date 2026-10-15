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
let mockManifest: Manifest = {
  intentId: 'int-prod-net-01', name: 'Production Network Baseline',
  description: 'Reviewed v2 architecture declarations for the local fixture scope.',
  version: 2, status: 'APPROVED', createdAt: now, updatedAt: now,
  approvedAt: now, createdBy: 'local-fixture', sourceType: 'JSON', schemaVersion: 2,
  components: [{ id: 'network', resourceTypes: ['AWS::EC2::VPC'], selector: { tags: { 'cig:tier': 'network' } }, minMatches: 1 }],
  relationships: [{ id: 'network-api', from: 'network', to: 'api', effect: 'ALLOW', relationshipType: 'CONTAINS' }],
  trustBoundaries: [{ id: 'production', members: ['network', 'api'] }],
  criticality: { network: 'HIGH' },
  constraints: [{ id: 'no-open-ssh', type: 'SECURITY_GROUP_NO_OPEN_SSH', severity: 'HIGH', description: 'SSH must not be public.', enabled: true }],
  activeVersion: 2, latestVersion: 2, revision: 2,
};
let mockVersions: Manifest[] = [
  { ...mockManifest, version: 1, status: 'APPROVED' },
  { ...mockManifest, version: 2, status: 'APPROVED' },
];
let currentMockEvaluation = { ...mockEvaluation };

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
    mockVersions = [{ ...mockManifest, status: 'DRAFT' }];
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
    const content = { ...mockManifest, ...body.manifest, version, status: 'DRAFT' as const, updatedAt: new Date().toISOString() };
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
    mockManifest = { ...item, status: 'APPROVED', activeVersion: versionNumber, revision: (mockManifest.revision || 0) + 1, approvedAt: new Date().toISOString() };
    mockVersions = mockVersions.map((version) => ({ ...version, status: version.version === versionNumber ? 'APPROVED' : version.status }));
    return HttpResponse.json({ item: mockVersions.find((version) => version.version === versionNumber) });
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
    return HttpResponse.json({ item: {
      intentId: String(params.id), fromVersion: Number(url.searchParams.get('fromVersion')),
      toVersion: Number(url.searchParams.get('toVersion')),
      components: { added: [], removed: [], changed: [] }, relationships: { added: [], removed: [], changed: [] },
      trustBoundaries: { added: [], removed: [], changed: [] }, criticality: { added: [], removed: [], changed: [] },
      constraints: { added: [], removed: [], changed: [] },
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
    if (!item) return HttpResponse.json({ message: 'Proposal not found' }, { status: 404 });
    return HttpResponse.json({ item });
  }),

  http.post('/v1/remediations', async ({ request }) => {
    await delay(250);
    const body = (await request.json()) as { findingId: string; actionId: 'REMOVE_OPEN_SSH' | 'ENABLE_S3_BLOCK_PUBLIC_ACCESS' };
    const finding = mockFindings.find((row) => row.id === body.findingId);
    if (!finding || !finding.remediationAvailable || finding.remediationActionId !== body.actionId || finding.tier === 'TIER_2') {
      return HttpResponse.json({ message: 'Finding is not eligible for this action' }, { status: 409 });
    }
    const now = new Date().toISOString();
    const item = {
      proposalId: `rem-${Date.now()}`,
      findingId: finding.id,
      actionId: body.actionId,
      status: 'PROPOSED' as const,
      revision: 1,
      dryRun: true,
      createdAt: now,
      expiresAt: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
      createdBy: { sub: 'local-user', role: 'operator', displayName: 'Local fixture user' },
      resourceId: finding.resourceId,
      resourceType: finding.resourceType,
      plan: { before: {}, after: {}, rollback: {}, description: 'Local simulated proposal; no cloud action was performed.' },
    };
    mockRemediations.unshift(item);
    return HttpResponse.json({ item }, { status: 201 });
  }),

  http.post('/v1/remediations/:id/approve', async ({ params, request }) => {
    await delay(250);
    const body = (await request.json()) as { expectedRevision: number; reason: string };
    const item = mockRemediations.find((row) => row.proposalId === params.id);
    if (!item) return HttpResponse.json({ message: 'Proposal not found' }, { status: 404 });
    if (item.revision !== body.expectedRevision) return HttpResponse.json({ message: 'Revision conflict' }, { status: 409 });
    item.status = 'APPROVED';
    item.revision += 1;
    item.approvedAt = new Date().toISOString();
    item.approvedBy = { sub: 'local-approver', role: 'approver', displayName: 'Local fixture approver' };
    item.reason = body.reason;
    return HttpResponse.json({ item });
  }),

  http.post('/v1/remediations/:id/execute', async ({ params, request }) => {
    await delay(250);
    const body = (await request.json()) as { expectedRevision: number };
    const item = mockRemediations.find((row) => row.proposalId === params.id);
    if (!item) return HttpResponse.json({ message: 'Proposal not found' }, { status: 404 });
    if (item.revision !== body.expectedRevision) return HttpResponse.json({ message: 'Revision conflict' }, { status: 409 });
    if (item.status !== 'APPROVED') return HttpResponse.json({ message: 'Proposal must be approved before execution' }, { status: 409 });
    item.status = 'DRY_RUN_COMPLETE';
    item.revision += 1;
    item.execution = { dryRun: true, status: 'COMPLETED', completedAt: new Date().toISOString() };
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
