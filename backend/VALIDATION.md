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
this bypasses API Gateway JWT authorization and does not establish a signed-in
browser journey. Deployment verification will follow this record.

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
