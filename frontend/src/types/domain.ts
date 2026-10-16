export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type FindingStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'SUPPRESSED';

export type DiffState = 'MATCHED' | 'ADDED' | 'MISSING' | 'CHANGED' | 'UNEXPECTED' | 'UNKNOWN';

export type GraphView = 'DIFF' | 'INTENT' | 'ACTUAL';

export type ConnectionState = 'connected' | 'degraded' | 'disconnected' | 'connecting';

export interface ConformanceMetrics {
  percent: number | null; // null represents not evaluated yet (INV-04)
  totalRules: number;
  passingRules: number;
  failingRules: number;
}

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface DashboardSummary {
  conformance: ConformanceMetrics;
  severityCounts: SeverityCounts;
  totalFindings: number;
  activeDriftCount: number | null;
  openRemediations: number | null;
  features?: {
    driftEvents?: boolean;
    remediation?: boolean;
  };
  partial?: boolean;
  lastEvaluatedAt: string | null;
  evaluatedRegion: string;
}

export interface Finding {
  id: string;
  ruleId: string;
  title: string;
  severity: Severity;
  severityScore?: number;
  severityFactors?: {
    formulaVersion: '1';
    baseSeverity: { label: string; points: number };
    componentCriticality: { label: string; points: number; componentIds: string[]; defaulted: boolean };
    blastRadius: { count: number; points: number; complete: boolean; downstreamResourceIds: string[]; explanation: string };
    exposure: { label: string; points: number; explanation: string };
    confidence: { label: 'HIGH' | 'MEDIUM' | 'LOW'; points: number; explanation: string };
    explanation: string;
  };
  confidence?: 'HIGH' | 'MEDIUM' | 'LOW';
  constraintSeverity?: Severity;
  tier?: 'TIER_2';
  reviewStatus?: 'NEEDS_HUMAN_REVIEW' | 'CORROBORATED';
  crossValidation?: {
    accepted: boolean;
    simulated?: boolean;
    sourceVerdicts: Array<{
      sourceFamily: string;
      verdict: string;
      evidenceId: string;
      originId?: string;
      predicate: string;
      sourceId?: string;
      targetId?: string;
      snapshotId?: string;
      observedAt: string;
      eligible?: boolean;
    }>;
    reason: string;
  };
  llmConclusion?: { candidateId: string; verdict: 'CONCERN' | 'BENIGN' | 'UNCERTAIN'; explanation: string } | null;
  status: FindingStatus;
  resourceId: string;
  resourceType: string;
  region: string;
  detectedAt: string;
  updatedAt: string;
  revision?: number;
  suppressionReason?: string;
  suppressedAt?: string;
  suppressedBy?: string;
  description: string;
  remediationAvailable: boolean;
  remediationActionId?: 'REMOVE_OPEN_SSH' | 'ENABLE_S3_BLOCK_PUBLIC_ACCESS';
  actionEligible?: boolean;
  aiExplanation?: {
    summary: string;
    rationale: string;
    citedEvidence: string[];
  };
  evidence?: Array<{source: string; resourceId: string; observedAt: string; details: Record<string, unknown>}>;
  history?: CandidateHistory;
  observed?: { attachmentImpact?: AttachmentImpact; history?: CandidateHistory; [key: string]: unknown };
  expected?: Record<string, unknown>;
  explanation?: string;
}

export interface FindingsResponse {
  items: Finding[];
  meta: {
    nextCursor?: string | null;
    totalCount?: number;
  };
}

export interface GraphNode extends Record<string, unknown> {
  id: string;
  label: string;
  resourceType: string;
  diffState: DiffState;
  severity?: Severity;
  findingCount?: number;
  arn?: string;
  properties?: Record<string, unknown>;
  componentId?: string;
  componentIds?: string[];
  resourceIds?: string[];
  declarationId?: string;
  effect?: 'ALLOW' | 'DENY';
  observationKind?: string;
  source?: string | null;
  explanation?: string;
  simulated?: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationshipType: string;
  diffState: DiffState;
  evidence?: unknown;
  protocol?: string;
  ports?: number[];
  observationKind?: string;
  declarationId?: string;
  effect?: 'ALLOW' | 'DENY';
  explanation?: string;
  simulated?: boolean;
}

export interface ArchitectureGraph {
  view: GraphView;
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  totalNodeCount: number;
  asOf: string;
  partial?: boolean;
  warnings?: Array<{source: string; message: string}>;
  intentId?: string;
  intentVersion?: number | string;
  snapshotId?: string | null;
  coverage?: unknown;
  simulated?: boolean;
}

export interface IntentVersion {
  versionId: string;
  createdAt: string;
  createdBy: string;
  description: string;
  status: 'DRAFT' | 'APPROVED' | 'SUPERSEDED';
  sourceFile: string;
}

export interface Intent {
  id: string;
  name: string;
  currentVersion: string;
  lastUpdatedAt: string;
  resourceCount: number;
  versions: IntentVersion[];
}

export interface IntentsResponse {
  items: Intent[];
  meta: {
    nextCursor?: string | null;
  };
}

export interface DriftEvent {
  evaluationId?: string;
  previousEvaluationId?: string;
  intentId?: string;
  intentVersion?: number;
  entityKind?: 'RESOURCE' | 'EDGE';
  simulated?: boolean;
  id: string;
  timestamp: string;
  resourceId: string;
  resourceType: string;
  eventType: 'CREATED' | 'MODIFIED' | 'DELETED';
  diffSummary: string;
  previousState?: Record<string, unknown>;
  currentState?: Record<string, unknown>;
}

export interface DriftEventsResponse {
  items: DriftEvent[];
  meta: {
    nextCursor?: string | null;
  };
}

export interface RemediationRequest {
  proposalId: string;
  findingId: string;
  actionId: 'REMOVE_OPEN_SSH' | 'ENABLE_S3_BLOCK_PUBLIC_ACCESS';
  status: 'PROPOSED' | 'APPROVED' | 'EXECUTING' | 'EXECUTED' | 'DRY_RUN_COMPLETE' | 'FAILED';
  revision: number;
  dryRun: boolean;
  createdAt: string;
  expiresAt: string;
  createdBy: { sub: string; role?: string; [key: string]: unknown };
  approvedBy?: { sub: string; role?: string; [key: string]: unknown };
  approvedAt?: string;
  reason?: string;
  resourceId: string;
  resourceType: string;
  plan: { before?: unknown; after?: unknown; rollback?: unknown; description: string; attachmentImpact?: AttachmentImpact };
  execution?: { dryRun: boolean; status: string; completedAt?: string };
}

export interface RemediationsResponse {
  items: RemediationRequest[];
  count: number;
  nextToken: string | null;
}

export interface AuditEvent {
  auditId: string;
  timestamp: string;
  actor: { sub: string; displayName?: string };
  action: string;
  target: unknown;
  result: string;
  requestId: string;
  evaluationId?: string;
  scopeKey: string;
  metadata: Record<string, unknown>;
}

export interface AuditEventsResponse {
  items: AuditEvent[];
  count: number;
  nextToken: string | null;
  limit: number;
}

export interface SystemStatus {
  backendReachable: boolean;
  awsSourcesConnected: boolean; // INV-03: "Connected" only if both are true
  evaluatedRegion: string;
  lastSyncAt: string;
  version: string;
  features?: {
    fixtureInventory?: boolean;
    topology?: boolean;
    evaluations?: boolean;
    remediationProposals?: boolean;
    remediationExecution?: boolean;
    [key: string]: unknown;
  };
}

export interface EvaluationRecord {
  evaluationId: string;
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'PARTIAL' | 'FAILED';
  intentId?: string | null;
  intentVersion?: number | null;
  createdAt?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  progressStage?: string | null;
  summary?: Record<string, unknown> | null;
  error?: { code: string; message: string } | null;
}

export interface AttachmentImpact {
  coverage: 'COMPLETE' | 'PARTIAL'; sourceCoverage: Record<string, string>;
  knownAttachmentCount: number; attachmentCount: number | null;
  attachments: Array<{ resourceId: string; resourceType: string; source: string | null; interfaceType?: string; status?: string; vpcId?: string; subnetId?: string; instanceId?: string | null }>;
  observedAt?: string; requiresHumanApproval: true; interpretation: string;
}
export interface CandidateHistory {
  status: 'FIRST_OBSERVATION' | 'PREVIOUSLY_OBSERVED' | 'NEW' | 'UNKNOWN'; reason: string;
  previousEvaluationId: string | null; driftEventIds: string[];
  comparisonScope: 'SAME_INTENT_VERSION'; isHistoricalChange: boolean;
}
