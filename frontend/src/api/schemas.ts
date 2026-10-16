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
  features: z.object({
    driftEvents: z.boolean().optional(),
    remediation: z.boolean().optional(),
  }).optional(),
  partial: z.boolean().optional(),
  lastEvaluatedAt: z.string().nullable(),
  evaluatedRegion: z.string(),
});

export const FindingSchema = z.object({
  id: z.string(),
  ruleId: z.string(),
  title: z.string(),
  severity: SeveritySchema,
  severityScore: z.number().optional(),
  severityFactors: z.object({
    formulaVersion: z.literal('1'),
    baseSeverity: z.object({ label: z.string(), points: z.number() }),
    componentCriticality: z.object({
      label: z.string(), points: z.number(), componentIds: z.array(z.string()), defaulted: z.boolean(),
    }),
    blastRadius: z.object({
      count: z.number(), points: z.number(), complete: z.boolean(),
      downstreamResourceIds: z.array(z.string()), explanation: z.string(),
    }),
    exposure: z.object({ label: z.string(), points: z.number(), explanation: z.string() }),
    confidence: z.object({ label: z.enum(['HIGH', 'MEDIUM', 'LOW']), points: z.number(), explanation: z.string() }),
    explanation: z.string(),
  }).passthrough().optional(),
  confidence: z.enum(['HIGH', 'MEDIUM', 'LOW']).optional(),
  constraintSeverity: SeveritySchema.optional(),
  tier: z.literal('TIER_2').optional(),
  reviewStatus: z.enum(['NEEDS_HUMAN_REVIEW', 'CORROBORATED']).optional(),
  crossValidation: z.object({
    accepted: z.boolean(), simulated: z.boolean().optional(), reason: z.string(),
    sourceVerdicts: z.array(z.object({
      sourceFamily: z.string(), verdict: z.string(), evidenceId: z.string(), originId: z.string().optional(),
      predicate: z.string(), sourceId: z.string().optional(), targetId: z.string().optional(),
      snapshotId: z.string().optional(), observedAt: z.string(), eligible: z.boolean().optional(),
    }).passthrough()),
  }).passthrough().optional(),
  llmConclusion: z.object({ candidateId: z.string(), verdict: z.enum(['CONCERN', 'BENIGN', 'UNCERTAIN']), explanation: z.string() }).nullable().optional(),
  actionEligible: z.boolean().optional(),
  status: FindingStatusSchema,
  resourceId: z.string(),
  resourceType: z.string(),
  region: z.string(),
  detectedAt: z.string(),
  updatedAt: z.string(),
  revision: z.number().optional(),
  description: z.string(),
  remediationAvailable: z.boolean(),
  remediationActionId: z.enum(['REMOVE_OPEN_SSH', 'ENABLE_S3_BLOCK_PUBLIC_ACCESS']).optional(),
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
  evaluationId: z.string().optional(),
  previousEvaluationId: z.string().optional(),
  intentId: z.string().optional(),
  intentVersion: z.number().int().optional(),
  entityKind: z.enum(['RESOURCE', 'EDGE']).optional(),
  simulated: z.boolean().optional(),
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

export const AuditEventsResponseSchema = z.object({
  items: z.array(AuditEventSchema),
  count: z.number(),
  nextToken: z.string().nullable(),
  limit: z.number(),
});

export const SystemStatusSchema = z.object({
  backendReachable: z.boolean(),
  awsSourcesConnected: z.boolean(),
  evaluatedRegion: z.string(),
  lastSyncAt: z.string(),
  version: z.string(),
  features: z.object({
    fixtureInventory: z.boolean().optional(),
    topology: z.boolean().optional(),
    evaluations: z.boolean().optional(),
    remediationProposals: z.boolean().optional(),
    remediationExecution: z.boolean().optional(),
  }).passthrough().optional(),
}).passthrough();

export const EvaluationSchema = z.object({
  evaluationId: z.string(),
  status: z.enum(['QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED']),
  intentId: z.string().nullable().optional(),
  intentVersion: z.number().nullable().optional(),
  createdAt: z.string().optional(),
  startedAt: z.string().nullable().optional(),
  finishedAt: z.string().nullable().optional(),
  progressStage: z.string().nullable().optional(),
  summary: z.record(z.unknown()).nullable().optional(),
  error: z.object({ code: z.string(), message: z.string() }).nullable().optional(),
}).passthrough();
export const EvaluationAcceptedSchema = z.object({
  evaluation: z.object({
    evaluationId: z.string(),
    status: z.literal('QUEUED'),
    intentId: z.string().nullable(),
    intentVersion: z.number().nullable(),
    createdAt: z.string(),
  }).passthrough(),
  statusUrl: z.string(),
});
export const EvaluationDetailSchema = z.object({ item: EvaluationSchema });
export const EvaluationsResponseSchema = z.object({
  items: z.array(EvaluationSchema),
  count: z.number(),
  nextToken: z.string().nullable(),
  limit: z.number(),
});
