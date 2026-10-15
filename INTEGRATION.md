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

# Frontend/backend integration

## Phase 2 additions (2026-10-15)

The current contract now includes immutable intent versions, activation/rollback,
async evaluation/history, append-only audit and finding lifecycle transitions.
The Phase 1 and older baseline sections below remain dated historical context.

`POST /v1/evaluations` retains `{intentId}` / `{}` input and adds optional numeric
`intentVersion` and `reason`. It now returns **202**, replacing the previous
synchronous 200 response, as approved:

```json
{"evaluation":{"evaluationId":"server-generated-id","status":"QUEUED","intentId":"intent-id","intentVersion":1,"createdAt":"UTC timestamp"},"statusUrl":"/v1/evaluations/server-generated-id"}
```

`GET /v1/evaluations` returns `{items,count,nextToken,limit}`, optionally filtered
by intentId/status. `GET /v1/evaluations/{id}` returns `{item}` with QUEUED,
RUNNING, SUCCEEDED, PARTIAL or FAILED, stage, timestamps, summary/conformance and
safe error fields. The frontend polls this route with backoff and terminal/error
stop conditions. It has no `/v1/jobs` dependency. A 202 is acceptance, not a
completed evaluation. Dashboard conformance reads completed published evaluations;
queued work cannot erase earlier results.

The worker pins the approved version/content hash when the job is created, uses
conditional claims and bounded retries, serializes publication per intent, and
stores hash-checked snapshot/result/finding artifacts in bounded chunks. Completed
artifacts are reused on retries. Findings retain lifecycle metadata and stable
IDs. Complete PASS-based resolutions are committed with terminal publication and
audit in one transaction, capped at 48 resolutions per job; a larger reconciliation
requires human/operator review rather than an unbounded transaction. Partial or
unknown evaluation never clears findings. No modifying AWS SDK call is implemented.

New intent endpoints:

| Route | Behavior |
| --- | --- |
| GET/POST `/v1/intents/{intentId}/versions` | Paginated history / create a draft `{manifest,expectedRevision}` |
| GET `/v1/intents/{intentId}/versions/{version}` | Immutable numeric snapshot with derived effectiveStatus |
| POST `/v1/intents/{intentId}/versions/{version}/approve` | Approve and activate with expectedRevision |
| POST `/v1/intents/{intentId}/rollback` | `{targetVersion,expectedRevision,reason}` moves only the active pointer |
| GET `/v1/intents/{intentId}/diff?fromVersion=1&toVersion=2` | Semantic declaration changes; reorder-only edits are ignored |

Initial create/detail/list/approve envelopes remain intact, with additive
`latestVersion`, `activeVersion`, `revision` and server scope. Initial repeated
approval stays idempotent; new stale mutations return 409. Approved snapshots are
never edited by rollback or superseding. A graph's explicit version can select a
historic approved snapshot. Legacy records require explicit local migration, not
an implicit write from a read/approval request.

`GET /v1/audit` returns a scope-bound paginated list, optionally filtered by action
and UTC from/to bounds. The backend records the verified subject, action, target,
time, result and request/evaluation correlation. There is no audit mutation API.
Audit entries and associated state changes commit transactionally. This is
application append-only behavior, not a claim of tamper resistance against an
account administrator.

`PATCH /v1/findings/{findingId}` accepts `action: ACKNOWLEDGE|SUPPRESS|REOPEN`,
`expectedRevision` and optional `reason`. Suppression requires a reason. Stale or
invalid transitions return 409. Resolution remains evaluation-driven. Review
status is separate from lifecycle; the four existing lifecycle statuses remain
OPEN, ACKNOWLEDGED, RESOLVED and SUPPRESSED.

Server role checks now use verified `cognito:groups`: viewer reads; approver also
approves/rolls back and acknowledges/suppresses/reopens; admin also creates intents
and starts evaluations. Missing identity is 401, missing/insufficient groups 403.
The browser sends no role flag. Local fixture mode uses a clearly synthetic actor
and configurable `CIG_LOCAL_ROLE`; this fallback is unavailable in production or
local live-discovery mode. Local SAM success does not validate Cognito JWTs.

There are six DynamoDB tables, preserving the three existing primary keys and
adding version/artifact sort keys plus history/audit/findings GSIs. Run against an
isolated local database:

```bash
cd backend
python scripts/local_db.py init --endpoint http://127.0.0.1:18000
python scripts/local_db.py migrate --endpoint http://127.0.0.1:18000
python scripts/local_db.py probe --endpoint http://127.0.0.1:18000
python scripts/verify_topology.py --endpoint http://127.0.0.1:18000 --evidence local-evidence/phase2-topology.json
```

`init` creates missing tables/indexes without replacing existing data. `migrate`
explicitly backfills legacy v1 snapshots, scopes and history index fields, with
audit; it skips other-account/region finding/evaluation records. The verifier
directly invokes API handlers plus the async worker and checks persistence,
version activation/rollback/immutability and audit reads. For interactive local
API use, start the loopback SAM API with fixture configuration and run
`scripts/run_evaluations.py --id <evaluationId>` in a separate local process with
the same non-secret table/endpoint/fixture settings. `--reconcile` marks expired
work failed. No background cloud service is required locally.

Cloud dispatch is optional: `EnableAsyncWorker=false` by default omits the
worker/event-source mapping and stream configuration. Production POST refuses
work when dispatch is disabled. Enabling it requires Academy permission for
DynamoDB Streams, Lambda event source mappings and their read permissions; these
are unverified. `ExistingExecutionRoleArn` can reference an already-approved lab
role. Its default sentinel `arn:aws:iam::000000000000:role/NOT_CONFIGURED` is never
used as a role; the default still lets SAM generate roles. Supplying a real role
disables SAM policy attachment for that function, so the operator must ensure its
permissions and PassRole entitlement already exist. Cognito groups/pool creation
also remain Academy deployment gates. No deployment or role assignment was run.

## Phase 1 additions (2026-10-15)

Intent creation now accepts `schemaVersion: 2` with `components`, `relationships`,
`trustBoundaries`, and per-component `criticality`. The legacy constraint manifest,
numeric `version`, `/v1` routes, response envelopes and error shape remain intact.
The server validates references, bounds, selectors and contradictory declarations;
v2 may contain relationship policy without an attribute constraint. See
[the approved schema and semantics](PLAN.md#3-phase-1-intent-v2-and-deterministic-conformance).
`backend/src/common/scenarios.py:scenario_manifest()` is a complete executable
example, also exercised through create/approve tests.

The deterministic engine supports ALLOWED_PATH, FORBIDDEN_PATH,
TRUST_BOUNDARY_CROSSING, REQUIRED_INTERMEDIARY, EXPOSURE_BLAST_RADIUS, required
relationships and required component membership. Every decision distinguishes
PASS, VIOLATION, UNKNOWN and NOT_APPLICABLE. Unruled zone crossings are ambiguous,
not confirmed violations. Missing attribute observations now produce UNKNOWN,
including missing RDS accessibility and unexpanded SG prefix-list sources.
Complete, applicable evidence is required before old findings can resolve;
findings in another account/region or under a removed/disabled rule are retained.

`GET /v1/architecture/graph?view=INTENT|ACTUAL|DIFF&intentId=...&version=...`
keeps the existing graph envelope. INTENT reads an approved declaration without
collecting AWS observations. DIFF uses MATCHED, MISSING, UNEXPECTED and UNKNOWN;
UNEXPECTED is a topology classification, not an assertion of severity. Observed
resource/edge IDs are stable across ACTUAL and DIFF. Existing frontend graph
schemas, controls, labels, fixtures and JSON manifest viewer consume these fields.
No graph comparison or path inference occurs in React.

Inventory retains EC2 tags and adds optional Lambda metadata/RDS SG attachments.
`meta.coverage.resourceTypes` and `meta.coverage.relationshipTypes` distinguish
COMPLETE, PARTIAL and UNSUPPORTED. Live collected edges remain **structural**;
neither shared VPC membership nor SG attachment establishes network reachability.
NETWORK_PERMISSION and NETWORK_REACHABILITY are currently UNSUPPORTED by the live
collector. Tests use clearly simulated flow evidence. No live network path has
been proven by this work.

SAM parameters `EnableConfig`, `EnableLambdaInventory`, and `EnableTagInventory`
default to false and conditionally grant their additional read permissions.
`TOPOLOGY_ENABLED=false` disables comparison/evaluation without discarding stored
manifests. A disabled Config feature skips the Config client/probe entirely.
The template still generates IAM roles and provisions Cognito; their acceptance
in this Academy lab is unverified. Config recording, Bedrock and modifying AWS
permissions are not introduced in Phase 1. No deployment is authorized.

For local simulated evaluation, explicitly override the declared SAM variables:

```json
{
  "Parameters": {
    "CIG_LOCAL": "true",
    "DYNAMODB_ENDPOINT_URL": "http://host.docker.internal:18000",
    "INVENTORY_PROVIDER": "fixture",
    "CIG_FIXTURE_SCENARIO": "lambda-db-bypass"
  }
}
```

Merge these non-secret settings with the existing table-name configuration in an
ignored local environment file. Available server-selected scenarios are `benign`,
`open-ssh`, `lambda-db-bypass`, `unruled-crossing`, and `source-disagreement`.
Requests cannot select arbitrary file paths or submit invented observation graphs.
Production rejects the fixture provider; local AWS discovery stays blocked.
Fixture metadata always marks observations/evaluations as simulated, and system
status continues to report AWS sources disconnected. The frontend local mode's
architecture/evaluation controls remain disabled until capability wiring is added;
the direct handler verifier below already exercises the local backend workflow.

To verify real DynamoDB Local persistence **without API Gateway or Cognito**:

```bash
cd backend
python scripts/local_db.py init --endpoint http://127.0.0.1:18000
python scripts/verify_topology.py --endpoint http://127.0.0.1:18000
```

Use an isolated local database and the project's installed Python dependencies.
The verifier directly invokes the Lambda handlers, checks consistent database
reads, all five scenarios and graph endpoints, then writes ignored evidence to
`local-evidence/phase1-topology.json`. It does not emulate deployed authentication.
Evaluation is still synchronous in Phase 1; async history/version/audit arrive in
Phase 2. Phase 4 will consume the disagreement evidence and add cross-validation;
these seeds do not claim Bedrock or independent-source validation is implemented.

Regenerate both cross-language transport fixtures together from real handlers:

```bash
CIG_CONTRACT_OUTPUT=frontend/tests/fixtures/backend-contract.json \
CIG_TOPOLOGY_CONTRACT_OUTPUT=frontend/tests/fixtures/topology-contract.json \
python -m unittest discover -s backend/tests -v
```

The sections below retain the dated baseline integration record; the Phase 1
validation record in `backend/VALIDATION.md` describes checks on the newer code.

The implemented MVP routes now have matching frontend consumers. The existing backend identifiers and response shapes are preserved; the API layer adapts transport fields for the UI. This is a local integration, not an AWS deployment.

## Connected flows

| UI | Backend contract |
| --- | --- |
| Overview | `GET /v1/dashboard/summary` reads stored findings and evaluation metrics; no evaluation means null conformance |
| Intents | JSON draft creation, paginated list, detail retrieval and explicit approval using `intentId` |
| Findings | List filters and opaque pagination, plus `/v1/findings/{findingId}` detail with stored evidence |
| System/status | Existing fields plus frontend readiness fields; local mode explicitly disables AWS discovery |
| Evaluation | Existing synchronous `/v1/evaluations` response is parsed and displayed; no invented job ID or polling |
| Architecture | `/v1/architecture/graph?view=ACTUAL` renders observed resources/edges; UNKNOWN means comparison is unavailable |
| Login | SAM template now includes a Cognito hosted domain, authorization-code OAuth and configurable callback/logout URLs |

`frontend/src/api/backendSchemas.ts` validates backend transport data and maps `findingId` to the UI's `id`, `firstSeenAt` to `detectedAt`, and `nextToken` to `meta.nextCursor`. JSON manifests retain native IDs and numeric versions. No historical versions, declared-resource counts or graph diff results are fabricated.

Finding acknowledgement, uploads, asynchronous jobs, intent topology comparison, drift history, audit events, Bedrock explanations and remediation remain disabled in live mode. Capability flags cannot enable a route that the backend does not implement. Stored dashboard drift/remediation counts are null and render as Not enabled. Partial inventory or incomplete scans cannot claim full conformance or resolve unseen findings.

## Run the actual local integration

Start the database and SAM using the main [README](README.md). Preserve any existing database container. From `backend/`:

```bash
sam validate --lint
sam build
sam local start-api \
  --template .aws-sam/build/template.yaml \
  --env-vars local-env.json \
  --docker-network cig-local \
  --region ap-south-1 \
  --skip-pull-image
```

The default CORS origin is `http://localhost:5173`. In a second terminal, from `frontend/`:

```bash
npm ci
test -f .env.development.local || cp .env.local-api.example .env.development.local
npm run dev -- --host localhost --port 5173 --strictPort
```

If a configuration file already exists, edit its public settings to match `.env.local-api.example`; copying only when absent will not switch an existing mock profile. The required settings are `VITE_USE_MOCKS=false`, `VITE_LOCAL_API=true`, `VITE_API_BASE_URL=http://127.0.0.1:3000` and the agreed region. Open `http://localhost:5173/intents`. The visible Local API banner identifies the unauthenticated, loopback-only development mode. It uses real DynamoDB Local data and does not run MSW mocks.

The local mode is restricted to a loopback API origin in development and is rejected by production builds. SAM's local JWT limitation remains; deployed API Gateway authentication is not removed. The backend refuses live discovery/evaluation in local mode, even if local SDK environment credentials exist. Local status does not claim AWS connectivity.

## Repeatable validation

From `backend/`, install `requirements-dev.txt` for the additional Moto contract tests:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

The generated frontend contract fixture came from actual Python handler responses using Moto and explicit test inventory observations. To regenerate it, run from the repository root:

```bash
CIG_CONTRACT_OUTPUT=frontend/tests/fixtures/backend-contract.json python3 -m unittest discover -s backend/tests -v
```

From `frontend/`:

```bash
npm test
npm run lint
npm run build
npx playwright install chromium
```

Browser tests expect a running real local backend and start a separate frontend on `http://127.0.0.1:15173`. For them, start SAM with `--parameter-overrides AllowedOrigin=http://127.0.0.1:15173`, then run:

```bash
CIG_API_URL=http://127.0.0.1:3000 npm run test:e2e
```

The browser tests leave their draft/approved test items in the configured local database. Screenshots/traces are written outside the repository. They do not prove live AWS discovery or Cognito login.

## Validation performed on 2026-10-13

- SAM CLI 1.168.0: template lint/validation and local Python 3.13 build passed.
- Thirteen Python tests passed, including handler persistence/evaluation/view contracts with Moto and the original SDK-stubbed checks.
- Seventeen frontend configuration/fixture/real-handler-response schema checks passed.
- Production TypeScript/Vite build passed. A build with `VITE_LOCAL_API=true` was rejected as intended; mock-enabled builds are also rejected.
- Actual SAM Lambda containers and isolated DynamoDB Local: POST 201, direct consistent database read, list GET and detail GET all passed. Intent ID: `bc168b39-52f4-481f-938a-44f14198a50a`.
- Chromium: create/read/approve/reload flow and unavailable-workflow checks passed at desktop and 390px mobile width, with no relevant browser errors in the checked intent flow. React Router emitted its existing future-flag warning.
- Browser plugin was not available; the repository's Playwright workflow performed rendered validation.
- Lint completed with three warnings from imported code (two fast-refresh exports and one unused mock-handler parameter).

The local database was an isolated temporary instance on host port 18000, the API used port 13000 and the browser test frontend used port 15173. Existing Docker databases were not modified. This proves persistence within the running local instance, not durability across an in-memory container restart.

## Production configuration and remaining work

Production uses `VITE_USE_MOCKS=false` and `VITE_LOCAL_API=false`, the deployed API origin, Cognito pool/client/domain outputs and exact OAuth callback/logout URLs. Configure `CognitoCallbackUrl`, `CognitoLogoutUrl` and `AllowedOrigin` together in the SAM deployment review. The template uses classic Cognito hosted login (`ManagedLoginVersion: 1`) with authorization-code flow, keeping the public app client secret-free. Amplify owns the PKCE flow and token/session handling. [Cognito client properties](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-userpoolclient.html).

No AWS resources were deployed. Live Cognito sign-in, anonymous/invalid-token rejection, AWS inventory, graph discovery and live evaluations need authorized Academy testing. Evaluation remains synchronous and bounded by the Lambda timeout; large accounts require later async orchestration. Full accessibility/component, boundary-lint and production security gates also remain broader work. Do not advertise these as verified.
