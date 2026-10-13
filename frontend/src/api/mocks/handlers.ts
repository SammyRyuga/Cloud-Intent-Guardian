import { http, HttpResponse, delay } from 'msw';
import {
  mockSystemStatus,
  mockDashboardSummary,
  mockFindings,
  mockArchitectureGraph,
  mockIntents,
  mockDriftEvents,
  mockRemediations,
  mockAuditEvents,
  mockActiveJob,
} from './fixtures';

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
  http.patch('/v1/findings/:id/acknowledge', async ({ params }) => {
    await delay(200);
    const item = mockFindings.find((f) => f.id === params.id);
    if (item) {
      item.status = 'ACKNOWLEDGED';
    }
    return HttpResponse.json({ success: true, findingId: params.id });
  }),

  // Generate AI Explanation
  http.post('/v1/findings/:id/ai-explanation', async ({ params }) => {
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
  http.get('/v1/intents', async () => {
    await delay(120);
    return HttpResponse.json({
      items: mockIntents,
      meta: { nextCursor: null },
    });
  }),

  // Intent Detail
  http.get('/v1/intents/:id', async ({ params }) => {
    await delay(100);
    const intent = mockIntents.find((i) => i.id === params.id);
    if (!intent) {
      return new HttpResponse(JSON.stringify({ message: 'Intent not found' }), { status: 404 });
    }
    return HttpResponse.json(intent);
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
    return HttpResponse.json({
      items,
      meta: { nextCursor: null },
    });
  }),

  // Remediation Decision
  http.post('/v1/remediations/:id/decision', async ({ params, request }) => {
    await delay(250);
    const body = (await request.json()) as { decision: 'APPROVE' | 'REJECT'; note?: string };
    const item = mockRemediations.find((r) => r.id === params.id);
    if (item) {
      item.status = body.decision === 'APPROVE' ? 'APPROVED' : 'REJECTED';
      item.decisionNote = body.note;
    }
    return HttpResponse.json({ success: true, remediationId: params.id });
  }),

  // Audit Events
  http.get('/v1/audit-events', async () => {
    await delay(120);
    return HttpResponse.json({
      items: mockAuditEvents,
      meta: { nextCursor: null },
    });
  }),

  // Evaluations trigger
  http.post('/v1/evaluations', async () => {
    await delay(300);
    return HttpResponse.json({
      jobId: 'job-' + Math.floor(Math.random() * 10000),
      message: 'Evaluation queued successfully',
      status: 'PENDING',
    });
  }),

  // Job Status Polling
  http.get('/v1/jobs/:id', async ({ params }) => {
    await delay(100);
    return HttpResponse.json({
      ...mockActiveJob,
      jobId: params.id,
    });
  }),
];
