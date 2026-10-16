import test from 'node:test';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import * as fixtures from '../src/api/mocks/fixtures.ts';
import * as schemas from '../src/api/schemas.ts';
import * as backendSchemas from '../src/api/backendSchemas.ts';

for (const [name, schema, value] of [
  ['system status', schemas.SystemStatusSchema, fixtures.mockSystemStatus],
  ['dashboard', schemas.DashboardSummarySchema, fixtures.mockDashboardSummary],
  ['findings', schemas.FindingSchema.array(), fixtures.mockFindings],
  ['architecture', schemas.ArchitectureGraphSchema, fixtures.mockArchitectureGraph],
  ['intents', schemas.IntentSchema.array(), fixtures.mockIntents],
  ['drift events', schemas.DriftEventSchema.array(), fixtures.mockDriftEvents],
  ['audit events', schemas.AuditEventsResponseSchema, fixtures.mockAuditResponse],
  ['accepted evaluation', schemas.EvaluationAcceptedSchema, fixtures.mockEvaluationAccepted],
  ['evaluation detail', schemas.EvaluationDetailSchema, { item: fixtures.mockEvaluation }],
  ['evaluation history', schemas.EvaluationsResponseSchema, fixtures.mockEvaluationHistory],
]) {
  test(`${name} mock fixture matches its response schema`, () => {
    schema.parse(value);
  });
}

test('remediation mock fixture matches the backend proposal envelope', () => {
  backendSchemas.RemediationsSchema.parse({ items: fixtures.mockRemediations, count: fixtures.mockRemediations.length, nextToken: null });
});

test('architecture fixture includes Phase 1 classifications and optional transport fields', () => {
  const graph = schemas.ArchitectureGraphSchema.parse(fixtures.mockArchitectureGraph);
  assert.ok(graph.nodes.some((node) => node.diffState === 'UNEXPECTED'));
  assert.equal(graph.intentVersion, 2);
  assert.equal(graph.snapshotId, 'snapshot-fixture-2026-10-15');
  assert.equal(graph.edges.find((edge) => edge.id === 'e3')?.observationKind, 'OBSERVED');
  assert.equal(graph.simulated, true);
  assert.ok(graph.coverage.resourceTypes);
  assert.ok(graph.coverage.relationshipTypes);
});

test('evaluation states include every asynchronous terminal and polling status', () => {
  for (const status of ['QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED']) {
    schemas.EvaluationSchema.parse({ ...fixtures.mockEvaluation, status });
  }
});

test('drift snapshot provenance and opaque pagination survive contract parsing', () => {
  const result = schemas.DriftEventsResponseSchema.parse({ items: [fixtures.mockDriftEvents[0]], meta: { nextCursor: 'opaque-server-cursor' } });
  assert.equal(result.items[0].previousEvaluationId, 'evaluation-fixture-1');
  assert.equal(result.meta.nextCursor, 'opaque-server-cursor');
  assert.equal(result.items[0].simulated, true);
});

test('finding lifecycle request validates reason and optimistic revision', () => {
  const schema = backendSchemas.FindingLifecycleRequestSchema;
  assert.deepEqual(schema.parse({ action: 'SUPPRESS', expectedRevision: 0, reason: '  Reviewed scope  ' }), { action: 'SUPPRESS', expectedRevision: 0, reason: 'Reviewed scope' });
  for (const request of [
    { action: 'SUPPRESS', expectedRevision: 0, reason: '   ' },
    { action: 'SUPPRESS', expectedRevision: 0, reason: 'x'.repeat(1001) },
    { action: 'REOPEN', expectedRevision: -1 },
    { action: 'REOPEN', expectedRevision: 1.5 },
    { action: 'RESOLVE', expectedRevision: 0 },
  ]) assert.equal(schema.safeParse(request).success, false);
  schema.parse({ action: 'REOPEN', expectedRevision: 1 });
});

test('finding suppression provenance survives mock and backend schemas', () => {
  const provenance = { suppressionReason: 'Reviewed monitoring scope.', suppressedAt: '2026-10-16T00:00:00Z', suppressedBy: 'approver-test', revision: 2, status: 'SUPPRESSED' };
  const mock = schemas.FindingSchema.parse({ ...fixtures.mockFindings[0], ...provenance });
  const live = backendSchemas.FindingLifecycleResponseSchema.parse({ item: { ...fixtures.mockFindings[0], findingId: fixtures.mockFindings[0].id, firstSeenAt: fixtures.mockFindings[0].detectedAt, ...provenance } }).item;
  assert.equal(live.suppressionReason, mock.suppressionReason);
  assert.equal(live.suppressedBy, 'approver-test');
  assert.equal(live.revision, 2);
});

// Actual local Python handler responses: activation returns the mutable intent facade.
test('version approval and rollback envelopes are intent facades, not immutable snapshots', () => {
  const wire = JSON.parse(readFileSync(new URL('./fixtures/version-decisions-contract.json', import.meta.url), 'utf8'));
  for (const operation of ['approved', 'rolledBack']) {
    const item = backendSchemas.ManifestDetailSchema.parse(wire[operation]).item;
    assert.equal(item.status, 'APPROVED');
    assert.equal(item.activeVersion, item.version);
    assert.equal('contentHash' in wire[operation].item, false);
    assert.equal(backendSchemas.IntentVersionDetailSchema.safeParse(wire[operation]).success, false);
  }
  backendSchemas.IntentVersionDetailSchema.parse(wire.draftVersion);
});
