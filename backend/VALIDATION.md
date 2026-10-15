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
