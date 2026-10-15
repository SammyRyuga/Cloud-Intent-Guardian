import { z } from "zod";

// These validate the existing backend wire format before adapting names for the UI.
const ManifestConstraintSchema = z.object({
  id: z.string(),
  type: z.string(),
  severity: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
  description: z.string(),
  enabled: z.boolean(),
}).passthrough();

// v2 declarations are response data too. Keep their complete shape when parsing
// instead of reducing a server response to the legacy constraint facade.
const BoundedTopologyObjectSchema = z.record(z.unknown()).refine(
  (row) => Object.keys(row).length <= 100,
  "Topology objects may contain at most 100 fields",
);
export const ManifestSchema = z.object({
  intentId: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.number(),
  status: z.enum(["DRAFT", "APPROVED"]),
  createdAt: z.string(),
  updatedAt: z.string(),
  approvedAt: z.string().nullable(),
  activeVersion: z.number().nullable().optional(),
  latestVersion: z.number().nullable().optional(),
  revision: z.number().optional(),
  createdBy: z.string(),
  sourceType: z.string(),
  schemaVersion: z.union([z.literal(1), z.literal(2)]).optional(),
  components: z.array(BoundedTopologyObjectSchema).max(100).optional(),
  relationships: z.array(BoundedTopologyObjectSchema).max(250).optional(),
  trustBoundaries: z.array(BoundedTopologyObjectSchema).max(20).optional(),
  criticality: z.record(z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]))
    .refine((row) => Object.keys(row).length <= 100, "Criticality may contain at most 100 entries")
    .optional(),
  constraints: z.array(ManifestConstraintSchema).max(50),
}).passthrough();
export const ManifestDetailSchema = z.object({ item: ManifestSchema });
export const ManifestsSchema = z.object({
  items: z.array(ManifestSchema),
  nextToken: z.string().nullable(),
  count: z.number(),
  limit: z.number(),
});
export type Manifest = z.infer<typeof ManifestSchema>;

const VersionManifestSchema = z.object({
  intentId: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.number(),
  status: z.enum(["DRAFT", "APPROVED"]),
  effectiveStatus: z.enum(["DRAFT", "APPROVED", "SUPERSEDED"]).optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
  approvedAt: z.string().nullable().optional(),
  createdBy: z.string(),
  author: z.object({ sub: z.string(), displayName: z.string().optional() }).optional(),
  sourceType: z.string().optional(),
  schemaVersion: z.union([z.literal(1), z.literal(2)]).optional(),
  contentHash: z.string(),
  parentVersion: z.number().optional(),
  components: z.array(BoundedTopologyObjectSchema).max(100).optional(),
  relationships: z.array(BoundedTopologyObjectSchema).max(250).optional(),
  trustBoundaries: z.array(BoundedTopologyObjectSchema).max(20).optional(),
  criticality: z.record(z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]))
    .refine((row) => Object.keys(row).length <= 100, "Criticality may contain at most 100 entries")
    .optional(),
  constraints: z.array(ManifestConstraintSchema).max(50),
}).passthrough();
export const IntentVersionDetailSchema = z.object({ item: VersionManifestSchema });
export const IntentVersionsSchema = z.object({
  items: z.array(VersionManifestSchema),
  nextToken: z.string().nullable(),
  count: z.number(),
  limit: z.number(),
});
export const IntentDiffSchema = z.object({
  item: z.object({
    intentId: z.string(),
    fromVersion: z.number(),
    toVersion: z.number(),
    components: z.record(z.unknown()),
    relationships: z.record(z.unknown()),
    trustBoundaries: z.record(z.unknown()),
    criticality: z.record(z.unknown()),
    constraints: z.record(z.unknown()),
  }).passthrough(),
});
export type IntentVersion = z.infer<typeof VersionManifestSchema>;
export type IntentDiff = z.infer<typeof IntentDiffSchema>["item"];

export const BackendFindingSchema = z
  .object({
    findingId: z.string(),
    title: z.string(),
    ruleId: z.string(),
    description: z.string(),
    severity: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
    severityScore: z.number().optional(),
    severityFactors: z.object({
      formulaVersion: z.literal("1"),
      baseSeverity: z.object({ label: z.string(), points: z.number() }),
      componentCriticality: z.object({
        label: z.string(), points: z.number(), componentIds: z.array(z.string()), defaulted: z.boolean(),
      }),
      blastRadius: z.object({
        count: z.number(), points: z.number(), complete: z.boolean(),
        downstreamResourceIds: z.array(z.string()), explanation: z.string(),
      }),
      exposure: z.object({ label: z.string(), points: z.number(), explanation: z.string() }),
      confidence: z.object({ label: z.enum(["HIGH", "MEDIUM", "LOW"]), points: z.number(), explanation: z.string() }),
      explanation: z.string(),
    }).passthrough().optional(),
    confidence: z.enum(["HIGH", "MEDIUM", "LOW"]).optional(),
    constraintSeverity: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]).optional(),
    status: z.enum(["OPEN", "ACKNOWLEDGED", "RESOLVED", "SUPPRESSED"]),
    resourceId: z.string(),
    resourceType: z.string(),
    region: z.string(),
    firstSeenAt: z.string(),
    updatedAt: z.string(),
    revision: z.number().optional(),
    remediationAvailable: z.literal(false),
    evidence: z
      .array(
        z.object({
          source: z.string(),
          resourceId: z.string(),
          observedAt: z.string(),
          details: z.record(z.unknown()),
        }),
      )
      .optional(),
    observed: z.record(z.unknown()).optional(),
    expected: z.record(z.unknown()).optional(),
    explanation: z.string().optional(),
  })
  .transform((item) => ({
    ...item,
    id: item.findingId,
    detectedAt: item.firstSeenAt,
  }));
export const BackendFindingsSchema = z
  .object({
    items: z.array(BackendFindingSchema),
    nextToken: z.string().nullable(),
  })
  .transform((page) => ({
    items: page.items,
    meta: { nextCursor: page.nextToken },
  }));
export const BackendFindingDetailSchema = z
  .object({ item: BackendFindingSchema })
  .transform((result) => result.item);
export const EvaluationStatusSchema = z.enum(["QUEUED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED"]);
const EvaluationSummarySchema = z.object({
  resourceCount: z.number().optional(),
  violationsFound: z.number().optional(),
  resolvedFindings: z.number().optional(),
  inventoryPartial: z.boolean().optional(),
}).passthrough();
export const EvaluationSchema = z.object({
  evaluationId: z.string(),
  status: EvaluationStatusSchema,
  intentId: z.string().nullable().optional(),
  intentVersion: z.number().nullable().optional(),
  createdAt: z.string().optional(),
  startedAt: z.string().nullable().optional(),
  finishedAt: z.string().nullable().optional(),
  progressStage: z.string().nullable().optional(),
  summary: EvaluationSummarySchema.nullable().optional(),
  error: z.object({ code: z.string(), message: z.string() }).nullable().optional(),
}).passthrough();
export const EvaluationAcceptedSchema = z.object({
  evaluation: z.object({
    evaluationId: z.string(),
    status: z.literal("QUEUED"),
    intentId: z.string().nullable(),
    intentVersion: z.number().nullable(),
    createdAt: z.string(),
  }).passthrough(),
  statusUrl: z.string(),
});
export const EvaluationDetailSchema = z.object({ item: EvaluationSchema });
export const EvaluationsSchema = z.object({
  items: z.array(EvaluationSchema),
  count: z.number(),
  nextToken: z.string().nullable(),
  limit: z.number(),
});
export type Evaluation = z.infer<typeof EvaluationSchema>;
export type EvaluationAccepted = z.infer<typeof EvaluationAcceptedSchema>;

export const AuditEventSchema = z.object({
  auditId: z.string(),
  timestamp: z.string(),
  actor: z.object({ sub: z.string(), displayName: z.string().optional() }),
  action: z.string(),
  target: z.unknown(),
  result: z.string(),
  requestId: z.string(),
  evaluationId: z.string().optional(),
  scopeKey: z.string(),
  metadata: z.record(z.unknown()),
}).passthrough();
export const AuditEventsSchema = z.object({
  items: z.array(AuditEventSchema),
  count: z.number(),
  nextToken: z.string().nullable(),
  limit: z.number(),
});
export type AuditEvent = z.infer<typeof AuditEventSchema>;
export type AuditEvents = z.infer<typeof AuditEventsSchema>;

export const FindingLifecycleActionSchema = z.enum(["ACKNOWLEDGE", "SUPPRESS", "REOPEN"]);
export const FindingLifecycleResponseSchema = z.object({ item: BackendFindingSchema });
