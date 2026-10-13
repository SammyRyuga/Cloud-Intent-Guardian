import test from 'node:test';
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
  ['audit events', schemas.AuditEventSchema.array(), fixtures.mockAuditEvents],
  ['evaluation job', schemas.JobStatusSchema, fixtures.mockActiveJob],
]) {
  test(`${name} mock fixture matches its response schema`, () => {
    schema.parse(value);
  });
}
