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

export const BackendFindingSchema = z
  .object({
    findingId: z.string(),
    title: z.string(),
    ruleId: z.string(),
    description: z.string(),
    severity: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
    status: z.enum(["OPEN", "ACKNOWLEDGED", "RESOLVED", "SUPPRESSED"]),
    resourceId: z.string(),
    resourceType: z.string(),
    region: z.string(),
    firstSeenAt: z.string(),
    updatedAt: z.string(),
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
export const EvaluationResultSchema = z
  .object({
    evaluation: z.object({
      evaluationId: z.string(),
      status: z.enum(["SUCCEEDED", "PARTIAL"]),
      summary: z.object({
        resourceCount: z.number(),
        violationsFound: z.number(),
        resolvedFindings: z.number(),
        inventoryPartial: z.boolean(),
      }),
    }),
  })
  .transform(({ evaluation }) => ({
    id: evaluation.evaluationId,
    status: evaluation.status,
    message: `${evaluation.summary.resourceCount} resources checked; ${evaluation.summary.violationsFound} violations found.`,
    summary: evaluation.summary,
  }));
