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
const topology = JSON.parse(
  readFileSync(
    new URL("./fixtures/topology-contract.json", import.meta.url),
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
test("v2 manifest declarations survive response parsing intact", () => {
  const item = B.ManifestSchema.parse({
    ...wire.created.item,
    schemaVersion: 2,
    components: [{
      id: "worker",
      resourceTypes: ["AWS::Lambda::Function"],
      selector: { tags: { "cig:tier": "worker" } },
      minMatches: 0,
    }],
    relationships: [{
      id: "worker-db",
      from: "worker",
      to: "database",
      effect: "DENY",
      relationshipType: "NETWORK_REACHABILITY",
      protocol: "tcp",
      ports: [5432],
    }],
    trustBoundaries: [{ id: "services", members: ["worker"] }],
    criticality: { worker: "HIGH" },
    constraints: [{
      id: "worker-db-bypass",
      type: "REQUIRED_INTERMEDIARY",
      severity: "HIGH",
      description: "A path must pass through the API tier.",
      enabled: true,
      from: "worker",
      to: "database",
      via: ["api-tier"],
      edgeTypes: ["NETWORK_REACHABILITY"],
    }],
  });
  assert.equal(item.schemaVersion, 2);
  assert.equal(item.components[0].selector.tags["cig:tier"], "worker");
  assert.equal(item.relationships[0].ports[0], 5432);
  assert.deepEqual(item.trustBoundaries[0].members, ["worker"]);
  assert.equal(item.criticality.worker, "HIGH");
  assert.deepEqual(item.constraints[0].via, ["api-tier"]);
});
test("generated v2 topology contract preserves declarations, graph metadata and simulation status", () => {
  const created = B.ManifestDetailSchema.parse(topology.created).item;
  const approved = B.ManifestDetailSchema.parse(topology.approved).item;
  assert.equal(created.schemaVersion, 2);
  assert.deepEqual(created.components.map((component) => component.id), approved.components.map((component) => component.id));

  const intentGraph = S.ArchitectureGraphSchema.parse(topology.intentGraph);
  const diffGraph = S.ArchitectureGraphSchema.parse(topology.diffGraph);
  assert.equal(intentGraph.view, "INTENT");
  assert.equal(diffGraph.view, "DIFF");
  assert.ok(intentGraph.nodes.some((node) => typeof node.componentId === "string"));
  assert.ok(intentGraph.nodes.some((node) => Array.isArray(node.resourceIds)));
  assert.ok(intentGraph.edges.some((edge) => typeof edge.declarationId === "string" && edge.effect === "ALLOW"));
  assert.ok(diffGraph.nodes.some((node) => Array.isArray(node.componentIds)));
  assert.ok(diffGraph.nodes.some((node) => typeof node.source === "string"));
  assert.ok(diffGraph.nodes.some((node) => typeof node.explanation === "string"));
  assert.ok(diffGraph.edges.some((edge) => edge.diffState === "UNEXPECTED"));
  assert.ok(diffGraph.edges.some((edge) => edge.observationKind === "OBSERVED"));
  assert.ok(diffGraph.coverage?.resourceTypes);
  assert.ok(diffGraph.coverage?.relationshipTypes);

  const simulated = topology.bypassEvaluation.simulated ?? topology.bypassEvaluation.evaluation?.simulated;
  assert.equal(simulated, true);
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
