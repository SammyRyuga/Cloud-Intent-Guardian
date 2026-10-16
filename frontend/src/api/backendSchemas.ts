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
const IntentDiffEntrySchema = z.object({
  id: z.string(),
  value: z.unknown().optional(),
  before: z.unknown().optional(),
  after: z.unknown().optional(),
}).passthrough();
const IntentDiffSectionSchema = z.object({
  added: z.array(IntentDiffEntrySchema),
  removed: z.array(IntentDiffEntrySchema),
  changed: z.array(IntentDiffEntrySchema),
});
export const IntentDiffSchema = z.object({
  item: z.object({
    intentId: z.string(),
    fromVersion: z.number(),
    toVersion: z.number(),
    components: IntentDiffSectionSchema,
    relationships: IntentDiffSectionSchema,
    trustBoundaries: IntentDiffSectionSchema,
    criticality: IntentDiffSectionSchema,
    constraints: IntentDiffSectionSchema,
  }).passthrough(),
});
export type IntentVersion = z.infer<typeof VersionManifestSchema>;
export type IntentDiff = z.infer<typeof IntentDiffSchema>["item"];

export const RemediationActionIdSchema = z.enum(["REMOVE_OPEN_SSH", "ENABLE_S3_BLOCK_PUBLIC_ACCESS"]);
export const CrossValidationSchema = z.object({
  accepted: z.boolean(),
  simulated: z.boolean().optional(),
  sourceVerdicts: z.array(z.object({
    sourceFamily: z.string(),
    verdict: z.string(),
    evidenceId: z.string(),
    originId: z.string().optional(),
    predicate: z.string(),
    sourceId: z.string().optional(),
    targetId: z.string().optional(),
    snapshotId: z.string().optional(),
    observedAt: z.string(),
    eligible: z.boolean().optional(),
  }).passthrough()),
  reason: z.string(),
}).passthrough();
export const LlmConclusionSchema = z.object({
  candidateId: z.string(),
  verdict: z.enum(["CONCERN", "BENIGN", "UNCERTAIN"]),
  explanation: z.string(),
});
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
    tier: z.literal("TIER_2").optional(),
    reviewStatus: z.enum(["NEEDS_HUMAN_REVIEW", "CORROBORATED"]).optional(),
    crossValidation: CrossValidationSchema.optional(),
    llmConclusion: LlmConclusionSchema.nullable().optional(),
    status: z.enum(["OPEN", "ACKNOWLEDGED", "RESOLVED", "SUPPRESSED"]),
    resourceId: z.string(),
    resourceType: z.string(),
    region: z.string(),
    firstSeenAt: z.string(),
    updatedAt: z.string(),
    revision: z.number().optional(),
    remediationAvailable: z.boolean(),
    remediationActionId: RemediationActionIdSchema.optional(),
    actionEligible: z.boolean().optional(),
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
  ruleResults: z.array(z.object({ ruleId: z.string(), outcome: z.string(), explanation: z.string().optional() }).passthrough()).optional(),
  warnings: z.array(z.object({ source: z.string().optional(), code: z.string().optional(), message: z.string() })).optional(),
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

export const RemediationItemSchema = z.object({
  proposalId: z.string(),
  findingId: z.string(),
  actionId: RemediationActionIdSchema,
  status: z.enum(["PROPOSED", "APPROVED", "EXECUTING", "EXECUTED", "DRY_RUN_COMPLETE", "FAILED"]),
  revision: z.number(),
  dryRun: z.boolean(),
  createdAt: z.string(),
  expiresAt: z.string(),
  createdBy: z.object({ sub: z.string(), displayName: z.string().optional(), role: z.string().optional() }).passthrough(),
  approvedBy: z.object({ sub: z.string(), displayName: z.string().optional(), role: z.string().optional() }).passthrough().optional(),
  approvedAt: z.string().optional(),
  reason: z.string().optional(),
  resourceId: z.string(),
  resourceType: z.string(),
  plan: z.object({ before: z.unknown(), after: z.unknown(), rollback: z.unknown(), description: z.string() }).passthrough(),
  execution: z.object({ dryRun: z.boolean(), status: z.string(), completedAt: z.string().optional() }).passthrough().optional(),
}).passthrough();
export const RemediationDetailSchema = z.object({ item: RemediationItemSchema });
export const RemediationsSchema = z.object({
  items: z.array(RemediationItemSchema),
  count: z.number(),
  nextToken: z.string().nullable(),
});
