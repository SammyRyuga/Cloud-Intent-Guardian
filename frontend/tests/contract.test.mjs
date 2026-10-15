import test from 'node:test';
import assert from 'node:assert/strict';
import * as fixtures from '../src/api/mocks/fixtures.ts';
import * as schemas from '../src/api/schemas.ts';

for (const [name, schema, value] of [
  ['system status', schemas.SystemStatusSchema, fixtures.mockSystemStatus],
  ['dashboard', schemas.DashboardSummarySchema, fixtures.mockDashboardSummary],
  ['findings', schemas.FindingSchema.array(), fixtures.mockFindings],
  ['architecture', schemas.ArchitectureGraphSchema, fixtures.mockArchitectureGraph],
  ['intents', schemas.IntentSchema.array(), fixtures.mockIntents],
  ['drift events', schemas.DriftEventSchema.array(), fixtures.mockDriftEvents],
  ['remediation', schemas.RemediationRequestSchema.array(), fixtures.mockRemediations],
  ['audit events', schemas.AuditEventsResponseSchema, fixtures.mockAuditResponse],
  ['accepted evaluation', schemas.EvaluationAcceptedSchema, fixtures.mockEvaluationAccepted],
  ['evaluation detail', schemas.EvaluationDetailSchema, { item: fixtures.mockEvaluation }],
  ['evaluation history', schemas.EvaluationsResponseSchema, fixtures.mockEvaluationHistory],
]) {
  test(`${name} mock fixture matches its response schema`, () => {
    schema.parse(value);
  });
}

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
