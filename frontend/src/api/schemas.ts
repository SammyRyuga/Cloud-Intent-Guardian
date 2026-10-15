import { z } from 'zod';

export const SeveritySchema = z.enum(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']);

export const FindingStatusSchema = z.enum(['OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'SUPPRESSED']);

export const DiffStateSchema = z.enum(['MATCHED', 'ADDED', 'MISSING', 'CHANGED', 'UNEXPECTED', 'UNKNOWN']);

export const GraphViewSchema = z.enum(['DIFF', 'INTENT', 'ACTUAL']);

export const ConformanceMetricsSchema = z.object({
  percent: z.number().nullable(),
  totalRules: z.number(),
  passingRules: z.number(),
  failingRules: z.number(),
});

export const SeverityCountsSchema = z.object({
  critical: z.number(),
  high: z.number(),
  medium: z.number(),
  low: z.number(),
  info: z.number(),
});

export const DashboardSummarySchema = z.object({
  conformance: ConformanceMetricsSchema,
  severityCounts: SeverityCountsSchema,
  totalFindings: z.number(),
  activeDriftCount: z.number().nullable(),
  openRemediations: z.number().nullable(),
  partial: z.boolean().optional(),
  lastEvaluatedAt: z.string().nullable(),
  evaluatedRegion: z.string(),
});

export const FindingSchema = z.object({
  id: z.string(),
  ruleId: z.string(),
  title: z.string(),
  severity: SeveritySchema,
  status: FindingStatusSchema,
  resourceId: z.string(),
  resourceType: z.string(),
  region: z.string(),
  detectedAt: z.string(),
  updatedAt: z.string(),
  description: z.string(),
  remediationAvailable: z.boolean(),
  remediationActionId: z.string().optional(),
  aiExplanation: z.object({
    summary: z.string(),
    rationale: z.string(),
    citedEvidence: z.array(z.string()),
  }).optional(),
});

export const FindingsResponseSchema = z.object({
  items: z.array(FindingSchema),
  meta: z.object({
    nextCursor: z.string().nullable().optional(),
    totalCount: z.number().optional(),
  }),
});

export const GraphNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  resourceType: z.string(),
  diffState: DiffStateSchema,
  severity: SeveritySchema.optional(),
  findingCount: z.number().optional(),
  arn: z.string().optional(),
  properties: z.record(z.unknown()).optional(),
  componentId: z.string().optional(),
  componentIds: z.array(z.string()).optional(),
  resourceIds: z.array(z.string()).optional(),
  declarationId: z.string().optional(),
  effect: z.enum(['ALLOW', 'DENY']).optional(),
  observationKind: z.string().optional(),
  source: z.string().nullable().optional(),
  explanation: z.string().optional(),
  simulated: z.boolean().optional(),
}).passthrough();

export const GraphEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  relationshipType: z.string(),
  diffState: DiffStateSchema,
  evidence: z.unknown().optional(),
  protocol: z.string().optional(),
  ports: z.array(z.number().int().min(1).max(65535)).optional(),
  observationKind: z.string().optional(),
  declarationId: z.string().optional(),
  effect: z.enum(['ALLOW', 'DENY']).optional(),
  explanation: z.string().optional(),
  simulated: z.boolean().optional(),
}).passthrough();

export const GraphCoverageSchema = z.object({
  resourceTypes: z.record(z.string()).optional(),
  relationshipTypes: z.record(z.string()).optional(),
}).passthrough();

export const ArchitectureGraphSchema = z.object({
  view: GraphViewSchema,
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
  truncated: z.boolean(),
  totalNodeCount: z.number(),
  asOf: z.string(),
  partial: z.boolean().optional(),
  warnings: z.array(z.object({source: z.string(), message: z.string()})).optional(),
  intentId: z.string().optional(),
  intentVersion: z.union([z.number(), z.string()]).optional(),
  snapshotId: z.string().nullable().optional(),
  coverage: GraphCoverageSchema.optional(),
  simulated: z.boolean().optional(),
}).passthrough();

export const IntentVersionSchema = z.object({
  versionId: z.string(),
  createdAt: z.string(),
  createdBy: z.string(),
  description: z.string(),
  status: z.enum(['DRAFT', 'APPROVED', 'SUPERSEDED']),
  sourceFile: z.string(),
});

export const IntentSchema = z.object({
  id: z.string(),
  name: z.string(),
  currentVersion: z.string(),
  lastUpdatedAt: z.string(),
  resourceCount: z.number(),
  versions: z.array(IntentVersionSchema),
});

export const IntentsResponseSchema = z.object({
  items: z.array(IntentSchema),
  meta: z.object({
    nextCursor: z.string().nullable().optional(),
  }),
});

export const DriftEventSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  resourceId: z.string(),
  resourceType: z.string(),
  eventType: z.enum(['CREATED', 'MODIFIED', 'DELETED']),
  diffSummary: z.string(),
  previousState: z.record(z.unknown()).optional(),
  currentState: z.record(z.unknown()).optional(),
});

export const DriftEventsResponseSchema = z.object({
  items: z.array(DriftEventSchema),
  meta: z.object({
    nextCursor: z.string().nullable().optional(),
  }),
});

export const RemediationRequestSchema = z.object({
  id: z.string(),
  findingId: z.string(),
  findingTitle: z.string(),
  severity: SeveritySchema,
  resourceId: z.string(),
  status: z.enum(['PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXECUTING', 'COMPLETED', 'FAILED']),
  requestedAt: z.string(),
  requestedBy: z.string(),
  plannedAction: z.string(),
  dryRunOutput: z.string().optional(),
  decisionNote: z.string().optional(),
});

export const RemediationsResponseSchema = z.object({
  items: z.array(RemediationRequestSchema),
  meta: z.object({
    nextCursor: z.string().nullable().optional(),
  }),
});

export const AuditEventSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  actor: z.string(),
  action: z.string(),
  resourceId: z.string().optional(),
  details: z.string(),
  ipAddress: z.string().optional(),
});

export const AuditEventsResponseSchema = z.object({
  items: z.array(AuditEventSchema),
  meta: z.object({
    nextCursor: z.string().nullable().optional(),
  }),
});

export const SystemStatusSchema = z.object({
  backendReachable: z.boolean(),
  awsSourcesConnected: z.boolean(),
  evaluatedRegion: z.string(),
  lastSyncAt: z.string(),
  version: z.string(),
});

export const JobStatusSchema = z.object({
  jobId: z.string(),
  type: z.enum(['EVALUATION', 'INGESTION']),
  status: z.enum(['PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED']),
  progressPercent: z.number(),
  startedAt: z.string(),
  completedAt: z.string().optional(),
  message: z.string().optional(),
  error: z.string().optional(),
});
