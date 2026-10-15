# Cloud Intent Guardian development plan

Status: approved by the user; Phase 1 implementation and validation completed.
Review date: 2026-10-15. Source baseline: `14dea4a`.

This document proposes Phases 1 and 2 in detail and defines the dependencies for
Phases 3-6. Approval authorizes local implementation and phase commits only.
Deployment, live AWS calls, real credentials, and real remediation execution are
outside this work. No application code or infrastructure has changed in this
planning step.

## 1. Sources and precedence

Reviewed: root `README.md`, `INTEGRATION.md`, `backend/VALIDATION.md`,
`backend/LOCAL_TESTING.md`, `backend/template.yaml`, all Python source and both
backend test modules, `backend/scripts/local_db.py`, frontend `AGENTS.md`, the
frontend PRD and implementation specification, current transport schemas,
endpoint helpers, hooks, capabilities and contract tests.

Case-study source:
`/Users/ryanfernandes/Downloads/CloudIntentGuardian_CaseStudy (1) (1).pdf`.
Its architectural-intent and cross-validation goals inform this plan. Its
Fargate/ALB, relational audit store, Organizations, broad Config recording and
automatic remediation proposals are superseded by the current task's Academy,
serverless, DynamoDB audit and explicit-human-approval requirements. Its claims
about competing products and research novelty have not been independently
validated and are not implementation acceptance criteria.

The implemented wire contract and the current task take precedence over older
proposed frontend contracts. Preserve `/v1`, native identifiers, numeric intent
versions, `{item}` details, `{items,count,nextToken,limit}` lists and
`{error:{code,message,details?}}` errors. Do not introduce a global `data/meta`
envelope. Gateway-generated authentication errors remain a separate boundary.

## 2. Gap analysis grounded in the checkout

| Area | Existing behavior | Required addition / consequence |
| --- | --- | --- |
| Intent validation | `intents/app.py` requires 1-50 attribute constraints; writes numeric `version:1` | Backward-compatible v2 schema; topology-only manifests; validate component references and rule semantics |
| Approval | `approve_intent/app.py` conditionally approves a draft; requires constraints | Validate v1 or v2; immutable approved content, active version pointer, atomic audit |
| Inventory | EC2/VPC/subnet/SG, RDS and S3; bounded and partial-aware | Retain tags, add optional Lambda metadata and RDS SG attachments; explicitly track coverage by resource/relationship type |
| Graph edges | `BELONGS_TO_VPC`, `IN_SUBNET`, `USES_SECURITY_GROUP`, `IN_VPC` | These are structural facts, not evidence of application traffic; add typed, evidence-backed network edges without changing existing edges |
| Graph API | `ACTUAL` only, always `diffState:UNKNOWN`; other views return 409 | Add `INTENT` and `DIFF` at the same `/v1/architecture/graph` route |
| Evaluation | `evaluations/app.py` synchronously checks four attributes, writes findings then summary | Add pure topology engine, rule outcomes, pinned intent/snapshot, durable job status, retries and reads |
| Missing attributes | `_violates` treats missing fields as non-violations; collector coerces missing RDS public-access value to false | Preserve outcomes for known v1 facts; represent missing facts as UNKNOWN and prevent unsafe passes/resolution |
| Findings | Stable hash of intent/rule/resource; status preserved on repeat detection | Explicit acknowledge/suppress/reopen transitions, suppression reasons, version-aware evidence and safer scoped reconciliation |
| Resolution | Complete inventory and complete bounded findings scan permit auto-resolution | Also require same account/region, evaluated rule applicability, sufficient source coverage and successful result publication; never clear an unknown rule |
| Versions | No version storage or pointer; latest approved intent chosen by bounded scan | Immutable versions, explicit activation/supersede/rollback, semantic diff, optimistic concurrency |
| Audit | No table or routes | Append-only server events, mutation transaction integration, paginated `/v1/audit` |
| Local API | Explicitly blocks inventory and evaluation | Keep live-AWS block; allow a separate server-configured local fixture provider plus explicit local worker |
| Auth | Cognito JWT authorizer; no group checks or account ownership | Server roles and configured account/region scope; introduce role helper before new approval/lifecycle mutations |
| UI | Working manifest persistence, stored findings/dashboard, ACTUAL graph and synchronous evaluation adapter | Extend existing React app in place; update transport schema, fixtures, MSW and tests with each API change |
| UI contract drift | Mock job IDs, `/v1/jobs`, `/v1/audit-events`, ADDED/CHANGED graph states; live adapters differ | Use evaluation IDs/status routes and `/v1/audit`; add UNEXPECTED; preserve old mock values only as compatibility inputs during transition |
| Local DB | Three tables, partition-key-only schema checks | Add new schemas/index checks non-destructively; never replace existing tables or containers |

Historical validation in `INTEGRATION.md` records thirteen backend tests,
seventeen frontend tests, SAM build/lint and local browser/persistence checks on
2026-10-13. These have not been rerun in this planning step. Some older sections
of `LOCAL_TESTING.md` describe already-fixed gaps; current source and the later
integration record govern.

## 3. Phase 1: intent v2 and deterministic conformance

### 3.1 Proposed manifest

`schemaVersion` describes the manifest format; existing `version` remains the
server-assigned revision number. Missing `schemaVersion` means legacy v1. Legacy
create/read/approve payloads remain accepted and retain their four rule meanings.

```json
{
  "schemaVersion": 2,
  "name": "Three-tier application",
  "description": "Database access must pass through the API tier",
  "components": [
    {"id":"web-tier","resourceTypes":["AWS::EC2::Instance"],
     "selector":{"tags":{"cig:tier":"web"}},"minMatches":1},
    {"id":"api-tier","resourceTypes":["AWS::EC2::Instance"],
     "selector":{"tags":{"cig:tier":"api"}},"minMatches":1},
    {"id":"worker","resourceTypes":["AWS::Lambda::Function"],
     "selector":{"idPatterns":["arn:aws:lambda:*:*:function:cig-worker-*"]},"minMatches":0},
    {"id":"database","resourceTypes":["AWS::RDS::DBInstance"],
     "selector":{"resourceIds":["arn:aws:rds:ap-south-1:123456789012:db:cig-demo"]},"minMatches":1}
  ],
  "relationships": [
    {"id":"web-api","from":"web-tier","to":"api-tier","effect":"ALLOW",
     "relationshipType":"NETWORK_REACHABILITY","protocol":"tcp","ports":[443],"required":true},
    {"id":"api-db","from":"api-tier","to":"database","effect":"ALLOW",
     "relationshipType":"NETWORK_REACHABILITY","protocol":"tcp","ports":[5432],"required":true},
    {"id":"deny-worker-db","from":"worker","to":"database","effect":"DENY",
     "relationshipType":"NETWORK_REACHABILITY","protocol":"tcp","ports":[5432]}
  ],
  "trustBoundaries": [
    {"id":"edge","members":["web-tier"],"crossingRules":[
      {"id":"edge-api","to":"services","effect":"ALLOW","via":["api-tier"]}]},
    {"id":"services","members":["api-tier","worker"],"crossingRules":[]},
    {"id":"data","members":["database"],"crossingRules":[]}
  ],
  "criticality":{"web-tier":"MEDIUM","api-tier":"HIGH","worker":"MEDIUM","database":"CRITICAL"},
  "constraints": [
    {"id":"no-ssh","type":"SECURITY_GROUP_NO_OPEN_SSH","severity":"HIGH"},
    {"id":"only-api-db","type":"ALLOWED_PATH","target":"database","allowedSources":["api-tier"],
     "pathMode":"DIRECT","edgeTypes":["NETWORK_REACHABILITY"],"severity":"HIGH"},
    {"id":"worker-db-bypass","type":"REQUIRED_INTERMEDIARY","from":"worker","to":"database",
     "via":["api-tier"],"edgeTypes":["NETWORK_REACHABILITY"],"severity":"HIGH"}
  ]
}
```

Selectors support exact IDs, bounded glob patterns (`*` and `?`, no executable
expressions/regex), and exact tag key/value matches. Alternative entries within
one selector list are OR; different selector fields and the resource-type filter
are AND. A component can match multiple resources. Missing tag permissions or
ambiguous membership produce UNKNOWN rather than a guessed match. Default
`minMatches` is 1; zero explicitly permits ephemeral/absent components. Resources
matching multiple components are ambiguous unless an explicit future schema
allows overlap. Trust zones are non-overlapping in v2; reject duplicate/unknown
members and invalid criticality keys. Unzoned resources have unknown trust scope.

Retain 50 constraints; initially cap components at 100, relationships at 250 and
zones at 20, with a 200 KiB normalized manifest limit. Enforce string/list bounds,
unique IDs, valid protocol/port combinations, all references and contradictory
allow/deny declarations. Reject contradictions with 400; do not silently choose
a winner. All supplied v2 sections are validated even if a feature is disabled.
A v2 manifest can omit/empty `constraints` only if it contains an evaluable
relationship or boundary rule. Components alone do not constitute an approved
policy. Missing component criticality defaults to MEDIUM with recorded evidence.

### 3.2 Edge evidence and local observation

Keep `/v1/resources` as `{items,edges,meta}` and existing node/edge fields. Add
optional node `tags`, edge `evidence`, `protocol`, `ports`, `observationKind`, and
metadata `coverage`/`snapshotId`. Define evidence kinds separately:

- STRUCTURAL: containment and attachment; valid only for explicitly structural rules.
- CONFIGURED: security policy permits a candidate network connection. SG matching
  alone does not prove routing/NACL reachability or actual traffic. Incomplete
  route/NACL/attachment coverage yields UNKNOWN for NETWORK_REACHABILITY.
- OBSERVED: a correlated traffic record supports a particular flow at a stated time.
  Absence of a flow record never proves absence of a possible path.

Add a conservative `NETWORK_PERMISSION` edge for SG-level permission when enough
attachment/ingress/egress data exists. Reserve `NETWORK_REACHABILITY` for sources
that actually establish the rule's full predicate; do not relabel permissions as
traffic. Live reachability can stay UNKNOWN where data is unsupported. Fixture
graphs explicitly declare their evidence kind and coverage, so the Lambda bypass
scenario is fully testable without pretending it was observed in AWS.

Introduce an inventory-provider seam around the current collector. Production
keeps read-only collection. Local execution continues to refuse cloud discovery;
`CIG_LOCAL=true` plus `INVENTORY_PROVIDER=fixture` permits only bundled,
allowlisted scenario IDs selected by server configuration. Never accept a file
path, arbitrary observation graph or cloud endpoint from an API request. Status
and graph metadata label fixtures as simulated and AWS sources disconnected.
Add Lambda/tag collection behind flags; access denial yields coverage warnings.

### 3.3 Rule semantics

Each rule returns PASS, VIOLATION, UNKNOWN or NOT_APPLICABLE, with matched
components, path/edge witnesses, source coverage and reasons. Positive violation
witnesses can survive partial collection if their own evidence is sufficient;
absence-based passes require complete relevant coverage. Bound traversals, track
visited nodes, handle cycles, and report UNKNOWN if computation limits are hit.
Persist per-resource/per-binding outcomes beneath each policy-rule result, so a
known good resource cannot hide another binding's missing data. Legacy known-value
checks retain their behavior; missing-value UNKNOWN handling is an explicit safety
correction documented and tested in Phase 1, including missing RDS/S3 metadata.

| Rule | Deterministic meaning |
| --- | --- |
| ALLOWED_PATH | An explicit allowlist for paths ending at `target`; a witnessed path from a source outside `allowedSources` violates it. `pathMode:DIRECT` checks incoming edges; TRANSITIVE checks all reachable source components. An allowed edge by itself does not forbid all other edges. |
| FORBIDDEN_PATH | A path from `from` to `to` using the selected edge types violates; DIRECT or TRANSITIVE is explicit. A DENY relationship compiles to the direct case. |
| TRUST_BOUNDARY_CROSSING | Check directed crossings against explicit crossing rules. Unlisted crossings are ambiguous candidates, not automatically violations. Explicit DENY is deterministic; explicit ALLOW with a bypassed required intermediary violates. |
| REQUIRED_INTERMEDIARY | Every applicable source-to-target path must pass through the declared `via` components in order. A bypass witness violates. No path is NOT_APPLICABLE unless a separate required relationship demands one. |
| EXPOSURE_BLAST_RADIUS | Count unique downstream nodes on qualifying directed network edges from a declared exposed component; a witnessed count above `maxReachableNodes` violates. Incomplete coverage makes counts lower bounds and prevents an absence-based pass. |

ALLOW relationships describe permitted edges; `required:true` additionally
requires them to exist when coverage can establish absence. Missing required
components/edges are distinct from forbidden observed paths. Normalize declarative
relationships into stable internal rule IDs and retain source declaration IDs in
evidence. Do not emit duplicate findings when an equivalent explicit constraint
and relationship express the same violation.

Conformance retains `percent,totalRules,passingRules,failingRules`. Add
`unknownRules,notApplicableRules,definition`; count enabled applicable policy
rules, not resource count. Unknown/partial results cannot claim full conformance;
percent is null if required applicable outcomes remain unknown. Keep unruled
topology changes as candidates for Phase 4.

### 3.4 Graph API proposal

`GET /v1/architecture/graph?view=ACTUAL|INTENT|DIFF&intentId=...&version=...`
retains `view,nodes,edges,truncated,partial,warnings,totalNodeCount,asOf` and node
`diffState`/edge identifiers. Add `intentId,intentVersion,snapshotId,coverage` and
explanation/evidence references. Use an explicit approved intent for DIFF; in
Phase 1 default selection preserves the bounded existing selection behavior.
Phase 2 resolves an explicit intent's active pointer. No approved baseline yields
409 `NO_APPROVED_INTENT`; missing explicit IDs/versions yield 404. Invalid views
yield 400. INTENT can render declarations without any AWS discovery.

| State | Meaning in DIFF |
| --- | --- |
| MATCHED | Declared component/pair matches observations with adequate evidence; does not assert whole-resource security |
| MISSING | Required declared component/edge absent with sufficient coverage |
| UNEXPECTED | Observed node/edge outside the applicable declared model, or explicitly forbidden; state alone is not a severity finding |
| UNKNOWN | Unsupported relationship, incomplete source coverage, ambiguous mapping, unzoned membership, or insufficient evidence |

DIFF is the union of declared and observed elements. Missing logical nodes use
stable namespaced IDs (`intent:<intentId>:component:<id>`); observed resources
keep their current IDs. Logical-to-concrete mappings are explicit fields, never
guessed by React. Multiple concrete matches are rendered separately; a required
logical edge is missing only if its declared matching semantics are unsatisfied.
INTENT renders logical declarations neutrally as UNKNOWN (no observation claim).
ACTUAL remains an observed view; UNKNOWN without a selected comparison is valid.
In DIFF replace the current blanket UNKNOWN result with actual classifications.
Unruled, confirmed topology differences can be UNEXPECTED while their security
conclusion remains UNKNOWN. Keep this distinction in evidence and the legend.

Update frontend domain/Zod graph enums and styling for UNEXPECTED in Phase 1;
do not wait until Phase 6 to repair consumers. Retain compatibility parsing for
old mock ADDED/CHANGED values while converting maintained fixtures. No frontend
diff or security logic is added.

## 4. Phase 2: versions, async jobs, history, audit and lifecycle

### 4.1 Storage and migration proposal

Preserve the primary keys and data of the three existing tables. Add on-demand
tables and access-pattern indexes through SAM and the local schema registry:

| Record/table | Key/access pattern | Content |
| --- | --- | --- |
| Existing IntentsTable | `intentId` | Existing manifest facade plus `activeVersion`, `latestVersion`, `revision`; facade content is the active approved version, or initial draft before first approval |
| New IntentVersionsTable | partition `intentId`, numeric sort `version` | Append-only version content, schema version, canonical content hash, author, parent version; approval metadata sealed on approval |
| Existing EvaluationsTable | `evaluationId`; new GSI partition `scopeKey`, sort `createdOrder` | Queued/running/terminal job metadata, pinned intent version/hash, configured scope, lease, stage, summary and safe error |
| New EvaluationArtifactsTable | partition `evaluationId`, sort `artifactKey` | Bounded snapshot chunks, rule outcomes and immutable finding evidence for reproducibility; completion manifest and content hashes |
| New AuditEventsTable | partition `auditId`; GSI partition `scopeKey`, sort `eventOrder` | Immutable server event, actor subject, action, target/version, result, request/evaluation correlation, selected redacted metadata |
| Existing FindingsTable | `findingId`; new GSI partition `scopeIntentKey`, sort `findingId` | Current lifecycle, rule/resource/path identity, pinned version/evaluation, suppression metadata and latest evidence |

`scopeKey` is server-derived account + region + stage (a distinct fixture scope
locally). Order keys are timestamp + unique ID to avoid timestamp collisions.
List filters are applied within query pages and may yield an empty page with a
next token. Scope-bound opaque tokens include endpoint/filter context; malformed
or mismatched tokens return 400. Do not claim globally sorted results from a scan.
GSIs may lag; status/detail reads use the base table consistently. Existing rows
need an explicit, resumable local migration/backfill to participate in indexes;
no silent exclusion or destructive table recreation. An unmigrated state returns
an actionable conflict for new indexed workflows, while legacy reads remain usable.

Backfill each legacy manifest as version 1 with the same hash/status, preserve
IDs and timestamps and mark historical actors as unknown when absent. Approval
and pointer changes use transactions and revision conditions. Existing approved
content is never overwritten: changing the root facade only copies a sealed
snapshot after a human-approved activation. SUPERSEDED is derived from approval
and the active pointer; historic approved snapshots remain immutable. Rollback
changes the pointer to a previously approved snapshot; it never edits that snapshot
or decrements the next version number. Evaluations already queued remain pinned.

Artifacts use chunks comfortably below DynamoDB item limits; API list responses
return summaries, not full graphs. A completion manifest prevents incomplete
chunks being treated as a valid snapshot. No always-on graph database or S3
dependency is introduced. Retention is explicit; no automatic deletion of audit
or approved versions in this scope.

### 4.2 Proposed API additions and authorized changes

| Method and path | Input / response |
| --- | --- |
| Existing POST `/v1/intents` | Existing v1 or new v2 manifest; still 201 `{item}` |
| Existing GET `/v1/intents/{intentId}` | Still `{item}`; additive active/latest version and revision fields |
| Existing POST `/v1/intents/{intentId}/approve` | Preserves initial-draft approval/idempotent response; delegates to transactional version approval |
| POST `/v1/intents/{intentId}/versions` | `{manifest,expectedRevision}` -> 201 `{item}` with monotonic numeric version, DRAFT |
| GET `/v1/intents/{intentId}/versions` | `limit,nextToken` -> standard list envelope |
| GET `/v1/intents/{intentId}/versions/{version}` | `{item}` with sealed content and derived effective status |
| POST `/v1/intents/{intentId}/versions/{version}/approve` | `{expectedRevision,comment?}` -> 200 `{item}`; approve and activate, atomically superseding prior pointer |
| POST `/v1/intents/{intentId}/rollback` | `{targetVersion,expectedRevision,reason}` -> 200 `{item}`; previously approved versions only |
| GET `/v1/intents/{intentId}/diff?fromVersion=1&toVersion=2` | `{item:{intentId,fromVersion,toVersion,components,relationships,trustBoundaries,criticality,constraints}}`; each section carries added/removed/changed entries |
| POST `/v1/evaluations` | Preserve `{intentId}` or `{}` input; optional `intentVersion` and bounded `reason`; change to 202 `{evaluation:{evaluationId,status:"QUEUED",intentId,intentVersion,createdAt},statusUrl}` |
| GET `/v1/evaluations` | `limit,nextToken,intentId?,status?` -> standard paginated list of job summaries |
| GET `/v1/evaluations/{id}` | `{item}`: job status, pinned version, stage, timestamps, summary/conformance/warnings when available, safe failure code/message |
| GET `/v1/audit` | `limit,nextToken,action?,from?,to?` -> standard paginated list; newest first in configured scope |
| PATCH `/v1/findings/{findingId}` | `{action:"ACKNOWLEDGE"|"SUPPRESS"|"REOPEN",reason?,expectedRevision}` -> 200 `{item}` |

The only intentional existing response break is POST evaluation's synchronous
200 `{evaluation,findings,inventory}` becoming 202 with status polling, as requested.
Do not claim queued work succeeded. Finding results remain available through
existing finding endpoints; evaluation history identifies each result and retains
its immutable evidence in artifacts. Add `evaluationId` filtering to findings if
needed by the history detail UI, backed by historical artifacts rather than only
current mutable rows. Old evaluations without queued timestamps remain readable.

No `/v1/jobs` or `/v1/audit-events` backend aliases are needed: those currently
exist only as frontend proposals/mock helpers. Change those callers/fixtures to
the requested routes in the same phase. Version diffs are semantic, keyed by
stable declaration IDs; reorder-only edits do not count as changes. Missing IDs,
unapproved activation, stale revisions and invalid transitions use the existing
404/409/400 error shape. Existing initial approval remains idempotent; new stale
version approval/pointer mutations return 409.

### 4.3 Durable async execution

Proposed cloud transport: optional DynamoDB Streams on EvaluationsTable, with
an insert filter for QUEUED jobs and a dedicated worker Lambda. A durable job
insert is the dispatch record, avoiding a write-then-invoke gap. No Step Functions
is proposed for this bounded Academy workload. Stream delivery can repeat; the
worker must acquire a conditional lease and check completion before any writes.
If transport is disabled, production POST returns 409
`ASYNC_EVALUATION_NOT_ENABLED`, rather than accepting work that cannot run.

Local transport: POST persists QUEUED to DynamoDB Local; an explicit local runner
claims that job and invokes the same worker against fixture observations. SAM
local does not establish deployed event-source-mapping behavior. Tests use
SDK-stubbed stream events, failure/retry injection and real local persistence;
they never poll AWS or run the collector with inherited credentials.

Job states: QUEUED -> RUNNING -> SUCCEEDED | PARTIAL | FAILED. Add `createdAt`,
nullable `startedAt/finishedAt`, `progressStage`, `leaseExpiresAt`, `attemptCount`,
`deadlineAt`, and safe `error` fields. Enforce graph/rule/job time budgets; timeout
and expired leases must become visible failed/stalled work, never success. The
local runner includes an explicit expired-job reconciliation command; the cloud
worker/stream retry policy has bounded attempts and failure handling. Polling
can report an expired job as FAILED through an audited conditional transition.

Write snapshot and rule-result artifacts before publishing terminal results.
Make finding writes idempotent and prevent an older job from overwriting newer
results. Serialize evaluation publication per scope + intent using a conditional
lease/revision; retries resume the same job and do not duplicate findings/audit.
Readiness/completion markers distinguish staged artifacts from published results.
Only reconcile findings after the complete relevant rule set and persistence
steps succeed; failed/partial runs cannot clear prior findings. Test crashes
between publication stages rather than assuming a cross-table bulk write is atomic.

Polling pauses in hidden tabs, stops at terminal status or 403/404, uses modest
backoff and has a time limit with a manual refresh option. Dashboard metrics read
the latest published completed evaluation; a queued job cannot erase earlier
results or fabricate conformance.

### 4.4 Audit and roles

Event fields: `auditId,timestamp,actor:{sub,displayName?},action,target,
result,requestId,evaluationId?,scopeKey,metadata`. Actor comes from verified JWT
claims; never from request JSON. Local fixtures use a clearly synthetic local
actor. Selected evidence fields only; no raw tokens, secrets or source dumps.
Event IDs derived from operation IDs prevent duplicate audit entries on retries.

Use DynamoDB transactions to combine each intent/approval/pointer/lifecycle change
with its audit event. Worker stage changes and each finding transition also carry
idempotent audit records. If required audit persistence fails, the mutation cannot
report success. Audit read handlers have read-only permissions; application write
paths append conditionally and cannot edit/delete events. This is application
immutability, not a claim of tamper resistance against an AWS account administrator.

Bring the minimal group-authorization helper forward from Phase 5 to Phase 2,
since new approval and suppression mutations already require it:

| Role | Permissions |
| --- | --- |
| viewer | Read configured-scope records/graphs/history/audit |
| approver | Viewer plus approve/activate/rollback intents, acknowledge and suppress/reopen findings, and later approve/reject remediation |
| admin | Approver plus create new intents/versions, start evaluations and later request/execute approved remediation |

Roles derive from `cognito:groups`; missing/unrecognized groups deny mutations.
Scope is configured server-side, not a browser account parameter. Group membership
grants no cross-account privilege. Normalize actual HTTP API group-claim forms
strictly with unit fixtures. Local dev claims are available only in loopback
fixture mode; production cannot enable that bypass. Existing deployed users would
need group assignment before mutation access; this behavioral hardening must be
documented and approved with this plan. Do not infer that Cognito JWT enforcement
was proven by handler tests.

### 4.5 Finding lifecycle

OPEN -> ACKNOWLEDGED; OPEN/ACKNOWLEDGED -> SUPPRESSED requires a non-empty reason;
ACKNOWLEDGED/SUPPRESSED -> OPEN through explicit REOPEN. Evaluation resolves
OPEN/ACKNOWLEDGED/SUPPRESSED only after confirming the same scoped violation is
absent under an applicable, fully evaluated rule. Retain suppression reason/history
after resolution. A later recurrence reopens the stable finding and is audited.
Repeated detection does not erase acknowledgement or suppression metadata.

Preserve the existing attribute-finding hash; topology identities use stable
intent/rule/endpoint/violation fingerprints, avoiding path-order and version-number
churn. Historical artifacts preserve evidence across version changes. A removed
rule is not proof that an AWS issue was fixed: retain the finding with an explicit
baseline-change review marker, and do not silently resolve it. Partial sources,
disabled rules, unobserved resources and UNKNOWN outcomes never resolve findings.

Reserve `reviewStatus:NEEDS_HUMAN_REVIEW` as a separate field from the four
lifecycle statuses. This meets Phase 4 review requirements while preserving the
existing finding-status enum; confidence LOW and review status block action.

## 5. Academy compatibility and feature flags

This is a static risk assessment, not a statement about this lab's entitlements.
No Academy identity, account policies, regions or service access were queried.

| Template area | Risk / proposed handling |
| --- | --- |
| All nine SAM functions omit `Role` | SAM generates execution roles, potentially blocked by restricted IAM. Propose an existing-role parameter mode and conditional generated-role mode; existing roles must already carry required policies, and `iam:PassRole` may still be required. Never attach new policies to a lab role automatically. |
| StatusFunction | Always probes Config today. Add `CONFIG_ENABLED=false` by default and skip SDK construction/probing when off. Config recording is not created. |
| Inventory/evaluator policies | Current read APIs use `Resource:'*'`, including S3 metadata. Separate actions that require wildcard from those supporting scoped resource ARNs; keep modification permissions absent from readers. Flag new Lambda/tag/route reads as permission-dependent. |
| Cognito pool/client/domain/groups | Creation or group administration may be restricted; prepare an existing-pool/client configuration path for later authorized deployment. Keep JWT authorization required; no production unauthenticated fallback. |
| DynamoDB Streams worker | Needs stream read permissions and event source mapping permission. Feature flag cloud transport; local runner works without it. Approval of this design does not assert Academy support. |
| Bedrock | Model/region/access not known. `BEDROCK_ENABLED=false`, bounded calls, explicit model configuration and graceful denied/unavailable/error fallback. Never select an assumed available model. |
| Flow Logs / CloudTrail / Config | Optional independent evidence adapters, disabled by default. No recorder, trail, log group or paid analytics setup is silently provisioned. Missing sources force review where corroboration is required. |
| Remediation | `REMEDIATION_ENABLED=false`, `REMEDIATION_DRY_RUN=true`; executor permissions conditional and absent by default. Human approval always required. |

Proposed flags also include `TOPOLOGY_ENABLED`, `LAMBDA_INVENTORY_ENABLED`,
`TAG_INVENTORY_ENABLED`, `ASYNC_WORKER_ENABLED`, `CLOUDTRAIL_ENABLED`,
`FLOW_LOGS_ENABLED`, and `INVENTORY_PROVIDER`. Core v2/version/audit reads do not
depend on optional evidence services. Flags are server-owned; frontend capability
hints mirror implemented availability and cannot grant permissions. Existing-role
and Cognito integration details remain a deployment gate until lab facts exist.

Keep Lambda, HTTP API and on-demand DynamoDB. Do not add Fargate, ALB, RDS audit,
NAT gateways, provisioned concurrency, Config recording or Step Functions here.
Bound inventory, traversal, artifacts, retries, model token usage and pagination.
Resource naming/descriptions use ordinary hyphens. Template edits must preserve
existing stateful resources and add design metadata and least-privilege policies.

## 6. Later phases and interfaces established now

### Phase 3: explainable severity

Propose `severityScore` (0-100), existing `severity` label, and
`severityFactors:{baseSeverity,componentCriticality,downstreamReachableCount,
blastRadiusComplete,exposure,confidence,formulaVersion,explanation}`. Publish and
test the exact weighting/thresholds before implementing it. Missing exposure or
reachability is UNKNOWN, not internal/zero; incomplete counts are lower bounds.
Keep confidence separate from potential impact so weak evidence cannot hide a
high-impact case through an artificially low score. Direct database bypass is
at least HIGH in the seeded critical-database scenario. Surface factors in detail
responses without replacing existing `evidence` fields.

### Phase 4: two-tier escalation

Deterministic outcomes stop before any model call. Only unknown/unruled topology
candidates go through `LLMClient` with Bedrock and deterministic mock implementations.
Return a strict allowlisted schema: verdict, candidate IDs, cited evidence IDs,
reason and confidence; reject additional executable instructions/actions,
unrecognized IDs, oversized output and malformed JSON. Model text is never code.

Corroboration compares the same time-scoped predicate across at least two genuinely
independent source families; two adapters over the same EC2 response count as one.
Inventory presence and a CloudTrail change event do not automatically corroborate
an end-to-end reachability claim. Persist each source's verdict, provenance,
freshness and limitations. Missing/disagreeing sources produce
`reviewStatus:NEEDS_HUMAN_REVIEW`, confidence LOW, and no actionable proposal.
Bedrock disabled/denied/error preserves deterministic results and records the
unreviewed candidate. Compare snapshot history before calling a difference a new
change; first-run unruled topology is explicitly labelled baseline ambiguity.

### Phase 5: gated proposals

Registry contains only prewritten revoke-open-SSH and enable-S3-public-access-block
actions. Proposal stores exact target/rule, before/after dry-run diff, dependencies,
blast radius, rollback plan, finding/evidence hash, expiry and approval actor.
Server derives parameters from validated evidence, not arbitrary requested APIs
or model output. A revoke action identifies the exact ingress permission; never
remove unrelated rules. S3 rollback distinguishes prior configuration from absence.
SG impact enumerates all attachments; incomplete/high impact requires human review.

Propose existing spec-compatible request/list/detail/decision routes plus a separate
explicit execute endpoint. Approval never executes as a side effect. Execution
requires current approval, admin role, enabled executor, non-dry-run server setting,
fresh matching preconditions and atomic execution claim. Dry-run never performs
modifying SDK calls and never resolves findings. Real modification clients are
SDK-stubbed only in this project work. Audit every proposal/decision/attempt/result.
Low confidence and model-only conclusions cannot become executable proposals.

### Phase 6: complete UI flows

Extend the existing JSON editor/viewer for components, relationships, boundaries
and criticality; add version/history/diff controls, graph highlighting, evaluation
history/status, severity/evidence detail, approval queue and audit view. Minimal
consumer/schema changes ship in each earlier phase; Phase 6 completes the screens.
Preserve tokens, layout, accessible state text/shapes, and all loading/empty/partial/
error/not-enabled states. Keep mock banners and production rejection of local/mock
mode. No frontend AWS SDK, inferred edges, severity computation or fabricated data.

## 7. Acceptance evidence and phase commits

For each implementation phase: backend SDK-stubbed/Moto unit suite; meaningful
DynamoDB Local integration for changed persistence/workflows; `sam validate --lint`;
`sam build`; frontend `npm run lint`, `npm test`, `npm run test:contract`, and
`npm run build`. Add targeted rendered mock/local browser journeys for changed UI.
Regenerate backend-response contract fixtures in the same phase as wire changes.
Use isolated local data; preserve existing Docker containers and tables. Keep
`backend/local-env.json` ignored (verified with `git check-ignore` during planning).

| Phase | Required new evidence |
| --- | --- |
| 1 | Legacy manifest compatibility; invalid/reference/overlap inputs; all five topology rules; cycles and partial coverage; concrete graph diff states; Lambda bypass witness; local fixture isolation; graph schema/mock updates |
| 2 | Immutable versions, supersede/rollback and diff; stale concurrent changes; queued -> running -> terminal polling; duplicate worker/crash/retry/publication tests; history/audit pagination; scoped resolution; suppression reason; role matrix; non-destructive local migration/probe/init/verify |
| 3 | Factor/threshold examples, unknown exposure, blast-radius lower bounds, stored evidence and HIGH bypass scenario |
| 4 | No model call for clear Tier 1; valid/invalid/unavailable model responses; two independent sources; source disagreement and insufficient sources -> human review; no executable action |
| 5 | Exact reversible actions, dry-run makes zero mutation calls, viewer denied, stale/duplicate approval/execute denied, LLM-only blocked, rollback plans and audit failures |
| 6 | All requested screens in mocks and real local fixture API mode; polling, graph state legend, approval conflicts, evidence display, pagination and keyboard paths |

Seed fixtures are shared by backend tests, generated transport contracts and MSW:
(1) benign matching change produces no finding or LOW;
(2) open SSH produces deterministic finding and, in Phase 5, proposal;
(3) worker Lambda -> DB bypass produces FORBIDDEN_PATH/REQUIRED_INTERMEDIARY HIGH;
(4) new unruled boundary path escalates and remains human review when not fully
corroborated; (5) independent-source disagreement always requires human review and
cannot create an executable action. Add a fully corroborated Tier 2 fixture too,
to test acceptance without bypassing human remediation approval.

Update `INTEGRATION.md` and `backend/VALIDATION.md` on every behavior change with
the exact commands, outcomes and scope. Keep historical results dated. A required
check that cannot run is explicitly unverified; do not call a phase fully validated
or quietly omit it. Commit each completed phase separately with its docs/tests;
leave unrelated `.DS_Store` files untouched. No phase commit has been made yet.

Planning verification: read-only source/document review, case-study text extraction,
Git baseline/status, local tool discovery and ignore check. `sam` was not found on
the current PATH, and `backend/.venv` was not present; no dependency installation,
backend/frontend test, SAM build/lint or Docker persistence check was run here.
Resolve local tooling before claiming implementation phase gates passed.

## 8. Approval decisions and remaining gates

Please approve or amend these proposed choices before Phase 1 coding:

1. Accept the manifest/rule/coverage semantics above, including UNKNOWN when SG
   permission alone cannot establish a traffic/reachability predicate.
2. Accept the explicitly requested evaluation 200 -> 202 transition, numeric
   immutable versions with active pointers, the new tables/indexes and the
   `/v1/evaluations/{id}` + `/v1/audit` route choices.
3. Accept bringing role checks forward to Phase 2 and using a local fixture worker
   plus optional DynamoDB Streams cloud transport. No cloud transport is claimed
   Academy-compatible until actual lab permissions are supplied for review.

Any future evidence that a necessary service conflicts with Academy restrictions
is a stop-and-ask gate for that cloud integration. Local deterministic/fixture
work remains possible. This approval does not authorize deployment, credential
use, service activation, or real remediation.

## 9. Public technical references

- [SAM Function role behavior](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-function.html): generated execution roles and explicit Role configuration.
- [Lambda with DynamoDB Streams](https://docs.aws.amazon.com/lambda/latest/dg/with-ddb.html): event source mapping and repeated-delivery/idempotency considerations.
- [VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html): traffic observations are distinct from a complete network-policy graph.
- [Bedrock supported models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html): model/region support must be checked before any later authorized activation.

References were read publicly during planning; they do not establish this Academy
account's allowed services, IAM policies or Bedrock access.
