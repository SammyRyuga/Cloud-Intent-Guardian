## Evidence and impact completion checkpoint (2026-10-16)

Local backend implementation is complete; this checkpoint has not yet been
rolled out. AWS Academy validation is excluded at the owner's request.

- `EnableSGAttachmentInventory` defaults off. Its bounded metadata-only helper
  combines existing EC2/RDS/Lambda SG relationships with filtered network-interface
  reads. Findings and proposal plans preserve attachment records, source coverage,
  observation time and an unknown total when coverage is incomplete. Counts are
  configuration attachment records, not unique affected workloads. Typed
  `SG_ATTACHMENT_IMPACT` coverage makes enabling a new source establish a fresh
  drift baseline instead of fabricating resource modifications. No network
  interfaces or security-group rules are created or changed.
- Tier 2 history is pinned to account/region/stage, intent version, exact path
  facts and published prior artifacts. It distinguishes FIRST_OBSERVATION,
  PREVIOUSLY_OBSERVED, NEW and UNKNOWN; drift links reference deterministic exact
  edge events only when the matching baseline permits actual staging/publication.
- Factual observation completeness is separate from policy ambiguity. Published
  SUCCEEDED or PARTIAL evaluations may establish/compare drift when actual
  resource observations are complete. Partial source data, missing artifacts,
  changed coverage and insufficient edge coverage still prevent absence claims.
  This does not upgrade conformance, confidence or remediation eligibility.
- `EnableBedrockDiagnostic` defaults off and applies only to the worker. Exact
  IAM-invoked hardcoded synthetic input permits one bounded regional inference;
  caller text, inventory and job IDs cannot enter it. Local mode and disabled
  flags prevent the SDK call. It processes no evaluation job or database state.
  The existing exact-model InvokeModel permission is sufficient.

227 backend tests passed, including SDK-stubbed bounds/denials and diagnostic
isolation. A real loopback DynamoDB Local six-evaluation journey verified first,
repeat and newly observed topology, exact persisted drift-event links, partial
source handling and attachment evidence in an approval-required proposal. No
cloud changes were made by that journey. Reproduce with
`backend/scripts/verify_candidate_history.py`; receipt is ignored under
backend/local-evidence/candidate-history-verification.json.

A fresh signed-in application write was separately verified in AWS:
`2f52463d-88cd-46b9-a238-cd4fe3e39df1` remains an unapproved diagnostic draft.
A consistent DynamoDB read and exact same-stream structured CloudWatch start/
success records independently corroborated that specific application operation.
This is observed application-role access, not a global IAM authorization or
packet-reachability claim. Receipt:
backend/local-evidence/fresh-application-access-verification.json.

The ENI permission was derived from the actual helper using IAM Policy Autopilot
0.3.0 (`generate-policies backend/src/common/sg_attachments.py --region ap-south-1
--account 513371322240 --service-hints ec2 --pretty`). Only the generated
`ec2:DescribeNetworkInterfaces` read permission is added conditionally to the
inventory and evaluation roles; generated policies were not uploaded directly.
All other source files, feature flags and `/v1` envelopes remain compatible.

The frontend redesign and final live worker verification are still in progress
at this checkpoint. No new older-finding decisions or real remediation have yet
been applied during this completion pass.

## Owner-approved activation and live evaluation (2026-10-16)

Application fix commit `5e9f660` is pushed. Render deployment
`dep-db94ijajnfac73ai001g` is verified LIVE at that commit. Backend source remains
the previously deployed `6a034b2`; activation/evaluation used existing endpoints
and required no new AWS infrastructure rollout.

Guardian intent `9af2782d-f80b-41f8-9bd7-eeefddeb672d` version 2 was approved and
activated through the signed-in Cognito frontend after explicit owner approval.
The facade now points to version 2 at revision 3; version 1 remains immutable,
approved history and is presented as SUPERSEDED. The approved content hash is
`f68b65b30f89413a2038cd08bc2c75e5f6c31c6558412fcc68b6e3d61f5f452e`.

Signed-in evaluation `43ba4996-35e7-4847-a29f-7dcebaa8efec` completed SUCCEEDED
in one attempt: **217/217 PASS, zero UNKNOWN, zero findings, 100% configuration
conformance**. It collected 96 account inventory nodes; the intent selects its
68 Guardian components and 144 required structural relationships. Polling and
history converged to SUCCEEDED in the browser. Consistent DynamoDB reads verified
the terminal job, exact content hash, version-2 drift baseline and zero drift
events. Approval, EVALUATION_SUCCEEDED and DRIFT_SNAPSHOT_PUBLISHED audit events
were verified with matching version/job IDs. The first complete snapshot is a
baseline, so zero events is expected. Five findings under older intents remain;
both previously reviewed real public-SSH findings stay OPEN.

The live approval uncovered a frontend response-parser mismatch: the activation
endpoint returns an intent facade, while the hook expected a version snapshot
with contentHash. Approval had succeeded despite the UI error. The hook now uses
the existing facade schema; the API contract is unchanged. Actual local Python
handler approval/rollback fixtures reproduce this distinction, and the regression
checks parsing plus cache invalidation. No approval was repeated to test the fix.
Current checks: 209 backend tests, 40 frontend tests, 17 contract checks, frontend
lint/build and SAM lint/build pass. Two existing Fast Refresh warnings remain.
The five earlier Chrome browser tests and this real signed-in journey are
separate evidence; no new intercepted browser run was claimed for the parser fix.

Modifying remediation remains disabled/dry-run, confirmed from stack parameters.
This success covers the approved structural configuration rules. Effective IAM
access and independent-source packet reachability remain unverified; unavailable
or conflicting evidence continues to require human review. Full ignored receipts:
backend/local-evidence/guardian-v2-activation-verification.json.

## Completion cloud receipts (2026-10-16)

- GitHub application code was pushed through `caf38fb`; backend completion is
  `6a034b2` (including `bf4e836`). Render deploy `dep-db904aavcj2c73becemg`
  is live at `caf38fb`. The final SAM rollout also reached UPDATE_COMPLETE.
- The deployed normalized-manifest regression passed input validation and
  returned the expected STALE_INTENT_REVISION 409 with a deliberately stale
  revision. Consistent before/after reads proved no intent state change.
  All 209 backend tests, 37 frontend tests, 16 contract checks, frontend lint/build,
  SAM lint/build and the five earlier Chrome browser journeys passed.
  The intent editor now labels its fictional EC2/RDS starter explicitly.
- The AWS stack reached UPDATE_COMPLETE with drift, exact-stack API/IAM/Cognito
  discovery, regional Gemma advisory escalation and evidence adapters enabled.
  Config, tag enrichment and network promotion remain off. Modifying remediation
  remains disabled/dry-run. No Flow Logs group or Analyzer paths were invented.
- Deployed ResourcesFunction invocation under its own execution role returned
  HTTP 200, 96 account inventory nodes and 169 edges, no warnings; these totals
  include other applications, while the intent selects exact Guardian assets.
  Resource and structural coverage are complete; IAM declarations are partial,
  network evidence unsupported and tag coverage partial as explicitly reported.
- Public health returned 200. Anonymous resources, audit and drift requests each
  returned 401. Signed-in browser showed Connected, required approved selection,
  SUPPRESSED finding status with the approved reason, and a working empty drift
  history view. Browser checks did not modify findings.
- Expanded Guardian version 2 is a saved DRAFT. Preview: 68 components, 144
  structural relationships, four zones and 217 PASS. Activation and its live
  evaluation await owner approval. See the version 2 review document in
  docs/intents/guardian-v2-review.md. No successful evaluation is inferred from
  the pure preview.

## Completion release validation (2026-10-16)

This section supersedes the older checkpoint below. The optional API, IAM and
Cognito collectors now resolve exact CloudFormation physical IDs, including
truncated function names, and have SAM feature flags and conditional read-only
permissions. API routes, JWT authorizers/issuers, function-role associations and
policy declarations are configuration evidence. Declared IAM allows do not prove
effective authorization; network and application access remain separate claims.
The bounded collector uses six role readers, 100 requests, 400 total rows and a
12-second deadline, with incomplete coverage on denial, caps or missing scope.

Drift now preserves protocol/ports, labels fixture evidence correctly, and gates
changes by exact resource/edge coverage rather than unrelated partial tag reads.
The eight-table DynamoDB Local journey passed baseline/change/retry/publication,
pagination/detail, partial-snapshot deletion prevention and new-version baseline
checks. It used an isolated loopback-bound official DynamoDB Local JAR because
Docker Desktop was unavailable; no existing database was replaced. Reproduce with
`backend/scripts/verify_drift.py` after `local_db.py init`. Receipt (ignored):
`backend/local-evidence/drift-verification.json`.

Regional synthetic Bedrock calls to `google.gemma-3-4b-it` succeeded twice in
ap-south-1 (648 total tokens). The exact live response passes the strict client
parser. Only a whole JSON object or an exact whole json code fence is accepted;
extra keys, duplicate keys, wrong candidate bindings and surrounding text fail.
Witnessed unruled crossings remain eligible for review under partial coverage.
Missing required edges without a witnessed path never become path-present model
candidates. Relationship-only v2 policies also surface positive undeclared
relationships; legacy attribute-only manifests keep their existing behavior.
Two independent predicate/snapshot-bound sources remain mandatory for accepting
an advisory conclusion. Missing sources, disagreement, model errors and access
denial remain human-review outcomes. This does not prove deployed worker-role
Bedrock invocation or real packet reachability. No cross-region inference or
Marketplace agreements were used.

Owner-approved review suppressed exactly three historical missing-EC2 findings
through the deployed lifecycle handler, with optimistic revisions and an atomic
audit event for each. Both previously reviewed public-SSH findings remain OPEN;
newer findings were not changed. No AWS resource remediation occurred.

Local checks: 209 backend tests and SAM lint/build passed after the collector
fixes. Frontend checks: 37 tests, 16 contract checks, strict TypeScript production
build and lint passed (two existing Fast Refresh warnings). Lifecycle controls
require a suppression reason and expected revision, preserve server failures,
and expose audited suppression/reopen provenance. Evaluation submission uses an
explicit approved intent and active version, with paginated selection; no silent
newest-intent fallback. Five Chrome browser journeys also passed, including lifecycle success, 403/409
failures, terminal status/history convergence and paginated approved selection.
A live version-creation check exposed a manifest round-trip defect: normalized
boundary crossings include `via: []`, which input validation previously rejected.
Empty optional boundary intermediaries are now accepted without changing canonical
content or hashes; REQUIRED_INTERMEDIARY still requires a nonempty list.
Current rollout receipts are recorded at the beginning of this document. Academy IAM role creation, optional service permissions
and Bedrock entitlement remain unverified in an Academy account. The normal
owner-authorized ap-south-1 account is distinct from Academy. Remediation remains
disabled/dry-run; unsupported or absent evidence is never converted to PASS.

## Remaining-work checkpoint (2026-10-16)

Saved locally tested snapshot-drift API/UI and disabled API/IAM/Cognito collector
prototypes. This checkpoint has **not been deployed**. The live Guardian baseline
and its seven passing structural rules remain the last verified deployed scope.

Final checks: 187 backend tests, 34 frontend tests, 14 contract tests, SAM lint,
SAM build and frontend lint/build passed. GPT-6.1 Sol verified the new collectors,
drift and frontend suites; the final combined backend suite was rerun after all
changes. Two existing Fast Refresh warnings remain. New drift persistence tests
use Moto; the eight-table DynamoDB Local drift journey and deployed drift remain
unverified. Drift defaults off. API/IAM/Cognito collector flags are absent from
SAM and default off in code until Guardian-only scope filtering/IAM wiring is
completed. Do not enable the prototypes account-wide as a Guardian-only claim.

Regional Bedrock runtime calls succeeded with synthetic data, but the model's
output failed the strict conclusion schema. LLM activation stays off. Existing
Flow Logs/Reachability paths remain absent. DynamoDB plus structured CloudWatch
records corroborated one historical application write, not packet reachability or
general effective IAM access. Five earlier findings were reviewed without state
changes: two reference one real public-SSH group outside Guardian; three reflect
older EC2 baselines. Details and next steps: [checkpoint](../docs/CHECKPOINT.md).

## Guardian serverless intent and evidence collection (2026-10-16)

The owner confirmed the target is Cloud Intent Guardian itself. The earlier
EC2/RDS tier selectors describe other applications in the account, so they are
not silently retargeted or approved. A concrete review draft is stored in ignored
`backend/local-evidence/guardian-intent-review.json`, with exact verified ARNs
for 12 API Lambda functions, one evaluation worker and seven DynamoDB tables.
It requires the evaluations-table stream trigger to the worker, and evaluates
compute/data boundaries with structural evidence. It does not claim API invocation,
IAM data authorization, or packet-level network coverage.

New opt-in SAM parameters EnableDynamoDBInventory and EnableServerlessRelationships
add bounded metadata-only ListTables/DescribeTable and ListEventSourceMappings
reads. EnableLambdaInventory must also be on to resolve both mapping endpoints.
Only enabled mappings to the current enabled table stream and exact observed
function/table ARNs produce DYNAMODB_STREAM_TRIGGER edges. Cross-scope,
unresolved, stale, transitional, denied or capped collection remains incomplete;
disabled mappings do not emit active edges. Collection never reads table items
or Lambda environment variables. Local mode blocks SDK client construction.
Each source is capped at 100 records. Optional services remain off by default.

Intent v2 trustBoundaries now accepts optional edgeTypes using the existing
STRUCTURAL, NETWORK_PERMISSION, NETWORK_REACHABILITY categories. Omission keeps
the original network default and normalized content shape, preserving approved
version hashes. STRUCTURAL includes DynamoDB stream wiring. Existing /v1 paths,
response envelopes and error shape are unchanged. Frontend transport tests verify
new field retention and legacy omission.

EnableNetworkEvidence optionally enriches worker evaluations from existing Flow
Logs and Reachability Analyzer records independently of Bedrock. It is off by
default, permanently off locally, and does not run in synchronous graph requests.
At most two exact endpoint/TCP-or-UDP/single-port bindings are queried, with
invocation-scoped client reuse. Observed accepted flow records produce scoped
reachability witnesses; Analyzer models configuration and produces permission
witnesses. Disagreement suppresses promotion. Negative/missing records never
prove global absence. Scoped witnesses cannot satisfy other protocols, ports,
unscoped paths or transitive boundary checks; graph coverage remains PARTIAL.
Integral DynamoDB Decimal ports are normalized safely. No analyses/logs are
created, and Bedrock/modifying remediation remain disabled in the live prototype.

Academy: the new flags may require unavailable read permissions; service denials
degrade coverage. Generated execution roles still require IAM role creation or
an explicitly pre-approved existing role. The normal-account deployment does not
verify Academy availability. No Step Functions, provisioned capacity or idle
compute was added.

GPT-6.1 Sol validation passed 170 backend tests, SAM lint/build, all five isolated
DynamoDB Local escalation/remediation scenarios, 33 frontend tests, 13 contract
tests, frontend lint/build and the rendered Chrome evaluation-status regression.
Lint retains two existing Fast Refresh warnings. Enabled and disabled stream
integration tests prove structural conformance without claiming network coverage.
Released implementation commit `6545469`. AWS stack cloud-intent-guardian-demo
reached UPDATE_COMPLETE; Render deploy `dep-db8o847f3r2c73eqf5t0` is live.
Lambda/DynamoDB/serverless mapping discovery is enabled. Network enrichment,
Bedrock, Config and modifying remediation remain off; remediation stays dry-run.
The disposable DynamoDB Local verification container was removed.

Deployed ResourcesFunction returned HTTP 200, 48 account resources, no warnings,
and COMPLETE Lambda/DynamoDB/structural/stream coverage. Of these, the Guardian
manifest binds 13 Lambda functions and seven tables. The unapproved diagnostic
preview passed 7/7 with zero findings and was saved separately without publishing
an evaluation. Exact IDs/inventory stay in ignored local-evidence files.

A review draft was created through the deployed handler as Deployment operator
(review draft), ID `9af2782d-f80b-41f8-9bd7-eeefddeb672d`. The owner then explicitly
approved activation and a live evaluation in chat. GPT-6.1 Sol used the signed-in
Cognito UI to approve version 1 and submit evaluation
`d9750c08-cc02-49ec-af1d-b1e387ef8fc2`. Its stored status and history both reached
SUCCEEDED automatically, with 100% conformance and all seven declared rules
passing. Browser warning/error logs were empty. Actual graph shows the observed
DYNAMODB_STREAM_TRIGGER. Five active findings from earlier intents remain;
no finding was suppressed or remediated to obtain the new result. This result
covers the declared structural baseline, not unmodeled IAM/network/API policies.
Real positive network-source/Bedrock integration and Academy IAM remain unverified.

## Evaluation status consistency correction (2026-10-16)

Overview no longer treats the POST acceptance snapshot as current job status.
Its acceptance acknowledgement contains the evaluation ID; the polled detail
supplies the current status. Terminal transitions invalidate evaluation history
and dependent results, keyed by evaluation ID so consecutive runs ending in the
same status also refresh. The visible history page polls unfinished jobs for a
bounded window, covering runs started before this page was opened and brief GSI
propagation delays. Polling stops for terminal jobs and forbidden/not-found responses.
Existing /v1 routes, 202 acceptance envelopes and stored statuses are unchanged.

PARTIAL detail explains that full conformance is unavailable and displays
server-provided UNKNOWN rule explanations and warnings. This does not upgrade
incomplete evidence to success. Strongly consistent inspection of the reported
job b965dfb2-5911-4a1e-b1f8-e6fab74ac6c4 confirmed PARTIAL, 25 resources,
two violations, four unknown rules and no warnings. Unknowns concern database
component resolution, boundary membership/edge coverage and relationship endpoint
resolution. The dashboard counts active findings across the configured scope;
that count is distinct from violations produced by this individual run.

GPT-6.1 Sol independently ran all 145 backend tests, SAM lint/build and the
isolated DynamoDB Local five-scenario verifier with escalation and remediation.
All passed, including version/audit checks and dry-run proposals. Evidence:
`/private/tmp/cig-status-validation-topology.json`. The temporary verification
container was removed. The GPT-6.1 Sol frontend verification passed 32 unit
tests, 13 contract tests, lint (two existing Fast Refresh warnings), production
TypeScript/Vite build and a controlled rendered Chrome regression. The regression
covers pre-existing QUEUED history plus four successive runs: PARTIAL, PARTIAL,
SUCCEEDED and FAILED, checking convergence, explanations, errors and button state.
The controlled browser test ran with
`CIG_E2E_BROWSER_CHANNEL=chrome npm run test:e2e -- evaluation-status.spec.ts`
from frontend/. Its optional per-test channel setting uses installed Chrome when
the bundled Chromium executable is unavailable.

Released application commit `3c49207`; Render deployment
`dep-db8nugbl550s73eisthg` is live. GPT-6.1 Sol verified the deployed app in a
fresh signed-in Brave tab: the original evaluation shows its four UNKNOWN
explanations. A new real evaluation, `189e311b-5456-4f98-8111-6028b63ea7d6`,
progressed from RUNNING/COLLECTING to PARTIAL automatically. Current status and
history both became PARTIAL without manual refresh, last-evaluated updated,
the Run evaluation button re-enabled, and no browser error logs were recorded.
The acceptance acknowledgement remained neutral rather than showing stale
QUEUED. No intent approval or modifying remediation was performed. Optional
Bedrock and evidence-source runtime integrations remain disabled/unverified.

## Overview evaluation and proposal count correction (2026-10-16)

A live read found no saved intents in the demo account. Evaluation therefore
returns HTTP 409 `NO_APPROVED_INTENT`: create and explicitly approve an intent
before evaluating it. The frontend now retains the backend's error code/message
and offers an Intents link instead of presenting every 409 as a concurrent edit.
No baseline is created or approved automatically.

`GET /v1/dashboard/summary` now reads scoped remediation proposals and reports
`features.remediation=true` and the count of PROPOSED, APPROVED or EXECUTING
proposals. A bounded/incomplete proposal scan yields a null count and
`partial=true`; the frontend labels this unavailable. ViewsFunction has read-only
access to the proposals table. Execution remains disabled and dry-run remains on.
Standalone drift-event history is still unimplemented and remains Not enabled.
The /v1 routes and response envelopes are unchanged.

Validation passed: 145 backend tests, 30 frontend tests, 13 contract tests,
SAM validation with lint, SAM build, frontend lint/build and git diff checks.
Frontend lint reports two existing Fast Refresh warnings. Tests cover scoped
pending proposal counts, incomplete scans, backend conflict messages, the Intents
link and unavailable-versus-disabled count labels. A deployed Lambda invocation
with a synthetic admin event confirmed the exact NO_APPROVED_INTENT response;
this bypasses API Gateway JWT authorization. Subsequent verification in the
owner's already signed-in browser confirmed the real protected API response,
correct prerequisite message and Intents link, and Pending Remediations = 0.
No password or token was accessed. No intent was created or approved.

Released application commit: `0408d06`. AWS stack reached UPDATE_COMPLETE.
Render deploy `dep-db8il2ks728c738rcm8g` is live on the same site. Render had not
automatically built the pushed commit, so the existing service was deployed
explicitly. A deployed ViewsFunction check returned HTTP 200, partial=false,
openRemediations=0 and features.remediation=true. The signed-in browser showed
those same values after refresh. Successful evaluation still requires an
owner-approved intent; no successful live evaluation is claimed by this fix.

## Working prototype deployment (2026-10-16)

User-authorized deployment is live at **https://cloud-intent-guardian.onrender.com**.
Source: https://github.com/SammyRyuga/Cloud-Intent-Guardian, application commit
`d081ac1` (Phase 6 code: `cbc11c9`). Render service
`srv-db8ibed9fdbs73edk180`, verified deploy `dep-db8idgei0phs73fpl62g`.
The existing DBTHON service was not changed.

AWS stack `cloud-intent-guardian-demo` reached CREATE_COMPLETE in ap-south-1
using the user-confirmed profile. API:
https://psqyc1ltj1.execute-api.ap-south-1.amazonaws.com . Cognito pool
`ap-south-1_1KdLuvAmM`, public web client `39n4qosui6478c7ar8tsr6g8fj`.
These identifiers are public frontend configuration, not secrets. The worker's
DynamoDB event source mapping is Enabled. Config, Bedrock, optional evidence
reads and modifying remediation are disabled; remediation remains dry-run.

Verified live: health HTTP 200; unauthenticated intent request HTTP 401; exact
Render-origin CORS preflight HTTP 204; root, /login and /overview HTTP 200 with
the current production bundle. A fresh browser tab reached the configured
Cognito hosted sign-in form with the correct callback, client and PKCE S256.
No password or token was entered or retrieved. An initial admin invitation was
accepted by Cognito, and group membership was confirmed as `admin`. The first
sign-in requires the owner to change the temporary password sent by Cognito.

Direct IAM-authorized deployed Lambda readiness checks (synthetic viewer event,
not a Cognito JWT request) returned status 200: source readiness CONNECTED and
25 inventory resources with partial=false. No intents were created/approved by
these live checks. A successful real JWT sign-in and protected end-to-end write,
evaluation and approval journey remain unverified until the owner signs in.
The local five-scenario/DynamoDB workflow and all 143 backend, 26 frontend and
13 contract tests passed separately; SAM lint/build and frontend build passed.

The initially open browser tab retained an old pre-configuration bundle and tried
the placeholder auth domain. Automatic review blocked that attempt. Inspection
proved the current bundle contains the actual API/pool/domain and no placeholder;
a fresh tab then reached the correct Cognito UI. No blocked navigation was bypassed.

No Flow Logs or Reachability Analyzer paths existed in the selected region when
checked. The live adapters are implemented and SDK-stubbed, but positive live
cross-validation and Bedrock runtime access are unverified. Academy restrictions
are not established by this deployment to the user's normal AWS account.

## Live evidence adapters and deployment authorization (2026-10-16)

The Phase 4 live collection gap is closed in code. Optional read-only adapters
consume an existing default-format VPC Flow Logs group and existing Reachability
Analyzer paths/results. `EnableEvidenceSources=false` remains the default;
`FlowLogsGroupName` and `CrossValidationPathsJson` configure existing sources.
No paths, analyses or logs are created. Reads are bounded to 20 log events and
100 analyses per candidate, with a five-minute evidence window and exact
resource/private-IP/protocol/port validation. Missing, inaccessible, malformed,
stale or mismatched evidence yields UNKNOWN. Local mode cannot construct AWS
clients. Reachability Analyzer models configuration, not actual application
sessions; corroboration means a directed network path is possible, not that
traffic traversed an intended application intermediary.

Live verdicts come only from these adapters, never model/inventory metadata
claims. Two independent families/origins must agree before a Tier 2 conclusion is
accepted; disagreement still requires human review and no Tier 2 action is
executable. Tests cover both native SDK-stubbed sources feeding cross-validation.
All 143 backend tests passed. Earlier notes below describing unimplemented live
collectors are superseded by this section.

The user explicitly amended the original no-AWS/no-deployment restriction:
profile `ryan`, ap-south-1, and a working AWS backend plus Render frontend are
now authorized. The user confirmed `ryan's workspace` and the first admin email
invitation. Existing real credentials are used only by the authorized deployment
and readiness commands; credential values are never retrieved or logged. Local
unit/persistence tests continue to use isolated dummy credentials.

Read-only checks confirmed the selected account and found no existing Flow Logs
or Reachability Analyzer paths in ap-south-1. Positive live cross-validation is
therefore not verified. The S3 inventory IAM action was corrected to
`s3:GetBucketPublicAccessBlock`, per the [S3 API reference](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetPublicAccessBlock.html).
Pre-deploy IAM review also added the worker audit GetItem permission needed for
idempotent retry recovery and the remediation ConditionCheckItem permission needed
for atomic finding guards. Deployment results will be recorded after verification. Config,
Bedrock/evidence-source activation and modifying remediation remain disabled.

## Phase 6 - integrated frontend and final checks (2026-10-16)

The React app now provides v2 JSON intent editing/viewing, immutable version
selection/diff/rollback controls, INTENT/ACTUAL/DIFF graph classifications and
component highlighting, async evaluation history/detail polling, finding severity
factors and cross-validation evidence, proposal approval/dry-run execution and
paginated audit history. Local controls follow explicit backend capabilities.
Unsupported uploads, standalone drift events and on-demand explanation routes
remain disabled in live mode. Existing styles and app structure are preserved.

Mocks now use valid three-tier declarations, independent version snapshots and
semantic diffs. Remediation mocks enforce status/revision/expiry/reason checks,
show concrete diff/rollback plans and record the same terminal status, revision 4
and audit transitions as the backend. All mock evidence stays visibly simulated.
The local API e2e assertions now follow advertised features instead of assuming
all new workflows are unavailable.

Rendered smoke verification used Brave through CUA against an isolated loopback
Vite mock server. Passed: v2 creation; v1-to-v2 relationship diff; new draft
version; graph legend/component highlight; evaluation history/detail; simulated
Tier 2 source evidence; proposal approval then DRY_RUN_COMPLETE at revision 4;
and the corresponding audit rows. Screenshots were emitted in tool output;
no screenshot file was saved. The mock server was stopped. This proves rendering
with simulated responses, not a deployed or live AWS integration.

Final hardening rejects malformed/unexpected source-record shapes, unknown or
missing remediation confidence, legacy findings without a revision, and proposals
whose resource/type/account/region differs from their finding. Target binding is
checked before execution; regression cases cover altered stored target fields.

Final gates: backend 130/130 tests, frontend 26/26 tests, 13/13 contract tests,
frontend lint (two existing Fast Refresh warnings), production build, SAM
`validate --lint`, SAM build and `git diff --check` passed. The architecture
chunk is 84.97 kB gzip. The DynamoDB Local five-scenario/version/audit/approved
dry-run verifier passed again (`local-evidence/phase6-topology.json`).

Not run: automated Playwright e2e (Chromium executable unavailable), deployed
Cognito/API Gateway, Academy IAM/service/region checks, real Bedrock, live
independent-source collection/corroboration or modifying AWS calls. Live source
collectors are not implemented; live ambiguous results therefore require human
review. Bedrock, Config, optional inventory and cloud execution defaults remain
off; local execution always stays dry-run. No deployment or real credentials
were used. These boundaries also apply to the earlier phase reports below.

## Phase 5 - approved remediation proposals (2026-10-16)

New routes: GET/POST `/v1/remediations`, GET `/v1/remediations/{proposalId}`,
POST `/{proposalId}/approve` and POST `/{proposalId}/execute` under that prefix.
List returns `{items,count,nextToken}`; mutations/detail return `{item}`. Creation
requires admin and `{findingId,actionId}`. Approval requires approver (or admin),
`{expectedRevision,reason}` and an unexpired unchanged finding. Execution requires
admin and `{expectedRevision}` after approval. Viewer can read. Every transition
and audit event is transactional, with conditional revision guards. Proposals
expire after 24 hours. Execution is separately claimed to prevent duplicate calls;
uncertain failures stay FAILED with human review, never automatically retried.

The closed registry supports `REMOVE_OPEN_SSH` and `ENABLE_S3_BLOCK_PUBLIC_ACCESS`.
Plans preserve the exact public ingress permissions or all four prior bucket
settings, show the change, and include a rollback plan (including delete of an
originally absent bucket configuration). Unknown prior settings prevent proposals.
Security-group attachment impact is explicitly unknown, so all proposals require
approval. There is no automatic action path. LOW-confidence, Tier 2, suppressed
and resolved findings cannot produce executable proposals.

Findings advertise `remediationAvailable` plus an allowlisted `remediationActionId`
only when a complete plan can be built. System status advertises proposal support;
local fixture mode also advertises evaluations. `RemediationEnabled=false` and
`RemediationDryRun=true` are the infrastructure defaults. Local execution ALWAYS
stays dry-run, even with flags changed. Modifying IAM permissions appear only
when both cloud execution flags explicitly permit writes. A proposal pins its execution mode before approval; later flags cannot turn a
dry-run proposal into a modifying action. Actual execution checks
account identity and current AWS state before invoking a fixed SDK method.
Academy write permissions and real execution remain unverified and were not used.

Added encrypted retained on-demand RemediationsTable and local init/probe schema.
`local-env.example.json` includes all seven tables and safe feature defaults;
`local-env.json` remains ignored. No secrets or real credentials were used.

Validation: 128 backend tests passed, including 14 remediation tests with Moto,
SDK Stubber, authorization, audit atomicity, expiry/staleness, successful stubbed
nonlocal execution, identity mismatch and changed-state rejection. All five seed
scenarios plus proposal/approval/dry-run persistence passed in DynamoDB Local
(`verify_topology.py --escalation --remediation`); all seven table/index probes
passed. Frontend lint/test/contract/build and SAM lint/build passed. These are
local/stubbed checks; real AWS, deployed API Gateway and Cognito remain unverified.

## Phase 4 - advisory escalation (2026-10-16)

`EnableLLM=false` is the default. Optional worker escalation uses an `LLMClient`
interface, deterministic local mock, or bounded Bedrock Converse text call with an
explicit model ID/ARN. No model is selected automatically. An exact closed JSON
schema rejects unknown keys, duplicate keys, invalid verdicts and mismatched IDs.
Only ambiguous witnessed topology candidates are escalated; clear Tier 1 results
make no model call. At most three candidates are assessed per evaluation.

Tier 2 findings add `tier`, `reviewStatus`, `confidence`, `crossValidation`,
`llmConclusion`, `llmStatus` and `actionEligible=false`. Two independent source
families and origins must agree on the same predicate, path, snapshot and time.
Disagreement or insufficient evidence yields `NEEDS_HUMAN_REVIEW` and LOW
confidence. Corroboration confirms evidence, not permission to modify architecture.
Flag-off, denied access, missing model, timeout and invalid output degrade safely.

Live source collectors are **not implemented**. Only explicitly simulated local
fixture records can currently pass corroboration; live candidates always need
human review. CloudTrail events alone cannot prove current path reachability.
Academy Bedrock access/region and existing-role permission remain unverified.
The implementation follows the public [Converse reference](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html).

Async hardening: scoped status polling reconciles expired jobs; history reads
refuse silently incomplete legacy indexes with a migration error; finding writes
reject pre-existing records outside their scope/intent. No periodic cloud
reconciler is enabled, so an abandoned job becomes FAILED on status polling.

Validation: 114 backend tests passed, including an SDK-stubbed Converse call,
malicious output, source disagreement/duplication/staleness and Unicode artifact
round trips. The isolated DynamoDB Local verifier with `--escalation` passed and
persisted both corroborated and human-review findings. SAM lint/build and frontend
lint/test/contract/build gates passed. No real credentials, deployment, Bedrock
invocation, API Gateway or live Cognito verification occurred.

## Phase 3 - severity evidence (2026-10-16)

Findings now include `constraintSeverity`, `confidence`, `severityScore` (0-100),
and `severityFactors`, preserved by list/detail responses and displayed in finding
detail. Formula v1 adds base severity (INFO 5, LOW 15, MEDIUM 35, HIGH 60,
CRITICAL 80), component criticality (0/5/10/15), up to 10 points for unique
observed downstream nodes, exposure (PUBLIC 10, INTERNAL 0, UNKNOWN 5), and
confidence uncertainty uplift (HIGH 0, MEDIUM 2, LOW 5), capped at 100. Labels
start at 10/30/60/85 for LOW/MEDIUM/HIGH/CRITICAL. Missing criticality defaults
to MEDIUM; incomplete reachability is explicitly a lower bound. Structural or
configured edges do not count as observed traffic. Scores never authorize action.

Validation: backend 102 tests passed with the cached Python 3.14 dependencies;
frontend lint passed (two existing fast-refresh warnings), 24 tests and 13
contract tests passed, production build passed. SAM lint and build passed.
The isolated DynamoDB Local async verifier passed all five seed scenarios,
versioning and audit, recording `backend/local-evidence/phase3-topology.json`.
These direct handler/worker checks do not verify API Gateway, real Cognito,
Academy permissions, live reachability, Bedrock or modifying AWS actions.

# Validation of the local persistence patch

## Phase 2 validation - 2026-10-15

Implemented transactional immutable version snapshots/activation/rollback,
asynchronous queued evaluation/status/history, scoped group authorization,
append-only audit, and human finding lifecycle transitions. Existing `/v1` and
envelopes remain; the approved evaluation POST change is 202 with a status URL.

Checks run on this phase:

- **93 backend tests passed** using the same cached Python 3.14.8/boto3/Moto
  environment documented below. Added coverage includes role claim forms and
  denial, audit rollback on storage failure, suppression reason/revision conflicts,
  version immutability/supersede/rollback and semantic diffs, explicit legacy
  migration, pinned jobs, scope-bound history, bounded artifact hashing, duplicate
  delivery and retry after complete artifacts. Legacy botocore Stubber tests now
  check transactional create/approval rather than the replaced single writes.
- **DynamoDB Local validation passed** on isolated port 18000. `init` added the
  three tables and new indexes; `migrate` explicitly backfilled earlier local
  records. The enhanced `verify_topology.py` exercised all five async seed
  scenarios plus version creation/approval/rollback, immutable v1 snapshot and
  audit reads. Intent ID: `206c680f-27e2-437b-aceb-70fc1dd51cab`. Ignored evidence:
  `backend/local-evidence/phase2-topology.json`. These are direct handler + worker
  invocations against a real local database, not API Gateway/Cognito evidence.
- **SAM validation/lint and Python 3.13 build passed**, with public build wheels
  resolved offline as below. No deployment or live AWS API was called.
- **Frontend gates passed:** lint (two existing fast-refresh warnings), tests
  24/24, contract tests 13/13 and production build. The architecture chunk is
  84.39 kB gzip. Both contract fixture files came from actual backend handlers.
- Python syntax and `git diff --check` passed; `local-env.json` remains ignored.

Run the same backend/SAM commands below and the updated local commands in
`INTEGRATION.md`. The verifier now queues 202 jobs and explicitly runs their
worker. The earlier Phase 1 commands/results remain historical.

Not verified: deployed JWT/group validation, real Cognito user assignment,
Academy permissions for role creation/PassRole/Cognito/Streams, actual stream
delivery/retry/deadline timing, cloud migration/backfill, or live inventory.
Cloud worker transport is disabled by default; local mode needs no Streams.
The 48-resolution transaction cap is a deliberate bounded-work limit; larger
reconciliations do not silently clear findings. GSI reads can lag; direct status
reads are consistent. Local in-memory database durability was not tested.

Severity scoring, Bedrock/cross-validation and remediation remain later phases.

## Phase 1 validation - 2026-10-15

Implemented v2 manifests, deterministic relationship/path/boundary rules,
coverage-aware graph comparison and explicit local fixture observations. Existing
v1 envelopes and attribute finding IDs remain intact. Phase 2 async/version/audit,
Phase 3 scoring, Phase 4 Bedrock/corroboration and Phase 5 remediation are not
implemented by this phase.

Checks run against this phase:

- **75 backend tests passed** with Python 3.14.8, cached boto3 1.43.108 and Moto
  5.2.4. Tests include the original botocore Stubber contracts, Moto-backed handler
  workflows, pure topology/manifest rules, and fake SDK inventory clients. They
  cover legacy manifests, v2 approval round trips, complete/partial coverage,
  component cardinality, selector ambiguity, all five topology rules, missing
  attributes, stable finding IDs, conservative resolution and local-only fixtures.
- **DynamoDB Local workflow passed** against a newly isolated container
  `cig-phase-validation`, loopback port 18000. Tables were initialized with
  `scripts/local_db.py init`, then `scripts/verify_topology.py` called the real
  Lambda handlers and checked consistent reads and all graph views. Benign:
  SUCCEEDED/no finding; open SSH: SUCCEEDED/deterministic finding; Lambda DB bypass:
  SUCCEEDED/path findings including HIGH; unruled crossing and source-disagreement
  seeds: PARTIAL/no fabricated conformance. Intent ID:
  `6f586f63-9823-428f-a348-853d90309723`. Ignored evidence:
  `backend/local-evidence/phase1-topology.json`.
- **SAM lint/validation and build passed** using SAM CLI 1.168.0. Build targets
  Python 3.13/x86_64; dependencies were resolved from public wheels downloaded to
  `/private/tmp/cig-phase-wheels`, with `PIP_NO_INDEX=1`. No cloud API was used.
- **Frontend gates passed**: `npm run lint` (three existing warnings), `npm test`
  (20/20), `npm run test:contract` (10/10) and `npm run build`. Generated real
  handler responses validate in both languages. The architecture chunk is
  83,476 bytes gzip, within the documented 250 kB gzip budget. No new rendered
  browser journey was run in this phase; the earlier browser evidence remains dated.
- `git diff --check` and Python compilation passed. `local-env.json` remains
  ignored. No existing database/container was replaced.

Reproduction commands on this host (from repository root, except SAM build):

```bash
CIG_CONTRACT_OUTPUT=frontend/tests/fixtures/backend-contract.json \
CIG_TOPOLOGY_CONTRACT_OUTPUT=frontend/tests/fixtures/topology-contract.json \
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
python3.14 -S -m unittest discover -s backend/tests -v

cd backend
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
python3.14 -S scripts/local_db.py init --endpoint http://127.0.0.1:18000
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
python3.14 -S scripts/verify_topology.py --endpoint http://127.0.0.1:18000

PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
SAM_CLI_TELEMETRY=0 AWS_EC2_METADATA_DISABLED=true \
python3.14 /private/tmp/cig-test-venv/bin/sam validate --lint
PIP_NO_INDEX=1 PIP_FIND_LINKS=/private/tmp/cig-phase-wheels \
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
SAM_CLI_TELEMETRY=0 AWS_EC2_METADATA_DISABLED=true \
python3.14 /private/tmp/cig-test-venv/bin/sam build
```

The cached virtualenv's original Python symlink is stale; the explicit interpreter
and `-S` avoid reliance on it and on unrelated host site packages. For a normal
checkout, install `requirements-dev.txt` into a working project virtualenv and
use its Python/SAM commands. PyPI DNS was unavailable inside the sandbox; public
build wheels were downloaded with the permitted network path. Docker Desktop was
started locally and Docker access required sandbox escalation.

Still unverified: deployed Cognito JWT/group enforcement, Academy IAM/region/service
availability, live AWS inventory/tag/Lambda permissions, real network reachability,
API Gateway integration for these new paths, independent-source cross-validation,
Bedrock and all modifying actions. The local verifier directly invokes handlers;
it does not prove deployed API authorization or persistence across an in-memory
container restart. The source-disagreement fixture is intentionally only an UNKNOWN
candidate until Phase 4 implements corroboration.

The original dated records below are retained as historical evidence.

Run date: 2026-10-13. Baseline inspected: `b479f32`.

Confirmed in this workspace:

- Seven `unittest` tests passed using cached Boto3 1.43.111 and botocore Stubber: local endpoint required; cloud endpoint rejected locally; local endpoint rejected outside local mode; production uses the default role/session; local client endpoint/timeouts/signing isolation; create/list/detail/approval response contracts; structured connection failure.
- Python AST parsing passed for backend Python files.
- `bash -n backend/scripts/diagnose-local.sh` passed.
- `git diff --check` passed.

The stubbed tests perform no service network calls and prove no DynamoDB persistence or SAM connectivity. Test responses are explicitly provided by botocore Stubber. The test code is committed and runs with `python -m unittest discover -s tests -v` after installing the existing requirements. In this workspace package installation failed because PyPI DNS resolution was unavailable; tests were run by adding already-cached package directories to Python's import path.

Not run/proven here:

- SAM validation/build/API emulation: SAM executable unavailable.
- Real DynamoDB Local writes/reads: Docker's daemon socket unavailable.
- The user's Windows network/container/environment state.
- Cognito authorization, live inventory/evaluation, Academy permissions, production deployment or resource costs.

The user's previously reported successful SAM validation/build, health calls and invalid-input calls remain user-reported evidence for their earlier code. They are not rerun results for this patch.

Use `LOCAL_TESTING.md` to run the runtime probe and the real four-part persistence verification on the machine with SAM and the existing database container. Only that verification can establish the immediate live milestone.

## Subsequent integration validation

The original limitations above describe the initial patch, not the current validation state. On 2026-10-13, SAM validation/build, real SAM-to-DynamoDB Local persistence, thirteen Python tests, seventeen frontend tests and two browser integration journeys passed. The database was isolated and temporary. See [current integration evidence](../INTEGRATION.md). Live AWS deployment and Cognito remain unverified.

### Snapshot drift implementation checks

Added deterministic snapshot change tests for actual resource attributes, edge
removal with preserved before-state, collection timestamp noise, partial/missing
coverage, first baseline, duplicate staging, published-only visibility and scoped
viewer reads. Five focused drift tests passed with Moto; the preceding complete
backend suite passed 174 tests. Frontend production build and 14 contract tests
passed. SAM template lint passed. These are local checks; no drift cloud deployment
or live evaluation has been performed by this change.
