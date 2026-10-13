import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as B from "../src/api/backendSchemas.ts";
import * as S from "../src/api/schemas.ts";

// Generated from real Python handlers in the Moto contract test, not handwritten frontend responses.
const wire = JSON.parse(
  readFileSync(
    new URL("./fixtures/backend-contract.json", import.meta.url),
    "utf8",
  ),
);
test("created, listed and approved manifests keep their original backend IDs", () => {
  const created = B.ManifestDetailSchema.parse(wire.created).item;
  const listed = B.ManifestsSchema.parse(wire.intents);
  const approved = B.ManifestDetailSchema.parse(wire.approved).item;
  assert.equal(listed.items[0].intentId, created.intentId);
  assert.equal(approved.intentId, created.intentId);
  assert.equal(approved.status, "APPROVED");
});
test("finding adapter preserves IDs, observed timestamps and opaque pagination", () => {
  const list = S.FindingsResponseSchema.parse(
    B.BackendFindingsSchema.parse(wire.findings),
  );
  const detail = S.FindingSchema.parse(
    B.BackendFindingDetailSchema.parse(wire.finding),
  );
  assert.equal(list.items[0].id, wire.findings.items[0].findingId);
  assert.equal(detail.detectedAt, wire.finding.item.firstSeenAt);
  assert.equal(list.meta.nextCursor, wire.findings.nextToken);
  assert.equal(detail.remediationAvailable, false);
});
test("dashboard and local readiness parse without inventing unavailable features", () => {
  const dashboard = S.DashboardSummarySchema.parse(wire.dashboard);
  assert.equal(dashboard.totalFindings, 1);
  assert.equal(dashboard.openRemediations, null);
  assert.equal(
    S.SystemStatusSchema.parse(wire.status).awsSourcesConnected,
    false,
  );
});
test("synchronous evaluation maps to its actual stored evaluation identifier", () => {
  const result = B.EvaluationResultSchema.parse(wire.evaluation);
  assert.equal(result.id, wire.evaluation.evaluation.evaluationId);
  assert.equal(result.status, "SUCCEEDED");
  assert.equal(result.summary.violationsFound, 1);
});
